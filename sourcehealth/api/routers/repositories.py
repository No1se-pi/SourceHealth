"""Repositories HTTP endpoints."""

from uuid import UUID, uuid4

from fastapi import APIRouter, Query, Request
from redis.exceptions import RedisError
from sqlalchemy import select

from sourcehealth.application.jobs import dispatch_pending
from sourcehealth.application.services import ServiceError
from sourcehealth.auth.sourcecraft import SourceCraftConnection
from sourcehealth.scoring.coverage import score_preview
from sourcehealth.storage.models import AnalysisRun, Repository

from ..dependencies import check_origin, public_repository, public_run, require_user
from ..schemas import (
    AnalysisPage,
    AnalysisRequest,
    AnalysisSummary,
    CategoryScoreMiniDTO,
    ErrorResponse,
    RepositoryDetails,
    RepositoryImport,
    RepositoryPage,
    RepositorySummary,
)

router = APIRouter()


def _repository_dto(repository: Repository, run: AnalysisRun | None, *, details: bool = False, rank: int | None = None):
    schema = RepositoryDetails if details else RepositorySummary
    preview = score_preview(run.scoring_policy_version, run.category_scores) if run is not None else None

    effective_health = repository.health_score
    if run is not None and run.profile == "mvp-v1" and run.health_score is not None:
        effective_health = run.health_score

    effective_latest_analysis_id = (
        run.id if (run is not None and run.profile == "mvp-v1")
        else repository.latest_analysis_id
    )

    cat_scores = {}
    coverage_pct = None
    if run is not None and isinstance(run.category_scores, dict):
        for cat_name in ("documentation", "cicd", "security", "activity", "issues", "code_health"):
            data = run.category_scores.get(cat_name)
            if isinstance(data, dict):
                cat_scores[cat_name] = CategoryScoreMiniDTO(
                    score=data.get("score"),
                    availability=data.get("availability", "no_data"),
                )
            else:
                cat_scores[cat_name] = CategoryScoreMiniDTO(score=None, availability="no_data")
        if isinstance(run.data_coverage, dict):
            coverage_val = run.data_coverage.get("nominal_weight_percent")
            if coverage_val is not None:
                try:
                    coverage_pct = int(coverage_val)
                except Exception:
                    coverage_pct = None

    return schema(
        **schema.model_validate(repository).model_dump(
            exclude={"score_preview", "category_scores", "data_coverage_percent", "health_rank", "health_score", "latest_analysis_id"}
        ),
        latest_analysis_id=effective_latest_analysis_id,
        health_score=effective_health,
        score_preview=preview,
        category_scores=cat_scores,
        data_coverage_percent=coverage_pct,
        health_rank=rank,
    )


@router.post("/api/v1/repositories", response_model=RepositoryDetails, status_code=201,
             responses={502: {"model": ErrorResponse}})
def import_repository(body: RepositoryImport, request: Request):
    require_user(request)
    check_origin(request)
    connection = SourceCraftConnection(request.app.state.auth)
    client = connection.client_for_repository_import(request.cookies.get("sh_session"))
    if client is None:
        repository_id = request.app.state.service.import_public_repository(
            body.url, request_id=request.state.request_id)
    else:
        with client as source:
            repository_id = request.app.state.service.import_public_repository(
                body.url, client=source, request_id=request.state.request_id)
    with request.app.state.sessions() as db:
        repository = public_repository(db, repository_id)
        run = db.get(AnalysisRun, repository.latest_analysis_id) if repository.latest_analysis_id else None
        return _repository_dto(repository, run, details=True)


