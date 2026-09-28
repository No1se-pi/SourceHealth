"""DTO — независимый HTTP-контракт. OpenAPI является источником TypeScript types."""

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from sourcehealth.ai.contracts import AISummaryResult
from sourcehealth.core.domain import Category, DataAvailability, RunStatus


class ErrorResponse(BaseModel):
    code: str
    message: str
    request_id: str


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    service: Literal["sourcehealth"] = "sourcehealth"


class CategoryScoreMiniDTO(BaseModel):
    score: float | None = None
    availability: str


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
    score_preview: "ScorePreviewDTO | None" = None
    description: str | None = None
    logo_url: str | None = None
    origin: str | None = "unknown"
    project_slug: str | None = None
    topics: list[str] = Field(default_factory=list)
    category_scores: dict[str, CategoryScoreMiniDTO] = Field(default_factory=dict)
    data_coverage_percent: int | None = None
    health_rank: int | None = None


class RepositoryDetails(RepositorySummary):
    sourcecraft_id: str | None
    default_branch: str | None
    head_sha: str | None


class RepositoryPage(BaseModel):
    items: list[RepositorySummary]
    limit: int
    offset: int
    total: int
    has_more: bool
    applied_sort: str | None = None
    applied_order: str | None = None


class HealthHistogramBucket(BaseModel):
    range_label: str
    min_score: float
    max_score: float
    count: int


class CatalogStatsDTO(BaseModel):
    catalog_total_public: int
    matched_total: int
    analyzed_count: int
    health_available_count: int
    health_forming_count: int
    health_no_data_count: int
    health_median: float | None = None
    health_q1: float | None = None
    health_q3: float | None = None
    health_histogram: list[HealthHistogramBucket]
    histogram_no_data_count: int
    languages: dict[str, int]
    topics: dict[str, int]
    origins: dict[str, int]


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
    profile: str
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




class AnalysisPage(BaseModel):
    items: list[AnalysisSummary]
    limit: int
    offset: int
    has_more: bool


class ScoreCoverageDTO(BaseModel):
    nominal_weight_percent: int = Field(ge=0, le=100)
    scored_categories: int = Field(ge=0, le=6)
    unscored_categories: list[Category]
    partial_categories: list[Category]


class ScorePreviewDTO(BaseModel):
    score: float | None = Field(default=None, ge=0, le=100)
    nominal_weight_percent: int = Field(ge=0, le=100)
    scored_categories: int = Field(ge=0, le=6)
    numeric: bool


class AnalysisDetails(AnalysisSummary):
    category_scores: dict[str, CategoryScoreDTO]
    data_coverage: dict[str, DataAvailability]
    recommendations: list[RecommendationDTO]
    checks: dict[str, AnalyzerResultDTO]
    score_coverage: ScoreCoverageDTO | None = None
    score_preview: ScorePreviewDTO | None = None

    @model_validator(mode="after")
    def derive_score_coverage(self):
        from sourcehealth.scoring.coverage import score_coverage, score_preview

        categories = {name: category.model_dump() for name, category in self.category_scores.items()}
        coverage = score_coverage(self.scoring_policy_version, categories)
        self.score_coverage = ScoreCoverageDTO(**coverage) if coverage is not None else None
        preview = score_preview(self.scoring_policy_version, categories)
        self.score_preview = ScorePreviewDTO(**preview) if preview is not None else None
        return self


class AnalysisRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    force_refresh: bool = False


class AISummaryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    model: Literal["flash", "lite", "pro"]


class AISummaryResponse(BaseModel):
    provider: Literal["yandex-ai-studio"] = "yandex-ai-studio"
    mode: Literal["flash", "lite", "pro"]
    model_name: str
    grounding_validated: Literal[True] = True
    cached: bool
    summary: AISummaryResult


class RepositoryImport(BaseModel):
    model_config = ConfigDict(extra="forbid")
    url: str = Field(min_length=1, max_length=512)


class UserDTO(BaseModel):
    id: UUID


class SourceCraftConnect(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pat: str = Field(min_length=1, max_length=4096, repr=False)
    retention_seconds: Literal[1800, 21600, 86400, 604800] = 1800


class SourceCraftConnectionDTO(BaseModel):
    connected: bool
    expires_in: int
    retention_seconds: Literal[1800, 21600, 86400, 604800] = 1800


class SourceCraftRetentionUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    retention_seconds: Literal[1800, 21600, 86400, 604800]


class ConnectedRepositoryDTO(BaseModel):
    id: str | None = None
    organization_slug: str | None = None
    repository_slug: str | None = None
    url: str
    visibility: Literal["public", "private", "internal"]
    can_analyze: bool
    default_branch: str | None = None
    is_empty: bool | None = None


class ConnectedRepositoriesDTO(BaseModel):
    items: list[ConnectedRepositoryDTO]
    has_more: bool
    next_page_token: str | None = None


class ProfileRepositoryDTO(BaseModel):
    repository_id: UUID
    organization_slug: str
    repository_slug: str
    health_score: float | None
    score_preview: ScorePreviewDTO | None = None
    last_analysis_at: datetime | None
    last_activity_at: datetime | None
    analysis_status: RunStatus | None
    next_analysis_at: datetime
    refresh_preference: Literal["adaptive", "1h", "6h", "24h", "7d", "off"]
    use_pat_for_scheduled_analysis: bool


class RepoTrackIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    repository_id: UUID


class RepoTrackPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    refresh_preference: Literal["adaptive", "1h", "6h", "24h", "7d", "off"]
    scheduled_pat: bool = Field(False, alias="use_pat_for_scheduled_analysis")


class AchievementDTO(BaseModel):
    id: str
    title: str
    description: str
    category: Literal["start", "quality", "security", "automation", "progress", "exploration"] = "progress"
    rarity: Literal["common", "uncommon", "rare", "epic"] = "common"
    icon_key: str = "default"
    hint: str = ""
    unlocked: bool
    unlocked_at: datetime | None
    repository_id: UUID | None
    progress_current: int | None = None
    progress_target: int | None = None
    progress_percent: float | None = None


class ProfileSummaryDTO(BaseModel):
    tracked_count: int
    analyzed_count: int
    official_health_count: int
    best_health: float | None = None
    median_health: float | None = None
    next_analysis_at: datetime | None = None
    achievements_unlocked: int = 0
    portfolio_healthy: int = 0
    portfolio_medium: int = 0
    portfolio_needs_attention: int = 0
    portfolio_no_data: int = 0


class ProfileDTO(BaseModel):
    sourcecraft: SourceCraftConnectionDTO
    repositories: list[ProfileRepositoryDTO]
    achievements: list[AchievementDTO]
    summary: ProfileSummaryDTO | None = None
