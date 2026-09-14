"""FastAPI composition root. Routers delegate commands to application services."""

import logging
from contextlib import asynccontextmanager
from uuid import UUID, uuid4

from fastapi import FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, RedirectResponse, Response
from redis.exceptions import RedisError
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException

from sourcehealth.application.connections import create_redis
from sourcehealth.application.jobs import dispatch_pending
from sourcehealth.application.services import AnalysisService, ServiceError
from sourcehealth.auth.service import AuthService
from sourcehealth.logging_config import configure_logging
from sourcehealth.markdown import render_markdown
from sourcehealth.settings import Settings
from sourcehealth.storage.database import create_database
from sourcehealth.storage.models import AnalysisRun, Repository

from .schemas import (
    AnalysisDetails,
    AnalysisRequest,
    AnalysisSummary,
    ErrorResponse,
    HealthResponse,
    RepositoryDetails,
    RepositoryPage,
    RepositorySummary,
    UserDTO,
)


def create_app(settings: Settings | None = None, *, sessions=None, redis=None) -> FastAPI:
    settings = settings or Settings()
    configure_logging()
    owned_engine = None
    if sessions is None:
        owned_engine, sessions = create_database(settings.database_url.get_secret_value())
    owned_redis = redis is None
    redis = redis if redis is not None else create_redis(settings.redis_url.get_secret_value())
    auth = AuthService(settings, redis, sessions)
    service = AnalysisService(sessions, settings)

    @asynccontextmanager
    async def lifespan(app):
        yield
        if owned_engine:
            owned_engine.dispose()
        if owned_redis:
            redis.close()

    app = FastAPI(title="SourceHealth API", version="1.0.0", lifespan=lifespan,
                  responses={code: {"model": ErrorResponse} for code in (400, 401, 403, 404, 409, 422, 503)})
    app.state.auth = auth

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        request.state.request_id = str(uuid4())
        try:
            response = await call_next(request)
        except Exception:
            # Log event identifiers only; arbitrary exception strings may contain credentials.
            logging.getLogger(__name__).error("request_failed", extra={"request_id": request.state.request_id,
                                                                       "component": "api", "event": "request_failed"})
            response = error(request, "internal_error", 500)
        response.headers["X-Request-ID"] = request.state.request_id
        response.headers["Cache-Control"] = "no-store"
        logging.getLogger(__name__).info("request_completed", extra={"request_id": request.state.request_id,
                                                                    "component": "api", "event": "request_completed"})
        return response

    def error(request, code, status):
        return JSONResponse(status_code=status, content={"code": code, "message": code,
                            "request_id": getattr(request.state, "request_id", str(uuid4()))})

    @app.exception_handler(ServiceError)
    async def service_error(request, exc):
        return error(request, exc.code, exc.status)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        return error(request, "invalid_request", 422)

    @app.exception_handler(HTTPException)
    async def http_error(request, exc):
        return error(request, "not_found" if exc.status_code == 404 else "request_rejected", exc.status_code)

    @app.exception_handler(SQLAlchemyError)
    @app.exception_handler(RedisError)
    async def dependency_error(request, exc):
        return error(request, "service_unavailable", 503)

    def require_user(request):
        user = auth.current_user(request.cookies.get("sh_session"))
        if user is None:
            raise ServiceError("authentication_required", 401)
        return user

    def check_origin(request):
        # All cookie-authenticated mutations require an exact browser Origin.
        if request.headers.get("origin") != settings.public_origin.rstrip("/"):
            raise ServiceError("invalid_origin", 403)

    def public_repository(db, repository_id):
        repo = db.get(Repository, repository_id)
        if repo is None or repo.visibility != "public":
            raise ServiceError("repository_not_found", 404)
        return repo

    def public_run(db, analysis_id):
        run = db.get(AnalysisRun, analysis_id)
        if run is None:
            raise ServiceError("analysis_not_found", 404)
        public_repository(db, run.repository_id)
        return run

    @app.get("/api/v1/health", response_model=HealthResponse)
    def health():
        """Liveness only: database readiness is a separate deployment check."""
        return HealthResponse()

    @app.get("/api/v1/repositories", response_model=RepositoryPage)
    def repositories(limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0, le=100000),
                     sort: str = Query("health_score", pattern="^(health_score|likes|last_activity)$"),
                     language: str | None = Query(None, max_length=64)):
        column = {"health_score": Repository.health_score, "likes": Repository.likes,
                  "last_activity": Repository.last_activity_at}[sort]
        query = select(Repository).where(Repository.visibility == "public")
        if language:
            query = query.where(Repository.language == language)
        with sessions() as db:
            rows = list(db.scalars(query.order_by(column.desc().nulls_last(), Repository.id).offset(offset).limit(limit + 1)))
            return RepositoryPage(items=[RepositorySummary.model_validate(row) for row in rows[:limit]],
                                  limit=limit, offset=offset, has_more=len(rows) > limit)

    @app.get("/api/v1/repositories/{repository_id}", response_model=RepositoryDetails)
    def repository(repository_id: UUID):
        with sessions() as db:
            return RepositoryDetails.model_validate(public_repository(db, repository_id))

    @app.get("/api/v1/repositories/{repository_id}/analyses/latest", response_model=AnalysisSummary)
    def latest(repository_id: UUID):
        with sessions() as db:
            repo = public_repository(db, repository_id)
            if repo.latest_analysis_id is None:
                raise ServiceError("analysis_not_found", 404)
            return AnalysisSummary.model_validate(public_run(db, repo.latest_analysis_id))

    @app.post("/api/v1/repositories/{repository_id}/analyses", response_model=AnalysisSummary, status_code=202)
    def start(repository_id: UUID, body: AnalysisRequest, request: Request):
        require_user(request)
        check_origin(request)
        if body.force_refresh:
            # Force policy requires repository permissions, not merely a valid Я ID.
            raise ServiceError("force_refresh_not_authorized", 403)
        run = service.request_analysis(repository_id)
        try:
            dispatch_pending(sessions, redis, settings.analysis_timeout)
        except RedisError:
            pass  # Durable queued row will be dispatched by reconciliation command.
        return AnalysisSummary.model_validate(run)

    @app.get("/api/v1/analyses/{analysis_id}", response_model=AnalysisDetails)
    def analysis(analysis_id: UUID):
        with sessions() as db:
            run = public_run(db, analysis_id)
            return AnalysisDetails(**AnalysisSummary.model_validate(run).model_dump(), category_scores=run.category_scores,
                                   data_coverage=run.data_coverage, recommendations=run.recommendations,
                                   checks=run.results.get("checks", {}))

    @app.get("/api/v1/analyses/{analysis_id}/report.md", response_class=Response,
             responses={200: {"content": {"text/markdown": {"schema": {"type": "string"}}}}})
    def markdown(analysis_id: UUID):
        with sessions() as db:
            run = public_run(db, analysis_id)
            if run.status not in {"completed", "partial"}:
                raise ServiceError("report_not_ready", 409)
            return Response(render_markdown(run.results), media_type="text/markdown; charset=utf-8",
                            headers={"Content-Disposition": f'attachment; filename="sourcehealth-{analysis_id}.md"'})

    def cookie(response, name, token, max_age):
        response.set_cookie(name, token, max_age=max_age, secure=settings.cookie_secure, httponly=True,
                            samesite="lax", path="/")

    @app.get("/api/v1/auth/yandex/login", response_class=RedirectResponse)
    def login():
        url, token = auth.login()
        response = RedirectResponse(url, status_code=302)
        cookie(response, "sh_oauth", token, 600)
        return response

    @app.get("/api/v1/auth/yandex/callback", response_class=RedirectResponse)
    def callback(request: Request, state: str = Query(max_length=256), code: str = Query(max_length=2048)):
        token = auth.callback(browser_token=request.cookies.get("sh_oauth", ""), state=state, code=code)
        auth.logout(request.cookies.get("sh_session"))
        response = RedirectResponse("/auth/callback", status_code=303)
        response.delete_cookie("sh_oauth", path="/")
        cookie(response, "sh_session", token, settings.session_ttl)
        return response

    @app.post("/api/v1/auth/logout", status_code=204)
    def logout(request: Request):
        check_origin(request)
        auth.logout(request.cookies.get("sh_session"))
        response = Response(status_code=204)
        response.delete_cookie("sh_session", path="/")
        return response

    @app.get("/api/v1/me", response_model=UserDTO)
    def me(request: Request):
        return require_user(request)

    return app
