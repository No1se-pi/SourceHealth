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
    RepositoryDetails,
    RepositoryImport,
    RepositoryPage,
    RepositorySummary,
)

router = APIRouter()


def _repository_dto(repository: Repository, run: AnalysisRun | None, *, details: bool = False):
    schema = RepositoryDetails if details else RepositorySummary
    preview = score_preview(run.scoring_policy_version, run.category_scores) if run is not None else None
    return schema(**schema.model_validate(repository).model_dump(exclude={"score_preview"}), score_preview=preview)


@router.post("/api/v1/repositories", response_model=RepositoryDetails, status_code=201)
def import_repository(body: RepositoryImport, request: Request):
    require_user(request)
    check_origin(request)
    repository_id = request.app.state.service.import_public_repository(body.url)
    with request.app.state.sessions() as db:
        repository = public_repository(db, repository_id)
        run = db.get(AnalysisRun, repository.latest_analysis_id) if repository.latest_analysis_id else None
        return _repository_dto(repository, run, details=True)


@router.get("/api/v1/repositories", response_model=RepositoryPage)
def repositories(request: Request, limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0, le=100000),
                 sort: str = Query("health_score", pattern="^(health_score|likes|last_activity)$"),
                 language: str | None = Query(None, max_length=64)):
    column = {"health_score": Repository.health_score, "likes": Repository.likes,
              "last_activity": Repository.last_activity_at}[sort]
    query = (select(Repository, AnalysisRun)
             .outerjoin(AnalysisRun, AnalysisRun.id == Repository.latest_analysis_id)
             .where(Repository.visibility == "public"))
    if language:
        query = query.where(Repository.language == language)
    with request.app.state.sessions() as db:
        rows = list(db.execute(query.order_by(column.desc().nulls_last(), Repository.id)
                               .offset(offset).limit(limit + 1)).all())
        return RepositoryPage(items=[_repository_dto(repository, run) for repository, run in rows[:limit]],
                              limit=limit, offset=offset, has_more=len(rows) > limit)


@router.get("/api/v1/repositories/{repository_id}", response_model=RepositoryDetails)
def repository(repository_id: UUID, request: Request):
    with request.app.state.sessions() as db:
        repository = public_repository(db, repository_id)
        run = db.get(AnalysisRun, repository.latest_analysis_id) if repository.latest_analysis_id else None
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
