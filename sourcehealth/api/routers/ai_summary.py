"""Authenticated, explicit-click AI report endpoint."""

import hashlib
import json
import logging
from uuid import UUID

from fastapi import APIRouter, Request
from redis.exceptions import RedisError

from sourcehealth.ai.context import build_ai_context
from sourcehealth.ai.contracts import LegacyAISummaryResult, LegacyGroundedAction, LegacyGroundedStatement
from sourcehealth.ai.prompt import PROMPT_VERSION, SCHEMA_VERSION
from sourcehealth.ai.yandex import MODEL_NAMES, YandexAIError, YandexAISummaryProvider
from sourcehealth.application.services import ServiceError
from sourcehealth.scoring.coverage import score_coverage
from sourcehealth.storage.models import Repository

from ..dependencies import check_origin, public_run, require_user
from ..schemas import AIReportRequest, AIReportResponse, AISummaryRequest, AISummaryResponse

router = APIRouter()
logger = logging.getLogger(__name__)


def _cache_key(analysis_id: UUID, mode: str, detail: str = "brief") -> str:
    digest = hashlib.sha256(
        f"{analysis_id}:{mode}:{detail}:{PROMPT_VERSION}:{SCHEMA_VERSION}".encode(),
    ).hexdigest()
    return f"ai-report:{digest}"


def _generate_report(analysis_id: UUID, model: str, detail: str, request: Request) -> AIReportResponse:
    check_origin(request)
    user = require_user(request)
    settings, redis = request.app.state.settings, request.app.state.redis
    if not settings.yandex_ai_api_key or not settings.yandex_ai_folder_id:
        raise ServiceError("ai_provider_disabled", 503)
    with request.app.state.sessions() as db:
        run = public_run(db, analysis_id)
        if run.status not in {"completed", "partial"}:
            raise ServiceError("ai_summary_not_ready", 409)
        repo = db.get(Repository, run.repository_id)
        report = dict(run.results or {})
        report.update({
            "analysis_id": str(run.id), "organization_slug": repo.organization_slug,
            "repository_slug": repo.repository_slug, "health_score": run.health_score,
            "scoring_policy_version": run.scoring_policy_version,
            "category_scores": run.category_scores, "recommendations": run.recommendations,
            "score_coverage": score_coverage(run.scoring_policy_version, run.category_scores),
        })

    key = _cache_key(analysis_id, model, detail)
    try:
        cached = redis.get(key)
        if cached:
            payload = json.loads(cached)
            payload["cached"] = True
            return AIReportResponse.model_validate(payload)
    except (RedisError, ValueError, TypeError):
        logger.warning("ai_cache_read_failed", extra={"component": "ai", "event": "cache_read_failed"})

    rate_key = f"ai-rate:{user['id']}"
    try:
        count = redis.incr(rate_key)
        if count == 1:
            redis.expire(rate_key, 3600)
        if count > settings.yandex_ai_rate_limit:
            raise ServiceError("ai_rate_limited", 429)
    except RedisError:
        logger.warning("ai_rate_limit_unavailable", extra={"component": "ai", "event": "rate_limit_unavailable"})

    context = build_ai_context(report, detail)
    provider = getattr(request.app.state, "ai_provider", None) or YandexAISummaryProvider(
        settings.yandex_ai_api_key.get_secret_value(), settings.yandex_ai_folder_id,
        timeout=settings.yandex_ai_timeout,
    )
    try:
        result = provider.summarize(context, model, detail)
    except YandexAIError as exc:
        logger.warning("ai_request_failed", extra={
            "component": "ai", "event": exc.code, "mode": model, "detail": detail,
        })
        raise ServiceError(exc.code, exc.status) from None
    grounding_status = getattr(provider, "last_grounding_status", "grounded")
    if grounding_status not in {"grounded", "warning"}:
        grounding_status = "grounded"
    response = AIReportResponse(
        mode=model, detail=detail, model_name=MODEL_NAMES[model], cached=False, summary=result,
        grounding_status=grounding_status, grounding_validated=grounding_status == "grounded",
    )
    try:
        redis.set(key, response.model_dump_json(), ex=settings.yandex_ai_cache_ttl)
    except RedisError:
        logger.warning("ai_cache_write_failed", extra={"component": "ai", "event": "cache_write_failed"})
    return response


def _legacy_statement(statement) -> LegacyGroundedStatement:
    return LegacyGroundedStatement(text=statement.text[:500], evidence_refs=statement.evidence_refs)


def _legacy_response(report: AIReportResponse) -> AISummaryResponse:
    if report.grounding_status != "grounded":
        raise ServiceError("ai_grounding_failed", 503)
    summary = report.summary
    legacy = LegacyAISummaryResult(
        executive_summary=summary.executive_summary[:1000],
        strengths=[_legacy_statement(item) for item in summary.strengths[:5]],
        risks=[_legacy_statement(item) for item in summary.risks[:5]],
        actions=[LegacyGroundedAction(
            text=item.action[:500], recommendation_ids=item.recommendation_ids,
            evidence_refs=item.evidence_refs,
        ) for item in summary.actions[:5]],
        limitations=[_legacy_statement(item) for item in summary.limitations[:5]],
    )
    return AISummaryResponse(
        mode=report.mode, model_name=report.model_name, cached=report.cached, summary=legacy,
    )


@router.post("/api/v1/analyses/{analysis_id}/ai-summary", response_model=AISummaryResponse)
def ai_summary(analysis_id: UUID, body: AISummaryRequest, request: Request):
    """Preserve the frozen v1 response for clients deployed before AI reports."""
    return _legacy_response(_generate_report(analysis_id, body.model, "brief", request))


@router.post("/api/v1/analyses/{analysis_id}/ai-report", response_model=AIReportResponse)
def ai_report(analysis_id: UUID, body: AIReportRequest, request: Request):
    return _generate_report(analysis_id, body.model, body.detail, request)
