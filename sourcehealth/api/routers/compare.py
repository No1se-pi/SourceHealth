"""Bounded comparison of stored public repository results."""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel, Field

from sourcehealth.compare import CompareService

router = APIRouter(prefix="/api/v1/compare")


class ComparedCategory(BaseModel):
    score: float | None = Field(default=None, ge=0, le=100)
    availability: str


class ComparedRepository(BaseModel):
    repository_id: UUID
    organization_slug: str
    repository_slug: str
    canonical_url: str
    health_score: float | None
    data_coverage_percent: int | None = Field(default=None, ge=0, le=100)
    language: str | None
    likes: int | None
    last_activity_at: datetime | None
    categories: dict[str, ComparedCategory]
    latest_analysis_id: UUID | None
    scoring_policy_version: str | None


class ComparableInfo(BaseModel):
    health: bool
    policy_versions_match: bool


class CompareResponse(BaseModel):
    repositories: list[ComparedRepository]
    comparable: ComparableInfo


@router.get("", response_model=CompareResponse)
def compare(request: Request, repository_id: list[UUID] = Query(..., min_length=2, max_length=4)):
    return CompareService(request.app.state.sessions).compare(repository_id)
