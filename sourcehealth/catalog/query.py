"""Reusable catalog filter, search, and statistics layer."""

import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import Select, case, func, or_, select
from sqlalchemy.orm import Session

from sourcehealth.catalog.topics import ALL_TOPICS
from sourcehealth.storage.models import AnalysisRun, Repository

LOG = logging.getLogger(__name__)


@dataclass
class CatalogFilters:
    q: str | None = None
    limit: int = 20
    offset: int = 0
    sort: str = "health_score"
    order: str = "desc"
    language: str | None = None
    topic: str | None = None
    origin: str | None = None
    health_min: float | None = None
    health_max: float | None = None
    health_status: str | None = None
    security_status: str | None = None
    security_min: float | None = None
    security_max: float | None = None
    cicd_status: str | None = None
    cicd_min: float | None = None
    cicd_max: float | None = None
    activity_status: str | None = None
    activity_min: float | None = None
    activity_max: float | None = None
    documentation_status: str | None = None
    documentation_min: float | None = None
    documentation_max: float | None = None
    issues_status: str | None = None
    issues_min: float | None = None
    issues_max: float | None = None
    code_health_status: str | None = None
    code_health_min: float | None = None
    code_health_max: float | None = None
    coverage_min: int | None = None
    activity_days: int | None = None

    def cache_key(self) -> str:
        data = {k: v for k, v in sorted(self.__dict__.items()) if v is not None and k not in {"limit", "offset"}}
        serialized = json.dumps(data, sort_keys=True)
        return "catalog:stats:" + hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:16]


def clean_query_term(q: str | None) -> str | None:
    if not q:
        return None
    cleaned = q.strip()
    for prefix in ("https://sourcecraft.dev/", "http://sourcecraft.dev/", "sourcecraft.dev/",
                   "https://api.sourcecraft.tech/", "http://api.sourcecraft.tech/"):
        if cleaned.lower().startswith(prefix):
            cleaned = cleaned[len(prefix):].strip("/")
    cleaned = cleaned.strip()
    return cleaned[:256] if cleaned else None


def _category_score_expr(cat: str):
    return AnalysisRun.category_scores[cat]["score"].as_float()


def _category_avail_expr(cat: str):
    return AnalysisRun.category_scores[cat]["availability"].as_string()


def build_catalog_base_query() -> Select:
    """Canonical join query ensuring latest terminal run is used."""
    return (
        select(Repository, AnalysisRun)
        .outerjoin(AnalysisRun, AnalysisRun.id == Repository.latest_analysis_id)
        .where(Repository.visibility == "public")
    )


def apply_catalog_filters(query: Select, filters: CatalogFilters) -> Select:
    """Apply all filter criteria strictly and safely."""
    clean_q = clean_query_term(filters.q)
    if clean_q:
        q_lower = clean_q.lower()
        query = query.where(
            or_(
                func.lower(Repository.repository_slug).contains(q_lower),
                func.lower(Repository.organization_slug).contains(q_lower),
                func.lower(Repository.organization_slug + "/" + Repository.repository_slug).contains(q_lower),
                func.lower(Repository.canonical_url).contains(q_lower),
                func.lower(Repository.description).contains(q_lower),
            )
        )

    if filters.language:
        query = query.where(Repository.language == filters.language)

    if filters.topic:
        # JSONB containment: topics @> '["<topic>"]'::jsonb
        query = query.where(Repository.topics.contains([filters.topic]))

    if filters.origin:
        query = query.where(Repository.origin == filters.origin)

    if filters.health_min is not None:
        query = query.where(Repository.health_score >= filters.health_min)
    if filters.health_max is not None:
        query = query.where(Repository.health_score <= filters.health_max)

    if filters.health_status:
        if filters.health_status == "available":
            query = query.where(Repository.health_score.isnot(None))
        elif filters.health_status == "no_data":
            query = query.where(Repository.health_score.is_(None))
        elif filters.health_status == "forming":
            # Either health_score is null and run is active or Soul preview available
            query = query.where(
                Repository.health_score.is_(None),
                AnalysisRun.id.isnot(None),
            )

    # Category filters
    cats = (
        ("security", filters.security_status, filters.security_min, filters.security_max),
        ("cicd", filters.cicd_status, filters.cicd_min, filters.cicd_max),
        ("activity", filters.activity_status, filters.activity_min, filters.activity_max),
        ("documentation", filters.documentation_status, filters.documentation_min, filters.documentation_max),
        ("issues", filters.issues_status, filters.issues_min, filters.issues_max),
        ("code_health", filters.code_health_status, filters.code_health_min, filters.code_health_max),
    )
    for cat_name, status, c_min, c_max in cats:
        if status == "available":
            query = query.where(
                AnalysisRun.id.isnot(None),
                _category_avail_expr(cat_name) == "available",
            )
        elif status == "no_data":
            query = query.where(
                or_(
                    AnalysisRun.id.is_(None),
                    _category_avail_expr(cat_name) == "no_data",
                )
            )

        if c_min is not None:
            query = query.where(
                AnalysisRun.id.isnot(None),
                _category_score_expr(cat_name) >= c_min,
            )
        if c_max is not None:
            query = query.where(
                AnalysisRun.id.isnot(None),
                _category_score_expr(cat_name) <= c_max,
            )

    if filters.coverage_min is not None:
        # data_coverage -> nominal_weight_percent >= coverage_min
        query = query.where(
            AnalysisRun.id.isnot(None),
            AnalysisRun.data_coverage["nominal_weight_percent"].as_integer() >= filters.coverage_min,
        )

    if filters.activity_days is not None:
        threshold = datetime.now(UTC) - timedelta(days=filters.activity_days)
        query = query.where(Repository.last_activity_at >= threshold)

    return query


