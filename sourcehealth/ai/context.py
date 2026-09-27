"""AI context builder with strict privacy allowlist and size bounds."""

from typing import Any

from .contracts import (
    AISummaryContext,
    GroundedCategory,
    GroundedFact,
    GroundedRecommendation,
)

DISALLOWED_PATTERNS = (
    "ghp_", "github_pat", "sourcecraft_pat", "Bearer ", "SECRET_RAW_RESPONSE_MARKER",
    "BEGIN PRIVATE KEY", "BEGIN RSA PRIVATE KEY", "BEGIN OPENSSH PRIVATE KEY",
    "@users.noreply.github.com",
)


def _sanitize_string(text: str | None, max_len: int = 500) -> str:
    if not text:
        return ""
    val = str(text).strip()
    for pattern in DISALLOWED_PATTERNS:
        if pattern in val:
            val = val.replace(pattern, "[REDACTED]")
    return val[:max_len]


def _is_safe_fact(fact_id: str, kind: str, summary: str) -> bool:
    # Reject facts that represent raw source, commits, or credentials
    lower_id = fact_id.lower()
    lower_kind = kind.lower()
    if any(k in lower_id or k in lower_kind for k in ("source_snippet", "raw_payload", "cookie", "token", "pat", "author_email")):
        return False
    return True


def build_ai_context(report: Any) -> AISummaryContext:
    """Build a strictly grounded and sanitized AI context from an analysis report or dictionary."""
    if isinstance(report, dict):
        data = report
    elif hasattr(report, "model_dump"):
        data = report.model_dump()
    elif hasattr(report, "__dict__"):
        data = report.__dict__
    else:
        raise ValueError("Unsupported report type for AI context generation")

    # 1. Repository slugs
    org_slug = data.get("organization_slug") or data.get("repository", {}).get("organization_slug", "unknown-org")
    repo_slug = data.get("repository_slug") or data.get("repository", {}).get("repository_slug", "unknown-repo")

    # 2. Top-level metadata
    analysis_id = str(data.get("id") or data.get("analysis_id", ""))
    policy_version = str(data.get("scoring_policy_version", "mvp-score-v1.2"))
    official_health = data.get("health_score")
    if official_health is not None:
        official_health = float(official_health)

    score_coverage_val = data.get("score_coverage")
    if isinstance(score_coverage_val, dict):
        score_coverage = score_coverage_val.get("nominal_weight_percent")
    elif isinstance(score_coverage_val, (int, float)):
        score_coverage = float(score_coverage_val)
    else:
        score_coverage = None

    # 3. Categories
    grounded_categories: list[GroundedCategory] = []
    raw_categories = data.get("category_scores", {})
    if isinstance(raw_categories, dict):
        for cat_name, cat_data in raw_categories.items():
            if isinstance(cat_data, dict):
                score = cat_data.get("score")
                grounded_categories.append(GroundedCategory(
                    name=str(cat_name),
                    score=float(score) if isinstance(score, (int, float)) else None,
                    availability=str(cat_data.get("availability", "no_data")),
                    explanation=_sanitize_string(cat_data.get("explanation", ""), max_len=500),
                    evidence_refs=[str(ref) for ref in cat_data.get("evidence_refs", [])[:10]],
                ))

    # 4. Recommendations (capped at 20)
    grounded_recommendations: list[GroundedRecommendation] = []
    raw_recommendations = data.get("recommendations", [])
    if isinstance(raw_recommendations, list):
        for rec in raw_recommendations[:20]:
            if isinstance(rec, dict):
                grounded_recommendations.append(GroundedRecommendation(
                    id=str(rec.get("id", "")),
                    priority=int(rec.get("priority", 2)),
                    category=str(rec.get("category", "")),
                    title=_sanitize_string(rec.get("title", ""), max_len=200),
                    description=_sanitize_string(rec.get("description", ""), max_len=500),
                    suggested_action=_sanitize_string(rec.get("suggested_action", ""), max_len=500),
                    expected_impact=_sanitize_string(rec.get("expected_impact"), max_len=200) if rec.get("expected_impact") else None,
                    evidence_refs=[str(ref) for ref in rec.get("evidence_refs", [])[:10]],
                ))

    # 5. Safe facts extracted from checks (capped at 50)
    grounded_facts: list[GroundedFact] = []
    checks = data.get("checks", {})
    if isinstance(checks, dict):
        for check_name, check_data in checks.items():
            if not isinstance(check_data, dict):
                continue
            # Extract safe evidence list if available
            ev_list = check_data.get("evidence", [])
            if isinstance(ev_list, list):
                for ev in ev_list:
                    if len(grounded_facts) >= 50:
                        break
                    if isinstance(ev, dict):
                        ev_id = str(ev.get("id", ""))
                        kind = str(ev.get("kind", check_name))
                        summary = _sanitize_string(ev.get("summary", ""), max_len=500)
                        if _is_safe_fact(ev_id, kind, summary):
                            grounded_facts.append(GroundedFact(
                                id=ev_id,
                                kind=kind,
                                summary=summary,
                                value=ev.get("value"),
                                unit=ev.get("unit"),
                                evidence_refs=[],
                            ))

            # Also add high-level summary metrics as grounded facts if facts list is small
            metrics = check_data.get("metrics", {})
            if isinstance(metrics, dict) and len(grounded_facts) < 50:
                for metric_key, metric_val in metrics.items():
                    if len(grounded_facts) >= 50:
                        break
                    if isinstance(metric_val, (int, float, bool, str)) and not isinstance(metric_val, str) or len(str(metric_val)) < 100:
                        fact_id = f"{check_name}:{metric_key}"
                        if _is_safe_fact(fact_id, check_name, str(metric_val)):
                            grounded_facts.append(GroundedFact(
                                id=fact_id,
                                kind=check_name,
                                summary=f"{check_name} {metric_key}: {metric_val}",
                                value=metric_val,
                                unit=None,
                                evidence_refs=[],
                            ))

    return AISummaryContext(
        schema_version="ai-context-v1",
        repository={"org": org_slug, "repo": repo_slug},
        analysis_id=analysis_id,
        scoring_policy_version=policy_version,
        official_health=official_health,
        score_coverage=score_coverage,
        categories=grounded_categories,
        facts=grounded_facts[:50],
        recommendations=grounded_recommendations[:20],
    )
