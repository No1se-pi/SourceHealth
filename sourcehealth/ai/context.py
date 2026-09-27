"""AI context builder with strict privacy allowlist and size bounds."""

import re
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
    "cookie", "oauth", "password", "client_secret", "session_secret",
)


def _sanitize_string(text: str | None, max_len: int = 500) -> str:
    if not text:
        return ""
    val = str(text).strip()

    # 1. Private key blocks (entire block or marker to end)
    val = re.sub(r"(?is)-----?BEGIN[ A-Z0-9_-]*PRIVATE KEY.*?-----?END[ A-Z0-9_-]*PRIVATE KEY-----?", "[REDACTED]", val)
    val = re.sub(r"(?is)-----?BEGIN[ A-Z0-9_-]*PRIVATE KEY.*", "[REDACTED]", val)
    val = re.sub(r"(?is)\bBEGIN[ A-Z0-9_-]*PRIVATE KEY\b.*", "[REDACTED]", val)

    # 2. Bearer tokens (with optional Authorization: prefix and colon)
    val = re.sub(r"(?i)\b(?:authorization:\s*)?bearer:?\s+(?:[\"']?[^\s\"'<>;,)]+[\"']?)", "[REDACTED]", val)
    val = re.sub(r"(?i)\b(?:authorization:\s*)?bearer:?\b", "[REDACTED]", val)

    # 3. Known token prefixes (GitHub, SourceCraft)
    val = re.sub(r"\b(?:gh[pousr]|github_pat)_[A-Za-z0-9_]+", "[REDACTED]", val)
    val = re.sub(r"(?i)\b(?:sourcecraft_pat|sc_pat)_[A-Za-z0-9_]+", "[REDACTED]", val)

    # 4. Obvious key-value credentials: token=..., api_key=..., password=..., secret=..., pat=...
    val = re.sub(
        r"(?i)\b[\w.-]*(?:token|secret|password|passwd|api[_-]?key|pat)\s*[:=]\s*(?:[\"']?[^\s\"'<>;,)]+[\"']?)",
        "[REDACTED]",
        val,
    )

    # 5. Clean up any leftover disallowed markers and emails
    for pattern in ("SECRET_RAW_RESPONSE_MARKER", "sourcecraft_pat", "github_pat", "ghp_"):
        if pattern in val:
            val = val.replace(pattern, "[REDACTED]")

    val = re.sub(r"[A-Za-z0-9._%+-]+@users\.noreply\.github\.com", "[REDACTED]", val)

    return val[:max_len]


def _extract_safe_scalar(val: Any) -> bool | int | float | None:
    """Extract strictly scalar bool, int, or float with explicit boolean precedence."""
    if isinstance(val, bool):
        return val
    if isinstance(val, (int, float)) and not isinstance(val, bool):
        return val
    return None


def _is_safe_fact(fact_id: str, kind: str, summary: str) -> bool:
    # Reject facts that represent raw source, commits, credentials, or PII
    lower_id = fact_id.lower()
    lower_kind = kind.lower()
    lower_sum = summary.lower()
    blocked_keywords = (
        "source_snippet", "raw_payload", "cookie", "token", "pat",
        "author_email", "oauth", "author_name", "commit_message",
        "private_key", "secret", "password", "session_secret",
        "bearer", "ghp_", "github_pat",
    )
    if any(k in lower_id or k in lower_kind or k in lower_sum for k in blocked_keywords):
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
                            safe_val = _extract_safe_scalar(ev.get("value"))
                            raw_unit = ev.get("unit")
                            safe_unit = _sanitize_string(raw_unit, max_len=50) if raw_unit and isinstance(raw_unit, str) else None
                            grounded_facts.append(GroundedFact(
                                id=ev_id,
                                kind=kind,
                                summary=summary,
                                value=safe_val,
                                unit=safe_unit,
                                evidence_refs=[],
                            ))

            # Also add high-level summary metrics as grounded facts if facts list is small
            metrics = check_data.get("metrics", {})
            if isinstance(metrics, dict) and len(grounded_facts) < 50:
                for metric_key, metric_val in metrics.items():
                    if len(grounded_facts) >= 50:
                        break
                    # Strictly allow only scalar bool, int, float; skip dict, list, str, object, None
                    if isinstance(metric_val, bool):
                        scalar_val = metric_val
                    elif isinstance(metric_val, (int, float)) and not isinstance(metric_val, bool):
                        scalar_val = metric_val
                    else:
                        continue

                    fact_id = f"{check_name}:{metric_key}"
                    fact_summary = _sanitize_string(f"{check_name} {metric_key}: {scalar_val}", max_len=500)
                    if _is_safe_fact(fact_id, check_name, fact_summary):
                        grounded_facts.append(GroundedFact(
                            id=fact_id,
                            kind=check_name,
                            summary=fact_summary,
                            value=scalar_val,
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
