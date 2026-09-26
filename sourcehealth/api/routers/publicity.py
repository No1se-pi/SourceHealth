"""Public, read-only share metadata."""

from uuid import UUID

from fastapi import APIRouter, Request
from pydantic import BaseModel

from sourcehealth.publicity import PublicityService

router = APIRouter(prefix="/api/v1/publicity")


class ShareInfo(BaseModel):
    repository_id: UUID
    organization_slug: str
    repository_slug: str
    health_score: float | None
    health_available: bool
    repository_url: str
    badge_url: str
    badge_markdown: str
    latest_analysis_id: UUID | None
    latest_analysis_url: str | None
    markdown_report_url: str | None


@router.get("/repositories/{repository_id}", response_model=ShareInfo)
def share_repository(repository_id: UUID, request: Request):
    return PublicityService(request.app.state.sessions, request.app.state.settings.public_origin).repository(repository_id)
