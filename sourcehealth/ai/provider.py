"""Provider protocol, grounding validator, and prompt template."""

from typing import Protocol

from .contracts import AISummaryContext, AISummaryResult


class AIValidationError(ValueError):
    """Raised when an AI summary violates grounding constraints or limits."""


class AISummaryProvider(Protocol):
    def summarize(self, context: AISummaryContext) -> AISummaryResult:
        """Generate a grounded, factual summary from the supplied context."""
        ...


class DisabledAIProvider:
    """Default provider indicating AI summarization is not enabled."""

    def summarize(self, context: AISummaryContext) -> AISummaryResult:
        raise RuntimeError("ai_provider_disabled")


def validate_ai_output(context: AISummaryContext, result: AISummaryResult) -> None:
    """Validate that AI output is strictly grounded in the context and obeys limits."""
    # 1. Collect all valid evidence IDs from context
    valid_evidence_ids: set[str] = set()
    for fact in context.facts:
        valid_evidence_ids.add(fact.id)
    for cat in context.categories:
        valid_evidence_ids.add(cat.name)
        for ref in cat.evidence_refs:
            valid_evidence_ids.add(ref)

    # 2. Collect all valid recommendation IDs from context
    valid_rec_ids: set[str] = {rec.id for rec in context.recommendations}

    # 3. Check array limits
    if len(result.strengths) > 5:
        raise AIValidationError(f"Too many strengths: {len(result.strengths)} (max 5)")
    if len(result.risks) > 5:
        raise AIValidationError(f"Too many risks: {len(result.risks)} (max 5)")
    if len(result.actions) > 5:
        raise AIValidationError(f"Too many actions: {len(result.actions)} (max 5)")
    if len(result.limitations) > 5:
        raise AIValidationError(f"Too many limitations: {len(result.limitations)} (max 5)")

    if len(result.executive_summary) > 1000:
        raise AIValidationError(f"Executive summary too long: {len(result.executive_summary)} chars (max 1000)")

    # 4. Check evidence refs in statements
    for group_name, statements in (
        ("strengths", result.strengths),
        ("risks", result.risks),
        ("limitations", result.limitations),
    ):
        for stmt in statements:
            if len(stmt.text) > 500:
                raise AIValidationError(f"{group_name} statement too long: {len(stmt.text)} chars (max 500)")
            for ref in stmt.evidence_refs:
                if ref not in valid_evidence_ids:
                    raise AIValidationError(f"Unknown evidence reference '{ref}' in {group_name}")

    # 5. Check actions: must have at least one valid rec_id OR evidence_ref
    for action in result.actions:
        if len(action.text) > 500:
            raise AIValidationError(f"Action text too long: {len(action.text)} chars (max 500)")

        has_grounding = False
        for rec_id in action.recommendation_ids:
            if rec_id not in valid_rec_ids:
                raise AIValidationError(f"Unknown recommendation ID '{rec_id}' in action")
            has_grounding = True

        for ev_ref in action.evidence_refs:
            if ev_ref not in valid_evidence_ids:
                raise AIValidationError(f"Unknown evidence reference '{ev_ref}' in action")
            has_grounding = True

        if not has_grounding:
            raise AIValidationError(
                f"Action '{action.text[:50]}...' must reference at least one valid recommendation ID or evidence reference"
            )


def build_future_prompt(context: AISummaryContext) -> str:
    """Build a deterministic future prompt for YandexGPT integration."""
    return f"""You are a reporting layer for SourceHealth.
Use ONLY the supplied facts, categories, and recommendations below.
Do not infer missing facts.
Do not calculate or modify Health score.
NO_DATA means unknown.
Every risk and action MUST cite supplied IDs.
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
