"""Allowlisted, format-neutral representation of a stored public report."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from sourcehealth.scoring.coverage import score_coverage

CATEGORY_SPECS = (
    ("documentation", "Documentation", 15),
    ("cicd", "CI/CD", 15),
    ("security", "Security", 20),
    ("activity", "Activity", 15),
    ("issues", "Issues", 15),
    ("code_health", "Code Health", 20),
)
MAX_TEXT = 2_000
MAX_ITEMS = 500


def _text(value: Any, *, limit: int = MAX_TEXT) -> str:
    if value is None:
        return ""
    text = str(value).replace("\x00", "").replace("\r", " ").replace("\n", " ")
    return text[:limit]


@dataclass(frozen=True)
class ReportCategory:
    key: str
    label: str
    weight: int
    score: float | int | None
    availability: str
    explanation: str
    evidence_refs: tuple[str, ...]


@dataclass(frozen=True)
class ReportRecommendation:
    priority: int
    title: str
    description: str
    action: str
    evidence_refs: tuple[str, ...]


@dataclass(frozen=True)
class ReportEvidence:
    identifier: str
    summary: str
    source: str
    reference: str
    url: str | None


@dataclass(frozen=True)
class ReportCheck:
    name: str
    availability: str
    source: str
    finding_count: int
    evidence: tuple[ReportEvidence, ...]


@dataclass(frozen=True)
class ReportDocument:
    """One semantic source shared by Markdown, PDF and DOCX renderers."""

    public_report: dict[str, Any]
    analysis_id: str | None
    status: str | None
    repository: str
    canonical_url: str
    completed_at: str
    scoring_policy_version: str
    health_score: float | int | None
    coverage_percent: int | float | None
    categories: tuple[ReportCategory, ...]
    recommendations: tuple[ReportRecommendation, ...]
    checks: tuple[ReportCheck, ...]

    @classmethod
    def from_report(cls, report: Any, *, analysis_id: Any = None, status: str | None = None) -> ReportDocument:
        if hasattr(report, "to_public_dict"):
            report = report.to_public_dict()
        if not isinstance(report, dict) or report.get("schema_version") != "3.0":
            raise ValueError("Report export requires public report schema 3.0")
        repository = report.get("repository")
        if not isinstance(repository, dict):
            raise ValueError("Report export requires repository identity")
        organization = _text(repository.get("organization_slug"), limit=128)
        slug = _text(repository.get("repository_slug"), limit=128)
        canonical_url = _text(repository.get("canonical_url"), limit=512)
        if not organization or not slug or not canonical_url:
            raise ValueError("Report export requires complete repository identity")

        raw_categories = report.get("category_scores") or {}
        if not isinstance(raw_categories, dict):
            raise ValueError("Report categories must be an object")
        categories = []
        for key, label, weight in CATEGORY_SPECS:
            raw = raw_categories.get(key) or {}
            if not isinstance(raw, dict):
                raise ValueError(f"Report category {key} must be an object")
            score = raw.get("score")
            if score is not None and (type(score) not in (int, float) or not 0 <= score <= 100):
                raise ValueError(f"Report category {key} has invalid score")
            categories.append(ReportCategory(
                key=key,
                label=label,
                weight=weight,
                score=score,
                availability=_text(raw.get("availability") or "no_data", limit=64),
                explanation=_text(raw.get("explanation")),
                evidence_refs=tuple(_text(item, limit=256) for item in (raw.get("evidence_refs") or [])[:MAX_ITEMS]),
            ))

        recommendations = []
        raw_recommendations = report.get("recommendations") or []
        if not isinstance(raw_recommendations, list):
            raise ValueError("Report recommendations must be an array")
        for item in raw_recommendations[:MAX_ITEMS]:
            if not isinstance(item, dict):
                raise ValueError("Report recommendation must be an object")
            priority = item.get("priority")
            if type(priority) is not int:
                raise ValueError("Report recommendation priority must be an integer")
            recommendations.append(ReportRecommendation(
                priority=priority,
                title=_text(item.get("title")),
                description=_text(item.get("description")),
                action=_text(item.get("suggested_action")),
                evidence_refs=tuple(_text(ref, limit=256) for ref in (item.get("evidence_refs") or [])[:MAX_ITEMS]),
            ))

        checks = []
        raw_checks = report.get("checks") or {}
        if not isinstance(raw_checks, dict):
            raise ValueError("Report checks must be an object")
        for name, item in sorted(raw_checks.items())[:MAX_ITEMS]:
            if not isinstance(item, dict):
                raise ValueError("Report check must be an object")
            evidence_items = []
            for evidence in (item.get("evidence") or [])[:MAX_ITEMS]:
                if not isinstance(evidence, dict):
                    continue
                url = _text(evidence.get("url"), limit=1_000) or None
                if url and not url.startswith(("https://sourcecraft.dev/", "https://sourcecraft.tech/")):
                    url = None
                evidence_items.append(ReportEvidence(
                    identifier=_text(evidence.get("id"), limit=256),
                    summary=_text(evidence.get("summary")),
                    source=_text(evidence.get("source"), limit=256),
                    reference=_text(evidence.get("reference"), limit=1_000),
                    url=url,
                ))
            findings = item.get("findings") or []
            checks.append(ReportCheck(
                name=_text(name, limit=256),
                availability=_text(item.get("availability") or "no_data", limit=64),
                source=_text(item.get("source"), limit=256),
                finding_count=min(len(findings), MAX_ITEMS) if isinstance(findings, list) else 0,
                evidence=tuple(evidence_items),
            ))

        policy = _text(report.get("scoring_policy_version") or "unconfigured-v1", limit=128)
        coverage = score_coverage(policy, raw_categories)
        health_score = report.get("health_score")
        if health_score is not None and (type(health_score) not in (int, float) or not 0 <= health_score <= 100):
            raise ValueError("Report health score is invalid")
        # Keep only the established public report keys. Renderers never see arbitrary internal fields.
        public_report = {key: deepcopy(report[key]) for key in (
            "schema_version", "repository", "completed_at", "scoring_policy_version", "health_score",
            "category_scores", "recommendations", "checks",
        ) if key in report}
        return cls(
            public_report=public_report,
            analysis_id=_text(analysis_id, limit=64) or None,
            status=_text(status, limit=32) or None,
            repository=f"{organization}/{slug}",
            canonical_url=canonical_url,
            completed_at=_text(report.get("completed_at"), limit=64),
            scoring_policy_version=policy,
            health_score=health_score,
            coverage_percent=coverage["nominal_weight_percent"] if coverage else None,
            categories=tuple(categories),
            recommendations=tuple(sorted(recommendations, key=lambda item: (item.priority, item.title))),
            checks=tuple(checks),
        )
