"""Операторская live-приёмка: безопасные summaries, существующие collectors и lifecycle.

Probe не открывает DB/Redis/Docker. Инфраструктура импортируется только для accept/doctor.
Секреты, raw HTTP bodies и exception text никогда не становятся диагностикой.
"""

import json
import math
import re
import time
from contextlib import nullcontext
from dataclasses import asdict

from sourcehealth.core.domain import RepositoryRef
from sourcehealth.integrations.sourcecraft.analytics import (
    CICollector,
    ContributorsCollector,
    IssuesCollector,
    PullRequestsCollector,
    ReleasesCollector,
)
from sourcehealth.integrations.sourcecraft.client import SourceCraftClient
from sourcehealth.integrations.sourcecraft.collectors import RepositoryCollector

COLLECTORS = (IssuesCollector, CICollector, PullRequestsCollector, ContributorsCollector, ReleasesCollector)
FATAL_RESOURCE_ERRORS = {"authentication_required", "access_denied", "invalid_response", "invalid_pagination"}


def configured(secret):
    return bool(secret and secret.get_secret_value().strip())


def preflight(settings, url):
    if not configured(settings.sourcecraft_pat):
        return None, "sourcecraft_pat_not_configured"
    try:
        return RepositoryRef.from_url(url), None
    except (ValueError, TypeError):
        return None, "invalid_sourcecraft_url"


def probe_sourcecraft(settings, url, *, client=None):
    """Возвращает (safe JSON, exit code); authenticated означает успешный metadata GET с PAT."""
    started = time.monotonic()
    ref, error = preflight(settings, url)
    output = {"overall": "error", "authenticated": False, "collectors": {}}
    if error:
        return {**output, "error": error}, 2
    output["repository"] = ref.canonical_url
    manager = nullcontext(client) if client is not None else SourceCraftClient(
        pat=settings.sourcecraft_pat.get_secret_value(), timeout=min(settings.sourcecraft_timeout, 10),
        max_pages=min(settings.sourcecraft_max_pages, 5), deadline_seconds=120)
    try:
        with manager as source:
            for cls in (RepositoryCollector, *COLLECTORS):
                before = time.monotonic()
                collected = cls(source).collect(ref)
                metadata = cls is RepositoryCollector
                complete = collected.availability == "available" and (metadata or collected.facts.get("complete") is True)
                item = {"availability": collected.availability.value, "complete": complete,
                        "observed_count": (1 if complete else 0) if metadata else len(collected.facts.get("items", [])),
                        "error": collected.error, "elapsed_seconds": round(time.monotonic() - before, 3)}
                output["collectors"][cls.name] = item
                if metadata:
                    if not complete:
                        output["error"] = collected.error or "metadata_unavailable"
                        return {**output, "elapsed_seconds": round(time.monotonic() - started, 3)}, 2
                    output["authenticated"] = True
                    item["metadata"] = {k: collected.facts[k] for k in ("id", "default_branch", "language", "visibility")
                                        if k in collected.facts}
        errors = {item["error"] for item in output["collectors"].values()}
        code = 2 if errors & FATAL_RESOURCE_ERRORS else 1 if any(not i["complete"] for i in output["collectors"].values()) else 0
        output["overall"] = {0: "ok", 1: "partial", 2: "error"}[code]
        return {**output, "elapsed_seconds": round(time.monotonic() - started, 3)}, code
    except Exception:
        return {**output, "overall": "error", "error": "probe_failed", "elapsed_seconds": round(time.monotonic() - started, 3)}, 2


