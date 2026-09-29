"""Strict Pydantic contracts for AI summary context and outputs."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class GroundedFact(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    kind: str
    summary: str = Field(..., max_length=500)
    value: bool | int | float | None = None
    unit: str | None = None
    evidence_refs: list[str] = Field(default_factory=list)


class GroundedCategory(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    score: float | None = Field(default=None, ge=0, le=100)
    availability: str
    explanation: str = Field(default="", max_length=500)
    evidence_refs: list[str] = Field(default_factory=list)


class GroundedRecommendation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    priority: int = Field(ge=1, le=3)
    category: str
    title: str = Field(..., max_length=200)
    description: str = Field(..., max_length=500)
    suggested_action: str = Field(..., max_length=500)
    expected_impact: str | None = Field(default=None, max_length=200)
    evidence_refs: list[str] = Field(default_factory=list)


class AISummaryContext(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["ai-context-v1"] = "ai-context-v1"
    repository: dict[str, str] = Field(..., description="Contains org and repo slugs")
    analysis_id: str
    scoring_policy_version: str
    official_health: float | None = None
    score_coverage: float | None = None
    categories: list[GroundedCategory] = Field(default_factory=list)
    facts: list[GroundedFact] = Field(default_factory=list, max_length=200)
    recommendations: list[GroundedRecommendation] = Field(default_factory=list, max_length=100)


class GroundedStatement(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(..., max_length=1500)
    evidence_refs: list[str] = Field(default_factory=list, max_length=20)


class GroundedAction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(..., pattern=r"^action-[1-9][0-9]*$", max_length=20)
    title: str = Field(..., max_length=200)
    priority: int = Field(ge=1, le=3)
    why: str = Field(..., max_length=1500)
    action: str = Field(..., max_length=1500)
    implementation_steps: list[str] = Field(default_factory=list, max_length=10)
    expected_result: str = Field(..., max_length=1000)
    recommendation_ids: list[str] = Field(default_factory=list, max_length=20)
    evidence_refs: list[str] = Field(default_factory=list, max_length=20)


class GroundedCategoryAnalysis(BaseModel):
    model_config = ConfigDict(extra="forbid")
    category: str
    score: float | None = Field(default=None, ge=0, le=100)
    availability: str
    assessment: str = Field(..., max_length=3000)
    positive_finding_ids: list[str] = Field(default_factory=list, max_length=10)
    problem_finding_ids: list[str] = Field(default_factory=list, max_length=10)
    evidence_refs: list[str] = Field(default_factory=list, max_length=20)


class GroundedCategoryFinding(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(..., pattern=r"^finding-[1-9][0-9]*$", max_length=20)
    category: str
    kind: Literal["positive", "problem"]
    text: str = Field(..., max_length=1500)
    evidence_refs: list[str] = Field(..., min_length=1, max_length=20)


class GroundedRoadmap(BaseModel):
    model_config = ConfigDict(extra="forbid")
    immediate: list[str] = Field(default_factory=list, max_length=15)
    short_term: list[str] = Field(default_factory=list, max_length=15)
    later: list[str] = Field(default_factory=list, max_length=15)


class AISummaryResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["ai-report-v2"] = "ai-report-v2"
    executive_summary: str = Field(..., max_length=4000)
    category_analysis: list[GroundedCategoryAnalysis] = Field(default_factory=list, max_length=12)
    category_findings: list[GroundedCategoryFinding] = Field(default_factory=list, max_length=40)
    strengths: list[GroundedStatement] = Field(default_factory=list, max_length=12)
    risks: list[GroundedStatement] = Field(default_factory=list, max_length=12)
    actions: list[GroundedAction] = Field(default_factory=list, max_length=15)
    roadmap: GroundedRoadmap = Field(default_factory=GroundedRoadmap)
    limitations: list[GroundedStatement] = Field(default_factory=list, max_length=10)


class LegacyGroundedAction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(..., max_length=500)
    recommendation_ids: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)


class LegacyGroundedStatement(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(..., max_length=500)
    evidence_refs: list[str] = Field(default_factory=list)


class LegacyAISummaryResult(BaseModel):
    """Frozen response contract of POST /ai-summary for existing clients."""

    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["ai-summary-v1"] = "ai-summary-v1"
    executive_summary: str = Field(..., max_length=1000)
    strengths: list[LegacyGroundedStatement] = Field(default_factory=list, max_length=5)
    risks: list[LegacyGroundedStatement] = Field(default_factory=list, max_length=5)
    actions: list[LegacyGroundedAction] = Field(default_factory=list, max_length=5)
    limitations: list[LegacyGroundedStatement] = Field(default_factory=list, max_length=5)
