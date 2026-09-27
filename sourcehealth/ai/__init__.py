"""Provider-neutral AI foundation and grounding contracts."""

from .context import build_ai_context
from .contracts import (
    AISummaryContext,
    AISummaryResult,
    GroundedAction,
    GroundedCategory,
    GroundedFact,
    GroundedRecommendation,
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
    "GroundedFact",
    "GroundedRecommendation",
    "GroundedStatement",
    "build_ai_context",
    "build_future_prompt",
    "validate_ai_output",
]
