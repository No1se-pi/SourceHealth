"""Authenticated profile, tracking preferences and derived achievements."""

from uuid import UUID

from fastapi import APIRouter, Query, Request, Response

from sourcehealth.auth.sourcecraft import SourceCraftConnection
from sourcehealth.profile.service import ProfileService

from ..dependencies import check_origin, require_user
from ..schemas import ProfileDTO, ProfileRepositoryDTO, RepoTrackIn, RepoTrackPatch

router = APIRouter(prefix="/api/v1/profile")


def services(request):
    user = require_user(request)
    return UUID(user["id"]), ProfileService(request.app.state.sessions)


@router.get("", response_model=ProfileDTO)
def profile(request: Request):
    user_id, service = services(request)
    connection = SourceCraftConnection(request.app.state.auth)
    repos = service.repositories(user_id)
    achievements = service.achievements(user_id)
    summary = service.summary(user_id, repos_dto=repos, achievements_dto=achievements)
    return {
        "sourcecraft": connection.status(request.cookies.get("sh_session")),
        "repositories": repos,
        "achievements": achievements,
        "summary": summary,
    }


@router.get("/repositories", response_model=list[ProfileRepositoryDTO])
def repositories(request: Request, limit: int = Query(100, ge=1, le=100), offset: int = Query(0, ge=0, le=100000)):
    user_id, service = services(request)
    return service.repositories(user_id, limit=limit, offset=offset)


@router.post("/repositories", response_model=ProfileRepositoryDTO, status_code=201)
def track(body: RepoTrackIn, request: Request):
    check_origin(request)
    user_id, service = services(request)
    return service.track(user_id, body.repository_id)


@router.patch("/repositories/{repository_id}", response_model=ProfileRepositoryDTO)
def update(repository_id: UUID, body: RepoTrackPatch, request: Request):
    check_origin(request)
    user_id, service = services(request)
    return service.update(user_id, repository_id, refresh_preference=body.refresh_preference,
                          use_pat=body.scheduled_pat)


@router.delete("/repositories/{repository_id}", status_code=204)
def untrack(repository_id: UUID, request: Request):
    check_origin(request)
    user_id, service = services(request)
    service.untrack(user_id, repository_id)
    return Response(status_code=204)
