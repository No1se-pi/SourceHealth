"""FastAPI composition root. Routers delegate commands to application services."""

import logging
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from redis.exceptions import RedisError
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException

from sourcehealth.application.connections import create_redis
from sourcehealth.application.services import AnalysisService, ServiceError
from sourcehealth.auth.service import AuthService
from sourcehealth.logging_config import configure_logging
from sourcehealth.settings import Settings
from sourcehealth.storage.database import create_database

from .routers import analyses, health, repositories, sourcecraft
from .routers import auth as auth_routes
from .schemas import ErrorResponse


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
    app.state.settings = settings
    app.state.sessions = sessions
    app.state.redis = redis
    app.state.service = service

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

    app.include_router(health.router)
    app.include_router(repositories.router)
    app.include_router(analyses.router)
    app.include_router(auth_routes.router)
    app.include_router(sourcecraft.router)
    return app
