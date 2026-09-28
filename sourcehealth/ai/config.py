"""Central bounded budgets for AI report depth and provider calls."""

from dataclasses import dataclass
from typing import Literal

AIReportDetail = Literal["brief", "detailed", "expert"]


@dataclass(frozen=True)
class DetailProfile:
    target_chars: int
    hard_chars: int
    max_completion_tokens: int
    timeout_seconds: float
    facts: int
    recommendations: int
    strengths: int
    risks: int
    actions: int
    limitations: int
    statement_chars: int
    summary_chars: int
    steps: int


DETAIL_PROFILES: dict[AIReportDetail, DetailProfile] = {
    "brief": DetailProfile(10_000, 10_000, 3_000, 45, 50, 20, 5, 5, 5, 5, 500, 1_000, 4),
    "detailed": DetailProfile(20_000, 20_000, 6_000, 75, 100, 50, 8, 8, 12, 8, 1_000, 2_000, 8),
    "expert": DetailProfile(50_000, 50_000, 14_000, 120, 200, 100, 12, 12, 15, 10, 1_500, 4_000, 10),
}

MAX_PROVIDER_CALLS = 4
RETRY_DELAYS_SECONDS = (0.5, 1.5, 3.0)
MAX_RETRY_AFTER_SECONDS = 5.0
