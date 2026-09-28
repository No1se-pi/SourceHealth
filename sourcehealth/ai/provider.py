"""Provider protocol and strict grounding validator for AI reports."""

from typing import Protocol

from .config import DETAIL_PROFILES, AIReportDetail
from .contracts import AISummaryContext, AISummaryResult, GroundedStatement


class AIValidationError(ValueError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


class AISummaryProvider(Protocol):
    def summarize(self, context: AISummaryContext, mode: str,
                  detail: AIReportDetail = "brief") -> AISummaryResult: ...


class DisabledAIProvider:
    def summarize(self, context: AISummaryContext, mode: str = "flash",
                  detail: AIReportDetail = "brief") -> AISummaryResult:
        raise RuntimeError("ai_provider_disabled")


def allowed_grounding_ids(context: AISummaryContext) -> tuple[set[str], set[str]]:
    evidence_ids = {fact.id for fact in context.facts}
    for category in context.categories:
        if category.availability not in {"no_data", "source_unavailable"}:
            evidence_ids.update(category.evidence_refs)
    return evidence_ids, {recommendation.id for recommendation in context.recommendations}


def _validate_statements(statements: list[GroundedStatement], valid_evidence_ids: set[str], *, optional=False):
    for statement in statements:
        if not optional and not statement.evidence_refs:
            raise AIValidationError("missing_statement_evidence")
        if any(ref not in valid_evidence_ids for ref in statement.evidence_refs):
            raise AIValidationError("unknown_evidence_ref")


def validate_ai_output(context: AISummaryContext, result: AISummaryResult,
                       detail: AIReportDetail = "brief") -> None:
    """Reject invented facts, score mutation, unsupported actions, and depth overflow."""
    profile = DETAIL_PROFILES[detail]
    valid_evidence_ids, valid_rec_ids = allowed_grounding_ids(context)
    if (len(result.executive_summary) > profile.summary_chars
            or len(result.strengths) > profile.strengths
            or len(result.risks) > profile.risks
            or len(result.actions) > profile.actions
            or len(result.limitations) > profile.limitations):
        raise AIValidationError("ai_output_limit_exceeded")
    _validate_statements(result.strengths, valid_evidence_ids)
    _validate_statements(result.risks, valid_evidence_ids)
    _validate_statements(result.limitations, valid_evidence_ids, optional=True)

    source_categories = {category.name: category for category in context.categories}
    numeric_names = {category.name for category in context.categories if category.score is not None}
    seen_categories: set[str] = set()
    for category in result.category_analysis:
        source = source_categories.get(category.category)
        if source is None or category.category in seen_categories:
            raise AIValidationError("unknown_category")
        seen_categories.add(category.category)
        if category.score != source.score or category.availability != source.availability:
            raise AIValidationError("category_value_mutated")
        if source.availability in {"no_data", "source_unavailable"}:
            if category.positive_findings or category.problems or category.evidence_refs:
                raise AIValidationError("unavailable_category_assertion")
        else:
            if category.evidence_refs != source.evidence_refs:
                raise AIValidationError("category_evidence_mutated")
            if (category.positive_findings or category.problems) and not category.evidence_refs:
                raise AIValidationError("missing_statement_evidence")
    if detail in {"detailed", "expert"} and not numeric_names.issubset(seen_categories):
        raise AIValidationError("missing_category_analysis")

    action_ids: set[str] = set()
    for action in result.actions:
        if action.id in action_ids:
            raise AIValidationError("duplicate_action_id")
        action_ids.add(action.id)
        if any(rec_id not in valid_rec_ids for rec_id in action.recommendation_ids):
            raise AIValidationError("unknown_recommendation_id")
        if any(ref not in valid_evidence_ids for ref in action.evidence_refs):
            raise AIValidationError("unknown_evidence_ref")
        if not action.recommendation_ids and not action.evidence_refs:
            raise AIValidationError("missing_action_grounding")
        if len(action.implementation_steps) > profile.steps:
            raise AIValidationError("ai_output_limit_exceeded")

    roadmap_ids = result.roadmap.immediate + result.roadmap.short_term + result.roadmap.later
    if len(roadmap_ids) != len(set(roadmap_ids)) or any(action_id not in action_ids for action_id in roadmap_ids):
        raise AIValidationError("ungrounded_roadmap_item")


def build_future_prompt(context: AISummaryContext) -> str:
    """Compatibility helper for consumers of the provider-neutral foundation."""
    return f"""You are a reporting layer for SourceHealth.
NO_DATA means unknown. Do not calculate or modify Health score.
Repository: {context.repository.get('org')}/{context.repository.get('repo')}
Official Health: {context.official_health}
Context: {context.model_dump_json()}"""
