"""Правила рекомендаций опираются на evidence; LLM может только объяснять их."""

from typing import Protocol

from sourcehealth.core import AnalyzerResult
from sourcehealth.core.domain import Recommendation


class RecommendationRule(Protocol):
    def recommend(self, results: dict[str, AnalyzerResult]) -> list[Recommendation]: ...


def validate_recommendations(items: list[Recommendation], results: dict[str, AnalyzerResult]) -> None:
    evidence = {e.id for result in results.values() for e in result.evidence}
    if len({item.id for item in items}) != len(items):
        raise ValueError("duplicate recommendation id")
    if any(not set(item.evidence_refs) <= evidence for item in items):
        raise ValueError("recommendation references unknown evidence")