def apply_catalog_sort(query: Select, filters: CatalogFilters) -> Select:
    clean_q = clean_query_term(filters.q)
    is_asc = filters.order.lower() == "asc"

    # Default sort is relevance if q is given and sort not explicitly specified
    sort_field = filters.sort
    if clean_q and (sort_field == "relevance" or not sort_field):
        q_lower = clean_q.lower()
        full_slug = func.lower(Repository.organization_slug + "/" + Repository.repository_slug)
        repo_slug = func.lower(Repository.repository_slug)
        org_slug = func.lower(Repository.organization_slug)

        relevance_rank = case(
            (full_slug == q_lower, 1),
            (repo_slug == q_lower, 2),
            (org_slug == q_lower, 3),
            (full_slug.startswith(q_lower), 4),
            (repo_slug.startswith(q_lower), 5),
            (org_slug.startswith(q_lower), 6),
            (func.lower(Repository.canonical_url).contains(q_lower), 7),
            (repo_slug.contains(q_lower), 8),
            (org_slug.contains(q_lower), 8),
            (func.lower(Repository.description).contains(q_lower), 9),
            else_=10,
        )
        return query.order_by(
            relevance_rank.asc(),
            Repository.health_score.desc().nulls_last(),
            Repository.id.asc(),
        )

    # Specific sorts
    if sort_field == "health_score":
        col = Repository.health_score
        order_col = col.asc().nulls_last() if is_asc else col.desc().nulls_last()
    elif sort_field == "likes":
        col = Repository.likes
        order_col = col.asc().nulls_last() if is_asc else col.desc().nulls_last()
    elif sort_field == "last_activity":
        col = Repository.last_activity_at
        order_col = col.asc().nulls_last() if is_asc else col.desc().nulls_last()
    elif sort_field == "name":
        col = Repository.repository_slug
        order_col = col.asc() if is_asc else col.desc()
    elif sort_field in {"security", "cicd", "activity", "documentation", "issues", "code_health"}:
        col = _category_score_expr(sort_field)
        order_col = col.asc().nulls_last() if is_asc else col.desc().nulls_last()
    elif sort_field == "coverage":
        col = AnalysisRun.data_coverage["nominal_weight_percent"].as_integer()
        order_col = col.asc().nulls_last() if is_asc else col.desc().nulls_last()
    else:
        col = Repository.health_score
        order_col = col.asc().nulls_last() if is_asc else col.desc().nulls_last()

    return query.order_by(order_col, Repository.id.asc())


def get_catalog_repositories(
    db: Session, filters: CatalogFilters
) -> tuple[list[tuple[Repository, AnalysisRun | None]], int]:
    """Return paginated repositories and total matching count."""
    base = build_catalog_base_query()
    filtered = apply_catalog_filters(base, filters)

    # Count total matching rows
    count_query = select(func.count()).select_from(filtered.subquery())
    total = db.scalar(count_query) or 0

    # Apply sort, limit, offset
    sorted_query = apply_catalog_sort(filtered, filters)
    paginated_query = sorted_query.offset(filters.offset).limit(filters.limit)

    rows = list(db.execute(paginated_query).all())
    return [(repo, run) for repo, run in rows], total


