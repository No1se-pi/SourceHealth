"""Catalog statistics and overview endpoints."""

from fastapi import APIRouter, Query, Request

from sourcehealth.catalog.query import CatalogFilters, get_catalog_stats

from ..schemas import CatalogStatsDTO

router = APIRouter(prefix="/api/v1/catalog")


@router.get("/stats", response_model=CatalogStatsDTO)
def catalog_stats(
    request: Request,
    q: str | None = Query(None, max_length=256),
    language: str | None = Query(None, max_length=64),
    topic: str | None = Query(None, max_length=64),
    origin: str | None = Query(None, pattern="^(native|fork|migrated|unknown)$"),
    health_min: float | None = Query(None, ge=0, le=100),
    health_max: float | None = Query(None, ge=0, le=100),
    health_status: str | None = Query(None, pattern="^(available|no_data|all)$"),
    security_status: str | None = Query(None, pattern="^(available|no_data|any)$"),
    security_min: float | None = Query(None, ge=0, le=100),
    security_max: float | None = Query(None, ge=0, le=100),
    cicd_status: str | None = Query(None, pattern="^(available|no_data|any)$"),
    cicd_min: float | None = Query(None, ge=0, le=100),
    cicd_max: float | None = Query(None, ge=0, le=100),
    activity_status: str | None = Query(None, pattern="^(available|no_data|any)$"),
    activity_min: float | None = Query(None, ge=0, le=100),
    activity_max: float | None = Query(None, ge=0, le=100),
    documentation_status: str | None = Query(None, pattern="^(available|no_data|any)$"),
    documentation_min: float | None = Query(None, ge=0, le=100),
    documentation_max: float | None = Query(None, ge=0, le=100),
    issues_status: str | None = Query(None, pattern="^(available|no_data|any)$"),
    issues_min: float | None = Query(None, ge=0, le=100),
    issues_max: float | None = Query(None, ge=0, le=100),
    code_health_status: str | None = Query(None, pattern="^(available|no_data|any)$"),
    code_health_min: float | None = Query(None, ge=0, le=100),
    code_health_max: float | None = Query(None, ge=0, le=100),
    coverage_min: int | None = Query(None, ge=0, le=100),
    activity_days: int | None = Query(None, ge=1, le=3650),
):
    filters = CatalogFilters(
        q=q,
        language=language,
        topic=topic,
        origin=origin,
        health_min=health_min,
        health_max=health_max,
        health_status=health_status,
        security_status=security_status,
        security_min=security_min,
        security_max=security_max,
        cicd_status=cicd_status,
        cicd_min=cicd_min,
        cicd_max=cicd_max,
        activity_status=activity_status,
        activity_min=activity_min,
        activity_max=activity_max,
        documentation_status=documentation_status,
        documentation_min=documentation_min,
        documentation_max=documentation_max,
        issues_status=issues_status,
        issues_min=issues_min,
        issues_max=issues_max,
        code_health_status=code_health_status,
        code_health_min=code_health_min,
        code_health_max=code_health_max,
        coverage_min=coverage_min,
        activity_days=activity_days,
    )
    redis_client = getattr(request.app.state, "redis", None)
    with request.app.state.sessions() as db:
        stats_data = get_catalog_stats(db, filters, redis_client=redis_client)
        return CatalogStatsDTO.model_validate(stats_data)