@router.get("/api/v1/repositories", response_model=RepositoryPage)
def repositories(
    request: Request,
    q: str | None = Query(None, max_length=256),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0, le=100000),
    sort: str = Query("health_score", pattern="^(relevance|health_score|likes|last_activity|name|security|cicd|activity|documentation|issues|code_health|coverage)$"),
    order: str = Query("desc", pattern="^(asc|desc)$"),
    language: str | None = Query(None, max_length=64),
    topic: str | None = Query(None, max_length=64),
    origin: str | None = Query(None, pattern="^(native|fork|migrated|unknown)$"),
    health_min: float | None = Query(None, ge=0, le=100),
    health_max: float | None = Query(None, ge=0, le=100),
    health_status: str | None = Query(None, pattern="^(available|forming|no_data|all)$"),
    security_status: str | None = Query(None, pattern="^(available|no_data|any)$"),
    security_min: float | None = Query(None, ge=0, le=100),
    security_max: float | None = Query(None, ge=0, le=100),
    cicd_status: str | None = Query(None, pattern="^(available|no_data|any)$"),
    cicd_min: float | None = Query(None, ge=0, le=100),
    cicd_max: float | None = Query(None, ge=0, le=100),
    activity_status: str | None = Query(None, pattern="^(available|no_data|any)$"),
    activity_min: float | None = Query(None, ge=0, le=100),
    activity_max: float | None = Query(None, ge=0, le=100),
    documentation_status: str | None = Query(None, pattern="^(available|no_data|any)$"),
    documentation_min: float | None = Query(None, ge=0, le=100),
    documentation_max: float | None = Query(None, ge=0, le=100),
    issues_status: str | None = Query(None, pattern="^(available|no_data|any)$"),
    issues_min: float | None = Query(None, ge=0, le=100),
    issues_max: float | None = Query(None, ge=0, le=100),
    code_health_status: str | None = Query(None, pattern="^(available|no_data|any)$"),
    code_health_min: float | None = Query(None, ge=0, le=100),
    code_health_max: float | None = Query(None, ge=0, le=100),
    coverage_min: int | None = Query(None, ge=0, le=100),
    activity_days: int | None = Query(None, ge=1, le=3650),
):
    from sourcehealth.catalog.query import CatalogFilters, get_catalog_repositories

    filters = CatalogFilters(
        q=q,
        limit=limit,
        offset=offset,
        sort=sort,
        order=order,
        language=language,
        topic=topic,
        origin=origin,
        health_min=health_min,
        health_max=health_max,
        health_status=health_status,
        security_status=security_status,
        security_min=security_min,
        security_max=security_max,
        cicd_status=cicd_status,
        cicd_min=cicd_min,
        cicd_max=cicd_max,
        activity_status=activity_status,
        activity_min=activity_min,
        activity_max=activity_max,
        documentation_status=documentation_status,
        documentation_min=documentation_min,
        documentation_max=documentation_max,
        issues_status=issues_status,
        issues_min=issues_min,
        issues_max=issues_max,
        code_health_status=code_health_status,
        code_health_min=code_health_min,
        code_health_max=code_health_max,
        coverage_min=coverage_min,
        activity_days=activity_days,
    )
    with request.app.state.sessions() as db:
        rows, total = get_catalog_repositories(db, filters)
        items = []
        for idx, (repo_row, run_row) in enumerate(rows):
            effective_health = (
                run_row.health_score
                if (run_row is not None and run_row.profile == "mvp-v1" and run_row.health_score is not None)
                else repo_row.health_score
            )
            rank = None
            if sort == "health_score" and order == "desc" and effective_health is not None:
                rank = offset + idx + 1
            items.append(_repository_dto(repo_row, run_row, rank=rank))

        return RepositoryPage(
            items=items,
            limit=limit,
            offset=offset,
            total=total,
            has_more=(offset + len(rows)) < total,
            applied_sort=sort,
            applied_order=order,
        )


@router.get("/api/v1/repositories/{repository_id}", response_model=RepositoryDetails)
def repository(repository_id: UUID, request: Request):
    with request.app.state.sessions() as db:
        repository = public_repository(db, repository_id)
        canonical_run = db.scalars(
            select(AnalysisRun)
            .where(
                AnalysisRun.repository_id == repository_id,
                AnalysisRun.profile == "mvp-v1",
                AnalysisRun.status.in_(["completed", "partial"]),
            )
            .order_by(AnalysisRun.completed_at.desc().nulls_last(), AnalysisRun.id.desc())
            .limit(1)
        ).first()
        run = canonical_run if canonical_run is not None else (
            db.get(AnalysisRun, repository.latest_analysis_id) if repository.latest_analysis_id else None
        )
        return _repository_dto(repository, run, details=True)


@router.get("/api/v1/repositories/{repository_id}/analyses/latest", response_model=AnalysisSummary)
def latest(repository_id: UUID, request: Request):
    with request.app.state.sessions() as db:
        repo = public_repository(db, repository_id)
        if repo.latest_analysis_id is None:
            raise ServiceError("analysis_not_found", 404)
        return AnalysisSummary.model_validate(public_run(db, repo.latest_analysis_id))


@router.get("/api/v1/repositories/{repository_id}/analyses", response_model=AnalysisPage)
def history(repository_id: UUID, request: Request, limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0)):
    with request.app.state.sessions() as db:
        public_repository(db, repository_id)
        rows = list(db.scalars(select(AnalysisRun).where(AnalysisRun.repository_id == repository_id)
                               .order_by(AnalysisRun.queued_at.desc(), AnalysisRun.id.desc())
                               .offset(offset).limit(limit + 1)))
        return AnalysisPage(items=[AnalysisSummary.model_validate(row) for row in rows[:limit]],
                            limit=limit, offset=offset, has_more=len(rows) > limit)


@router.post("/api/v1/repositories/{repository_id}/analyses", response_model=AnalysisSummary, status_code=202)
def start(repository_id: UUID, body: AnalysisRequest, request: Request):
    require_user(request)
    check_origin(request)
    if body.force_refresh:
        # Force policy requires repository permissions, not merely a valid Я ID.
        raise ServiceError("force_refresh_not_authorized", 403)
    connection = SourceCraftConnection(request.app.state.auth)
    session_token = request.cookies.get("sh_session")
    connected = connection.status(session_token)["connected"]
    candidate_id = uuid4() if connected else None
    if candidate_id is not None and not connection.lease_for_analysis(session_token, candidate_id):
        raise ServiceError("sourcecraft_connection_expired", 409)
    try:
        run = request.app.state.service.request_analysis(
            repository_id, require_official_security=connected, preallocated_id=candidate_id)
    except Exception:
        if candidate_id is not None:
            connection.delete_analysis_credential(candidate_id)
        raise
    # Existing active/cache runs retain their original authorization context.
    if candidate_id is not None and run.id != candidate_id:
        connection.delete_analysis_credential(candidate_id)
    try:
        dispatch_pending(request.app.state.sessions, request.app.state.redis, request.app.state.settings.analysis_timeout)
    except RedisError:
        pass  # Durable queued row will be dispatched by reconciliation command.
    return AnalysisSummary.model_validate(run)
