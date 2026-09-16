"""Health HTTP endpoints."""

from fastapi import APIRouter

from ..schemas import HealthResponse

router = APIRouter()



@router.get("/api/v1/health", response_model=HealthResponse)
def health():
    """Liveness only: database readiness is a separate deployment check."""
    return HealthResponse()
