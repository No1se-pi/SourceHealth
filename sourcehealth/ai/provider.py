"""Provider protocol, grounding validator, and prompt template."""

from typing import Protocol

from .contracts import AISummaryContext, AISummaryResult


class AIValidationError(ValueError):
    """Raised when an AI summary violates grounding constraints or limits."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


class AISummaryProvider(Protocol):
    def summarize(self, context: AISummaryContext) -> AISummaryResult:
        """Generate a grounded, factual summary from the supplied context."""
        ...


class DisabledAIProvider:
    """Default provider indicating AI summarization is not enabled."""

    def summarize(self, context: AISummaryContext) -> AISummaryResult:
        raise RuntimeError("ai_provider_disabled")


def allowed_grounding_ids(context: AISummaryContext) -> tuple[set[str], set[str]]:
    """Return the exact identifiers that generated text may reference."""
    evidence_ids: set[str] = set()
    for fact in context.facts:
        evidence_ids.add(fact.id)
    for cat in context.categories:
        for ref in cat.evidence_refs:
            evidence_ids.add(ref)
    return evidence_ids, {rec.id for rec in context.recommendations}


def validate_ai_output(context: AISummaryContext, result: AISummaryResult) -> None:
    """Validate that AI output is strictly grounded in the context and obeys limits."""
    valid_evidence_ids, valid_rec_ids = allowed_grounding_ids(context)

    # 3. Check array limits
    if len(result.strengths) > 5:
        raise AIValidationError("other_grounding_failure")
    if len(result.risks) > 5:
        raise AIValidationError("other_grounding_failure")
    if len(result.actions) > 5:
        raise AIValidationError("other_grounding_failure")
    if len(result.limitations) > 5:
        raise AIValidationError("other_grounding_failure")

    if len(result.executive_summary) > 1000:
        raise AIValidationError("other_grounding_failure")

    # 4. Check evidence refs in statements
    # Strengths and risks MUST cite at least one valid evidence reference
    for group_name, statements in (
        ("strengths", result.strengths),
        ("risks", result.risks),
    ):
        for stmt in statements:
            if len(stmt.text) > 500:
                raise AIValidationError("other_grounding_failure")
            if not stmt.evidence_refs:
                raise AIValidationError("missing_statement_evidence")
            for ref in stmt.evidence_refs:
                if ref not in valid_evidence_ids:
                    raise AIValidationError("unknown_evidence_ref")

    # Limitations may remain without refs when describing missing coverage, but any cited refs must be valid
    for stmt in result.limitations:
        if len(stmt.text) > 500:
            raise AIValidationError("other_grounding_failure")
        for ref in stmt.evidence_refs:
            if ref not in valid_evidence_ids:
                raise AIValidationError("unknown_evidence_ref")

    # 5. Check actions: must have at least one valid rec_id OR evidence_ref
    for action in result.actions:
        if len(action.text) > 500:
            raise AIValidationError("other_grounding_failure")

        has_grounding = False
        for rec_id in action.recommendation_ids:
            if rec_id not in valid_rec_ids:
                raise AIValidationError("unknown_recommendation_id")
            has_grounding = True

        for ev_ref in action.evidence_refs:
            if ev_ref not in valid_evidence_ids:
                raise AIValidationError("unknown_evidence_ref")
            has_grounding = True

        if not has_grounding:
            raise AIValidationError("missing_action_grounding")


def build_future_prompt(context: AISummaryContext) -> str:
    """Build a deterministic future prompt for YandexGPT integration."""
    return f"""You are a reporting layer for SourceHealth.
Use ONLY the supplied facts, categories, and recommendations below.
Do not infer missing facts.
Do not calculate or modify Health score.
NO_DATA means unknown.
Every strength, risk, and action MUST cite supplied IDs.
Output strictly valid JSON matching schema_version 'ai-summary-v1'.

Repository: {context.repository.get('org')}/{context.repository.get('repo')}
Official Health: {context.official_health}
Score Coverage: {context.score_coverage}%

Categories:
{chr(10).join(f"- {c.name}: score={c.score}, availability={c.availability}, explanation={c.explanation}" for c in context.categories)}

Facts:
{chr(10).join(f"[{f.id}] ({f.kind}) {f.summary}" for f in context.facts[:30])}

Recommendations:
{chr(10).join(f"[{r.id}] (Priority {r.priority}) {r.title}: {r.description}" for r in context.recommendations[:10])}
"""
