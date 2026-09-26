"""Read-only integrity signals for a public repository."""

from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Request
from pydantic import BaseModel

from sourcehealth.integrity import IntegrityService

router = APIRouter(prefix="/api/v1/repositories")


class IntegritySignal(BaseModel):
    id: str
    severity: Literal["info", "warning"]
    title: str
    description: str
    facts: dict[str, Any]


class IntegrityResponse(BaseModel):
    repository_id: UUID
    analysis_id: UUID | None
    has_signals: bool
    signal_count: int
    warning_count: int
    info_count: int
    signals: list[IntegritySignal]


@router.get("/{repository_id}/integrity", response_model=IntegrityResponse)
def integrity(repository_id: UUID, request: Request):
    return IntegrityService(request.app.state.sessions).repository(repository_id)
