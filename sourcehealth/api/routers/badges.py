"""Bounded, database-only public Health badge."""

from fastapi import APIRouter, Request
from fastapi.responses import Response
from sqlalchemy import select

from sourcehealth.application.services import ServiceError
from sourcehealth.integrations.sourcecraft.analytics import identifier
from sourcehealth.storage.models import Repository

router = APIRouter(prefix="/api/v1/badges")


@router.get("/{organization}/{repository}.svg")
def badge(organization: str, repository: str, request: Request):
    try:
        organization, repository = identifier(organization), identifier(repository)
    except Exception:
        raise ServiceError("invalid_repository_slug", 422) from None
    with request.app.state.sessions() as db:
        row = db.scalar(select(Repository).where(Repository.organization_slug == organization,
                                                 Repository.repository_slug == repository,
                                                 Repository.visibility == "public"))
        if row is None:
            raise ServiceError("repository_not_found", 404)
        value = "no score" if row.health_score is None else str(round(row.health_score))
    width = 142 if value == "no score" else 118
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="20" role="img" '
           f'aria-label="SourceHealth: {value}"><linearGradient id="s" x2="0" y2="100%">'
           '<stop offset="0" stop-color="#bbb"/><stop offset="1" stop-color="#999"/></linearGradient>'
           f'<rect width="{width}" height="20" rx="3" fill="#555"/><rect x="88" width="{width-88}" height="20" '
           'rx="3" fill="#e53935"/><g fill="#fff" text-anchor="middle" '
           'font-family="Verdana,Arial,sans-serif" font-size="11"><text x="44" y="14">SourceHealth</text>'
           f'<text x="{(width+88)//2}" y="14">{value}</text></g></svg>')
    return Response(svg, media_type="image/svg+xml; charset=utf-8",
                    headers={"Cache-Control": "public, max-age=300"})