def validate_acceptance(run, repository):
    """Проверяет сохранённый result повтором той же policy, без HTTP и новых расчётов метрик."""
    from sourcehealth.api.schemas import AnalysisDetails, AnalysisSummary
    from sourcehealth.core import AnalyzerResult
    from sourcehealth.core.domain import Category, DataAvailability, Evidence, Recommendation
    from sourcehealth.markdown import render_markdown
    from sourcehealth.recommendations import validate_recommendations
    from sourcehealth.scoring.coverage import score_coverage
    from sourcehealth.scoring.engine import ScoringEngine
    from sourcehealth.scoring.mvp import MVPPolicy

    def require(condition):
        if not condition:
            raise ValueError("acceptance_invariant_failed")

    require(run.status in {"completed", "partial"} and run.profile == "mvp-v1")
    require(isinstance(run.head_sha, str) and re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", run.head_sha))
    require(set(run.category_scores) == {c.value for c in Category})
    require(run.scoring_policy_version == MVPPolicy.version)
    payload = run.results
    require(payload.get("schema_version") == "3.0")
    require(payload["repository"]["head_sha"] == run.head_sha and payload["repository"]["id"] == str(repository.id))
    require(repository.visibility == "public" and repository.latest_analysis_id == run.id)
    require(repository.health_score == run.health_score and repository.head_sha == run.head_sha)
    require(payload["health_score"] == run.health_score and payload["scoring_policy_version"] == run.scoring_policy_version)
    require(payload["category_scores"] == run.category_scores and payload["recommendations"] == run.recommendations)
    require(run.data_coverage == {name: category["availability"] for name, category in run.category_scores.items()})
    checks = {}
    for name, raw in payload["checks"].items():
        check = AnalyzerResult(**{**raw, "availability": DataAvailability(raw["availability"]),
                                  "evidence": [Evidence(**value) for value in raw["evidence"]]})
        check.to_dict()
        require(check.category != "security" or check.source == "sourcecraft_appsec")
        require(check.source != "sourcehealth_local" or check.category == "code_health")
        checks[name] = check
    require({"repository_metadata", "issues", "cicd", "platform_activity", "documentation", "technical_debt",
             "git_activity", "sast", "sourcecraft_appsec"} <= checks.keys())
    require(checks["repository_metadata"].metrics.get("visibility") == "public")
    outcome = ScoringEngine(MVPPolicy()).score(checks)
    expected = json.loads(json.dumps({name: asdict(value) for name, value in outcome.categories.items()}))
    require(expected == run.category_scores and outcome.health_score == run.health_score)
    validate_recommendations([Recommendation(**item) for item in run.recommendations], checks)
    details = AnalysisDetails(**AnalysisSummary.model_validate(run).model_dump(), category_scores=run.category_scores,
                              data_coverage=run.data_coverage, recommendations=run.recommendations, checks=payload["checks"])
    require(details.score_coverage.model_dump() == score_coverage(run.scoring_policy_version, run.category_scores))
    json.dumps(payload, allow_nan=False)
    details.model_dump_json()
    render_markdown(payload)
    return {"repository_id": str(repository.id), "analysis_id": str(run.id), "status": run.status,
            "head_sha": run.head_sha, "health_score": run.health_score, "scoring_policy_version": run.scoring_policy_version,
            "score_coverage": details.score_coverage.model_dump(mode="json"),
            "categories": {name: {k: value[k] for k in ("score", "availability")} for name, value in run.category_scores.items()},
            "recommendation_count": len(run.recommendations)}


def accept_public(settings, url, sessions, redis, *, timeout=900, client=None, dispatch=None,
                  clock=time.monotonic, sleep=time.sleep):
    """Импорт → существующая очередь → bounded poll; timeout никогда не меняет status run."""
    from redis.exceptions import RedisError
    from sqlalchemy.exc import SQLAlchemyError

    from sourcehealth.storage.models import AnalysisRun, Repository

    from .jobs import dispatch_pending
    from .services import AnalysisService, ServiceError

    started = clock()
    ref, error = preflight(settings, url)
    if not error and settings.analysis_profile != "mvp-v1":
        error = "mvp_profile_required"
    if not math.isfinite(timeout) or not 0 < timeout <= 86400:
        error = "invalid_acceptance_timeout"
    if error:
        return {"overall": "error", "error": error}, 2
    output = {"overall": "error"}

    def finish(code, **values):
        return {**output, **values, "elapsed_seconds": round(clock() - started, 3)}, code

    try:
        redis.ping()
        service = AnalysisService(sessions, settings)
        manager = nullcontext(client) if client is not None else SourceCraftClient(
            pat=settings.sourcecraft_pat.get_secret_value(), timeout=min(settings.sourcecraft_timeout, timeout, 10),
            deadline_seconds=min(45, timeout))
        with manager as source:
            repository_id = service.import_public_repository(ref.canonical_url, client=source)
        run = service.request_analysis(repository_id, trigger="system")
        output.update(repository_id=str(repository_id), analysis_id=str(run.id), status=run.status)
        if clock() - started < timeout:
            (dispatch or dispatch_pending)(sessions, redis, settings.analysis_timeout)
        while True:
            with sessions() as db:
                row = db.get(AnalysisRun, run.id)
                output["status"] = row.status
                if row.status == "failed":
                    return finish(1, error="analysis_failed")
                if row.status in {"completed", "partial"}:
                    try:
                        summary = validate_acceptance(row, db.get(Repository, repository_id))
                    except Exception:
                        return finish(1, error="acceptance_invariant_failed")
                    # AppSec NO_DATA is expected; other incomplete checks must remain visible.
                    incomplete = any(c["availability"] not in {"available", "not_configured"}
                                     for name, c in row.results["checks"].items() if name != "sourcecraft_appsec")
                    return finish(1 if incomplete else 0, **summary, overall="partial" if incomplete else "ok")
            remaining = timeout - (clock() - started)
            if remaining <= 0:
                return finish(1, error="acceptance_timeout")
            sleep(min(2, remaining))
    except ServiceError as exc:
        return finish(2, error=exc.code)
    except RedisError:
        return finish(2, error="redis_unavailable")
    except SQLAlchemyError:
        return finish(2, error="database_unavailable")
    except Exception:
        return finish(2, error="acceptance_failed")


def doctor(settings, sessions, redis):
    """Только connectivity и presence; не печатает DSN, идентификаторы OAuth или secrets."""
    from sqlalchemy import text

    output = {"sourcecraft_pat": configured(settings.sourcecraft_pat),
              "yandex_client_id": bool(settings.yandex_client_id),
              "yandex_client_secret": configured(settings.yandex_client_secret),
              "session_secret": configured(settings.session_secret),
              "analysis_profile": settings.analysis_profile, "code_runtime_enabled": settings.code_runtime_enabled}
    try:
        with sessions() as db:
            db.execute(text("SELECT 1"))
        output["database_reachable"] = True
    except Exception:
        output["database_reachable"] = False
    try:
        output["redis_reachable"] = bool(redis.ping())
    except Exception:
        output["redis_reachable"] = False
    return output, 0 if output["database_reachable"] and output["redis_reachable"] else 1
