"""DTO — независимый HTTP-контракт. OpenAPI является источником TypeScript types."""

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from sourcehealth.core.domain import Category, DataAvailability, RunStatus


class ErrorResponse(BaseModel):
    code: str
    message: str
    request_id: str


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    service: Literal["sourcehealth"] = "sourcehealth"


class RepositorySummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    organization_slug: str
    repository_slug: str
    canonical_url: str
    visibility: Literal["public", "private", "unknown"]
    health_score: float | None
    language: str | None
    likes: int | None
    last_activity_at: datetime | None
    latest_analysis_id: UUID | None


class RepositoryDetails(RepositorySummary):
    sourcecraft_id: str | None
    default_branch: str | None
    head_sha: str | None


class RepositoryPage(BaseModel):
    items: list[RepositorySummary]
    limit: int
    offset: int
    has_more: bool


class EvidenceDTO(BaseModel):
    id: str
    source: str
    type: str
    reference: str
    summary: str
    url: str | None = None
    location: str | None = None
    timestamp: datetime | None = None


class AnalyzerResultDTO(BaseModel):
    analyzer: str
    status: Literal["ok", "partial", "error"]
    availability: DataAvailability
    source: str
    category: Category | None
    analyzer_version: str
    contract_version: str
    metrics: dict[str, Any]
    findings: list[dict[str, Any]]
    metadata: dict[str, Any]
    error: str | None
    evidence: list[EvidenceDTO]


class CategoryScoreDTO(BaseModel):
    category: Category
    score: float | None = Field(default=None, ge=0, le=100)
    availability: DataAvailability
    explanation: str
    evidence_refs: list[str]


class RecommendationDTO(BaseModel):
    id: str
    category: Category
    title: str
    description: str
    priority: int = Field(ge=1, le=3)
    evidence_refs: list[str]
    suggested_action: str
    expected_impact: str | None


class AnalysisSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    repository_id: UUID
    status: RunStatus
    trigger: Literal["manual", "scheduled", "refresh", "system"]
    queued_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    head_sha: str | None
    health_score: float | None
    scoring_policy_version: str
    analyzer_contract_version: str
    error_code: str | None


class AnalysisDetails(AnalysisSummary):
    category_scores: dict[str, CategoryScoreDTO]
    data_coverage: dict[str, DataAvailability]
    recommendations: list[RecommendationDTO]
    checks: dict[str, AnalyzerResultDTO]


class AnalysisRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    force_refresh: bool = False


class UserDTO(BaseModel):
    id: UUID