def compute_median_and_quartiles(scores: list[float]) -> tuple[float | None, float | None, float | None]:
    """Compute median, Q1 (25th percentile) and Q3 (75th percentile) on sorted scores."""
    if not scores:
        return None, None, None
    n = len(scores)
    sorted_scores = sorted(scores)

    def percentile(p: float) -> float:
        if n == 1:
            return round(sorted_scores[0], 1)
        idx = p * (n - 1)
        lower = int(idx)
        upper = lower + 1 if lower + 1 < n else lower
        weight = idx - lower
        val = sorted_scores[lower] * (1.0 - weight) + sorted_scores[upper] * weight
        return round(val, 1)

    return percentile(0.5), percentile(0.25), percentile(0.75)


def get_catalog_stats(
    db: Session, filters: CatalogFilters, redis_client: Any = None
) -> dict[str, Any]:
    """Calculate truthful catalog overview statistics and facets."""
    cache_key = filters.cache_key()
    if redis_client is not None:
        try:
            cached = redis_client.get(cache_key)
            if cached:
                return json.loads(cached)
        except Exception as e:
            LOG.warning("catalog_stats_cache_error: %s", e)

    # 1. Global public catalog total
    global_total = db.scalar(select(func.count(Repository.id)).where(Repository.visibility == "public")) or 0

    # 2. Filtered subset
    base = build_catalog_base_query()
    filtered = apply_catalog_filters(base, filters)

    # Pull rows needed for stats: health_score, latest_analysis_id, language, origin, topics
    stats_select = select(
        Repository.id,
        Repository.health_score,
        Repository.latest_analysis_id,
        Repository.language,
        Repository.origin,
        Repository.topics,
    ).select_from(filtered.subquery())

    rows = list(db.execute(stats_select).all())
    matched_total = len(rows)

    analyzed_count = 0
    health_available_count = 0
    health_forming_count = 0
    health_no_data_count = 0

    numeric_scores: list[float] = []
    language_counts: dict[str, int] = {}
    topic_counts: dict[str, int] = {t: 0 for t in ALL_TOPICS}
    origin_counts: dict[str, int] = {"native": 0, "fork": 0, "migrated": 0, "unknown": 0}

    # Histogram: 10 buckets
    # 0-9, 10-19, 20-29, 30-39, 40-49, 50-59, 60-69, 70-79, 80-89, 90-100
    histogram_counts = [0] * 10

    for row in rows:
        _id, health, latest_analysis, lang, orig, t_list = row

        if latest_analysis is not None:
            analyzed_count += 1

        if health is not None and isinstance(health, (int, float)):
            health_available_count += 1
            h_float = float(health)
            numeric_scores.append(h_float)
            # Bucket index
            if h_float >= 100.0:
                b_idx = 9
            elif h_float < 0.0:
                b_idx = 0
            else:
                b_idx = int(h_float // 10)
                if b_idx > 9:
                    b_idx = 9
            histogram_counts[b_idx] += 1
        else:
            health_no_data_count += 1
            if latest_analysis is not None:
                health_forming_count += 1

        # Language
        if lang:
            language_counts[lang] = language_counts.get(lang, 0) + 1

        # Origin
        orig_norm = orig if orig in origin_counts else "unknown"
        origin_counts[orig_norm] += 1

        # Topics
        if isinstance(t_list, list):
            for t in t_list:
                if t in topic_counts:
                    topic_counts[t] += 1

    median, q1, q3 = compute_median_and_quartiles(numeric_scores)

    # Sort languages by count desc
    sorted_languages = dict(sorted(language_counts.items(), key=lambda kv: kv[1], reverse=True))

    histogram_buckets = [
        {
            "range_label": f"{i*10}-{i*10 + 9 if i < 9 else 100}",
            "min_score": float(i * 10),
            "max_score": float(i * 10 + 9.9 if i < 9 else 100.0),
            "count": histogram_counts[i],
        }
        for i in range(10)
    ]

    result = {
        "catalog_total_public": global_total,
        "matched_total": matched_total,
        "analyzed_count": analyzed_count,
        "health_available_count": health_available_count,
        "health_forming_count": health_forming_count,
        "health_no_data_count": health_no_data_count,
        "health_median": median,
        "health_q1": q1,
        "health_q3": q3,
        "health_histogram": histogram_buckets,
        "histogram_no_data_count": health_no_data_count,
        "languages": sorted_languages,
        "topics": topic_counts,
        "origins": origin_counts,
    }

    if redis_client is not None:
        try:
            redis_client.set(cache_key, json.dumps(result), ex=30)
        except Exception as e:
            LOG.warning("catalog_stats_cache_set_error: %s", e)

    return result
