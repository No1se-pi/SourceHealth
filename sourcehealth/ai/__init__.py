"""Provider-neutral AI foundation and grounding contracts."""

from .context import build_ai_context
from .contracts import (
    AISummaryContext,
    AISummaryResult,
    GroundedAction,
    GroundedCategory,
    GroundedCategoryAnalysis,
    GroundedFact,
    GroundedRecommendation,
    GroundedRoadmap,
    GroundedStatement,
)
from .provider import AISummaryProvider, DisabledAIProvider, build_future_prompt, validate_ai_output

__all__ = [
    "AISummaryContext",
    "AISummaryProvider",
    "AISummaryResult",
    "DisabledAIProvider",
    "GroundedAction",
    "GroundedCategory",
    "GroundedCategoryAnalysis",
    "GroundedFact",
    "GroundedRecommendation",
    "GroundedRoadmap",
    "GroundedStatement",
    "build_ai_context",
    "build_future_prompt",
    "validate_ai_output",
]
