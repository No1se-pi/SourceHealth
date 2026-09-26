"""Сессионное подключение SourceCraft; приватные metadata не сохраняются."""

from fastapi import APIRouter, Query, Request, Response

from sourcehealth.auth.sourcecraft import SourceCraftConnection

from ..dependencies import check_origin, require_user
from ..schemas import ConnectedRepositoriesDTO, SourceCraftConnect, SourceCraftConnectionDTO, SourceCraftRetentionUpdate

router = APIRouter(prefix="/api/v1/sourcecraft")


def connection(request):
    require_user(request)
    request.app.state.auth._configured()  # HTTPS or explicit localhost auth configuration.
    return SourceCraftConnection(request.app.state.auth), request.cookies.get("sh_session")


@router.post("/connection", response_model=SourceCraftConnectionDTO)
def connect(body: SourceCraftConnect, request: Request):
    check_origin(request)
    service, token = connection(request)
    return service.connect(token, body.pat, body.retention_seconds)


@router.get("/connection", response_model=SourceCraftConnectionDTO)
def status(request: Request):
    service, token = connection(request)
    return service.status(token)


@router.patch("/connection", response_model=SourceCraftConnectionDTO)
def update_retention(body: SourceCraftRetentionUpdate, request: Request):
    check_origin(request)
    service, token = connection(request)
    return service.update_retention(token, body.retention_seconds)


@router.delete("/connection", status_code=204)
def disconnect(request: Request):
    check_origin(request)
    service, token = connection(request)
    service.disconnect(token)
    return Response(status_code=204)


@router.get("/repositories", response_model=ConnectedRepositoriesDTO)
def repositories(request: Request, organization: str = Query(pattern=r"^[A-Za-z0-9_-]{1,128}$")):
    service, token = connection(request)
    return service.repositories(token, organization)


@router.get("/me/repositories", response_model=ConnectedRepositoriesDTO)
def my_repositories(request: Request, page_token: str | None = Query(default=None, max_length=1024)):
    service, token = connection(request)
    return service.my_repositories(token, page_token)
