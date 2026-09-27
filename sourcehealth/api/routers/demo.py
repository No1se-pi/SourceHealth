"""Interactive demo / Health Lab endpoints.

Deterministic simulator using canonical mvp-score-v1.2 aggregation semantics.
Zero database mutations, zero queue, zero external network calls.
"""

from fastapi import APIRouter, Query, Response

from sourcehealth.api.schemas import (
    DemoPresetDTO,
    DemoSimulateRequest,
    DemoSimulateResponse,
)
from sourcehealth.scoring.mvp import DEMO_PRESETS, calculate_mvp_health

router = APIRouter(prefix="/api/v1/demo", tags=["demo"])


@router.post("/simulate", response_model=DemoSimulateResponse)
def simulate_health(body: DemoSimulateRequest) -> DemoSimulateResponse:
    """Calculate aggregate Health Score strictly using canonical mvp-score-v1.2 semantics."""
    result = calculate_mvp_health(body.scores)
    return DemoSimulateResponse(**result)


@router.get("/presets", response_model=list[DemoPresetDTO])
def get_demo_presets() -> list[DemoPresetDTO]:
    """Return standard demonstration presets for the Health Lab."""
    return [DemoPresetDTO(**p) for p in DEMO_PRESETS]


@router.get("/badge.svg")
def demo_badge(score: float | None = Query(None, description="Health score (0..100) or null for no data"),
               label: str = Query("SourceHealth", description="Badge left label")) -> Response:
    """Render dynamic demo SVG badge matching production style."""
    if score is not None:
        score_val = max(0.0, min(100.0, float(score)))
        value = str(round(score_val))
        if score_val >= 75:
            color = "#2e7d32"
        elif score_val >= 50:
            color = "#f9a825"
        else:
            color = "#e53935"
    else:
        value = "no score"
        color = "#888888"

    width = 142 if value == "no score" else 118
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="20" role="img" '
        f'aria-label="{label}: {value}">'
        f'<linearGradient id="s" x2="0" y2="100%">'
        f'<stop offset="0" stop-color="#bbb"/><stop offset="1" stop-color="#999"/>'
        f'</linearGradient>'
        f'<rect width="{width}" height="20" rx="3" fill="#555"/>'
        f'<rect x="88" width="{width-88}" height="20" rx="3" fill="{color}"/>'
        f'<g fill="#fff" text-anchor="middle" font-family="Verdana,Arial,sans-serif" font-size="11">'
        f'<text x="44" y="14">{label}</text>'
        f'<text x="{(width+88)//2}" y="14">{value}</text>'
        f'</g>'
        f'</svg>'
    )
    return Response(
        content=svg,
        media_type="image/svg+xml; charset=utf-8",
        headers={"Cache-Control": "no-cache"},
    )
