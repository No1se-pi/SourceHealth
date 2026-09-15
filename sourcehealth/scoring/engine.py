"""Детерминированная граница методики. В foundation нет выдуманных весов."""

from dataclasses import asdict, dataclass, field
from math import isfinite
from typing import Protocol

from sourcehealth.core import AnalyzerResult
from sourcehealth.core.domain import Category, DataAvailability


@dataclass(frozen=True)
class CategoryScore:
    category: Category
    score: float | None = None
    availability: DataAvailability = DataAvailability.NO_DATA
    explanation: str = "Методика категории ещё не утверждена."
    evidence_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.score is not None:
            if not isfinite(self.score) or not 0 <= self.score <= 100:
                raise ValueError("score must be finite and within 0..100")
            if self.availability not in (DataAvailability.AVAILABLE, DataAvailability.NOT_CONFIGURED,
                                         DataAvailability.PARTIAL):
                raise ValueError("unavailable data cannot become a score")
            if not self.evidence_refs:
                raise ValueError("score requires evidence")


@dataclass(frozen=True)
class ScoreResult:
    policy_version: str
    categories: dict[str, CategoryScore] = field(default_factory=dict)
    health_score: float | None = None


class ScoringPolicy(Protocol):
    version: str

    def evaluate(self, results: dict[str, AnalyzerResult]) -> ScoreResult: ...


class UnconfiguredPolicy:
    """Честный baseline: данные есть, формула отсутствует, число равно null."""

    version = "unconfigured-v1"

    def evaluate(self, results: dict[str, AnalyzerResult]) -> ScoreResult:
        categories = {}
        for category in Category:
            relevant = [r for r in results.values() if r.category == category]
            availability = DataAvailability.NO_DATA
            if relevant:
                availability = relevant[0].availability
                if any(r.availability != availability for r in relevant):
                    availability = DataAvailability.PARTIAL
            categories[category.value] = CategoryScore(category, availability=availability)
        return ScoreResult(self.version, categories)


class ScoringEngine:
    def __init__(self, policy: ScoringPolicy | None = None) -> None:
        self.policy = policy or UnconfiguredPolicy()

    def score(self, results: dict[str, AnalyzerResult]) -> ScoreResult:
        """Security принимает только подтверждения из интеграции SourceCraft AppSec."""
        eligible = {name: result for name, result in results.items()
                    if result.category != Category.SECURITY or result.source == "sourcecraft_appsec"}
        outcome = self.policy.evaluate(eligible)
        if set(outcome.categories) != {c.value for c in Category} or outcome.policy_version != self.policy.version:
            raise ValueError("policy must return all categories and its version")
        evidence = {e.id: r for r in eligible.values() for e in r.evidence}
        for name, category in outcome.categories.items():
            if category.category != name:
                raise ValueError("category mismatch")
            for ref in category.evidence_refs:
                if ref not in evidence or evidence[ref].category != name:
                    raise ValueError("unknown or wrong-category evidence")
                if name == "security" and evidence[ref].source != "sourcecraft_appsec":
                    raise ValueError("security requires SourceCraft AppSec")
        if outcome.health_score is not None:
            if not isfinite(outcome.health_score) or not 0 <= outcome.health_score <= 100:
                raise ValueError("invalid health score")
            if not any(c.score is not None for c in outcome.categories.values()):
                raise ValueError("health score requires scored categories")
        return outcome

    def apply(self, report) -> None:
        outcome = self.score(report.checks)
        report.scoring_policy_version = outcome.policy_version
        report.health_score = outcome.health_score
        report.category_scores = {key: asdict(value) for key, value in outcome.categories.items()}
