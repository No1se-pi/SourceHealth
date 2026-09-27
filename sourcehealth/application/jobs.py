"""Durable queued rows → RQ. PostgreSQL advisory lock fences duplicate deliveries."""

import logging
from dataclasses import asdict, replace
from datetime import UTC, datetime
from time import perf_counter
from uuid import UUID

from redis import Redis
from redis.exceptions import LockError
from rq import Queue
from rq.exceptions import DuplicateJobError, NoSuchJobError
from rq.job import Job
from sqlalchemy import select, text

from sourcehealth.auth.service import AuthService
from sourcehealth.auth.sourcecraft import SourceCraftConnection
from sourcehealth.core import AnalysisContext
from sourcehealth.core.domain import ACTIVE_STATUSES, DataAvailability
from sourcehealth.integrations.sourcecraft.analytics import (
    CICollector,
    ContributorsCollector,
    IssuesCollector,
    PullRequestsCollector,
    ReleasesCollector,
)
from sourcehealth.integrations.sourcecraft.appsec import SourceCraftAppSecClient
from sourcehealth.integrations.sourcecraft.client import SourceCraftClient
from sourcehealth.integrations.sourcecraft.collectors import AppSecCollector, CollectedFacts, RepositoryCollector
from sourcehealth.recommendations.mvp import recommend
from sourcehealth.runtime import configured_runtime
from sourcehealth.scoring.engine import ScoringEngine
from sourcehealth.scoring.mvp import MVPPolicy
from sourcehealth.settings import Settings
from sourcehealth.storage.database import create_database
from sourcehealth.storage.models import AnalysisRun, Repository

from .cache import JsonCache, platform_cache_key
from .connections import create_redis
from .pipeline import analyze_context
from .services import AnalysisService, repository_ref

logger = logging.getLogger(__name__)


def _timed_collection(stage, collect, timings):
    started = perf_counter()
    result = collect()
    timings[f"{stage}_ms"] = round((perf_counter() - started) * 1000)
    logger.info("analysis_stage_finished", extra={"component": "worker", "event": "analysis_stage_finished",
                "analyzer": stage, "availability": result.availability.value,
                "complete": result.facts.get("complete") if isinstance(result.facts, dict) else None,
                "sourcecraft_error_code": result.error, "duration_ms": timings[f"{stage}_ms"]})
    return result


def queue_name(profile: str) -> str:
    """Очередь определяется сохранённым профилем, не environment dispatcher."""
    return {"platform-v1": "analysis", "code-v1": "analysis-code", "mvp-v1": "analysis-code"}[profile]


def dispatch_pending(sessions, redis: Redis, timeout: int = 600) -> int:
    """Коммит queued уже существует. Повторная доставка безопасна для execute_analysis."""
    with sessions() as db:
        rows = list(db.execute(select(AnalysisRun.id, AnalysisRun.profile).where(AnalysisRun.status == "queued")
                               .order_by(AnalysisRun.queued_at).limit(100)))
    count = 0
    for run_id, profile in rows:
        queue = Queue(queue_name(profile), connection=redis)
        job_id = str(run_id)
        lock = redis.lock(f"sourcehealth:dispatch:{job_id}", timeout=30, blocking_timeout=0)
        if not lock.acquire(blocking=False):
            continue
        try:
            try:
                job = Job.fetch(job_id, connection=redis)
                status = job.get_status(refresh=True)
                if status in {"started", "deferred", "scheduled"}:
                    continue
                if status == "queued" and job_id in queue.job_ids:
                    continue
                # A worker may stop after dequeue and before started status is saved.
                # The DB row remains the outbox; replace that orphaned RQ object.
                job.delete()
            except NoSuchJobError:
                pass
            try:
                queue.enqueue(execute_analysis, job_id, job_id=job_id, job_timeout=timeout,
                              result_ttl=0, failure_ttl=86400, unique=True)
                count += 1
            except DuplicateJobError:
                pass
        finally:
            try:
                lock.release()
            except LockError:
                pass
    return count


def lock_key(analysis_id: UUID) -> int:
    """Signed 64-bit key, stable across Python processes and restarts."""
    return int.from_bytes(analysis_id.bytes[:8], byteorder="big", signed=True)


def collect_platform(repository, settings, redis, *, user_pat=None):
    """Один реальный vertical slice: API metadata + честная AppSec availability."""
    timings = {}
    metadata_started = perf_counter()
    cache = JsonCache(redis)
    key = platform_cache_key(repository.id, "repository_metadata-v2")
    # A user-authorized run uses one caller identity and never consumes a shared platform cache.
    cached = None if user_pat else cache.get(key)
    metadata = None
    if cached:
        try:
            metadata = CollectedFacts(**{**cached, "availability": DataAvailability(cached["availability"])})
        except (ValueError, TypeError, KeyError):
            pass
    if metadata is None:
        with SourceCraftClient(pat=user_pat or (settings.sourcecraft_pat.get_secret_value() if settings.sourcecraft_pat else None),
                               timeout=settings.sourcecraft_timeout, max_pages=settings.sourcecraft_max_pages) as client:
            metadata = _timed_collection(
                "repository_metadata", lambda: RepositoryCollector(client).collect(repository), timings)
        if metadata.availability == DataAvailability.AVAILABLE and not user_pat:
            cache.put(key, asdict(metadata), settings.platform_cache_ttl)
    elif "repository_metadata_ms" not in timings:
        timings["repository_metadata_ms"] = round((perf_counter() - metadata_started) * 1000)
        logger.info("analysis_stage_finished", extra={
            "component": "worker", "event": "analysis_stage_finished", "analyzer": "repository_metadata",
            "availability": metadata.availability.value, "complete": None,
            "sourcecraft_error_code": metadata.error, "duration_ms": timings["repository_metadata_ms"],
        })
    if user_pat and metadata.availability == DataAvailability.AVAILABLE:
        with SourceCraftAppSecClient(pat=user_pat, timeout=settings.sourcecraft_timeout,
                                     max_pages=min(settings.sourcecraft_max_pages, 20)) as client:
            appsec = _timed_collection(
                "appsec", lambda: AppSecCollector(client).collect(repository, metadata.facts.get("id")), timings)
    else:
        appsec = _timed_collection(
            "appsec", lambda: AppSecCollector(None).collect(repository, metadata.facts.get("id")), timings)
    return AnalysisContext(repository=repository,
                           metadata={"collection": {"repository_metadata": {"collected_at": metadata.collected_at,
                                                                              "schema_version": metadata.schema_version,
                                                                              "error": metadata.error},
                                                    "appsec": {"collected_at": appsec.collected_at,
                                                               "schema_version": appsec.schema_version,
                                                               "error": appsec.error}},
                                     "stage_timings_ms": timings},
                           sourcecraft_facts={"repository_metadata": metadata.facts, "appsec": appsec.facts},
                           collection_statuses={"repository_metadata": metadata.availability,
                                                "appsec": appsec.availability})


def execute_analysis(analysis_id: str) -> None:
    settings = Settings()
    engine, sessions = create_database(settings.database_url.get_secret_value())
    redis = create_redis(settings.redis_url.get_secret_value())
    service = AnalysisService(sessions, settings)
    credentials = SourceCraftConnection(AuthService(settings, redis, sessions))
    run_id = UUID(analysis_id)
    total_started = perf_counter()
    timings = {}
    # Session advisory lock survives short database transactions but not process death.
    # Redis queue/lock loss therefore cannot start a second heavy execution.
    try:
        with engine.connect() as guard:
            acquired = guard.scalar(text("SELECT pg_try_advisory_lock(:key)"), {"key": lock_key(run_id)})
            guard.commit()
            if not acquired:
                return
            try:
                with sessions() as db:
                    run = db.get(AnalysisRun, run_id)
                    if run is None or run.status != "queued":
                        return
                    repository = repository_ref(db.get(Repository, run.repository_id))
                    profile = run.profile
                service.transition(run_id, "collecting")
                logger.info("worker_job_started", extra={
                    "analysis_id": analysis_id, "repository_id": repository.id,
                    "profile": profile, "queue": queue_name(profile),
                    "component": "worker", "event": "worker_job_started",
                })
                user_pat = credentials.analysis_credential(run_id)
                context = (collect_platform(repository, settings, redis, user_pat=user_pat) if user_pat
                           else collect_platform(repository, settings, redis))
                if context.collection_statuses.get("repository_metadata") == DataAvailability.AVAILABLE:
                    with sessions.begin() as db:
                        row = db.get(Repository, run.repository_id)
                        metadata = context.sourcecraft_facts["repository_metadata"]
                        if metadata.get("likes") is not None:
                            row.likes = metadata["likes"]
                        if metadata.get("language") is not None:
                            row.language = metadata["language"]
                elif context.metadata.get("collection", {}).get("repository_metadata", {}).get("error") in {
                        "public_repository_required", "not_found", "access_denied"}:
                    with sessions.begin() as db:
                        db.get(Repository, run.repository_id, with_for_update=True).visibility = "unknown"
                if profile == "mvp-v1":
                    context = collect_mvp(context, settings, pat=user_pat)
                service.transition(run_id, "analyzing")
                timings.update(context.metadata.get("stage_timings_ms", {}))
                report = analyze_context(context, include_code=profile in {"code-v1", "mvp-v1"}, with_mvp=profile == "mvp-v1",
                                         runtime=configured_runtime(settings, with_mvp=True) if profile == "mvp-v1" else
                                         configured_runtime(settings) if profile == "code-v1" else None,
                                         timings=timings)
                service.transition(run_id, "scoring")
                scoring_started = perf_counter()
                ScoringEngine(MVPPolicy() if profile == "mvp-v1" else None).apply(report)
                timings["scoring_ms"] = round((perf_counter() - scoring_started) * 1000)
                for check in report.checks.values():
                    logger.info("analysis_check_result", extra={
                        "analysis_id": analysis_id, "component": "worker", "event": "analysis_check_result",
                        "analyzer": check.analyzer, "availability": check.availability.value,
                        "complete": check.metrics.get("complete") if isinstance(check.metrics, dict) else None,
                        "sourcecraft_error_code": check.error,
                    })
                if profile == "mvp-v1":
                    report.recommendations = recommend(report.checks)
                service.finish(run_id, report)
                timings["total_ms"] = round((perf_counter() - total_started) * 1000)
                logger.info("analysis_finished", extra={"analysis_id": analysis_id, "repository_id": repository.id,
                                                        "component": "worker", "event": "analysis_finished", **timings})
                logger.info("worker_job_finished", extra={
                    "analysis_id": analysis_id, "repository_id": repository.id,
                    "profile": profile, "queue": queue_name(profile),
                    "duration_ms": timings["total_ms"],
                    "status": "completed" if report.complete else "partial",
                    "component": "worker", "event": "worker_job_finished",
                })
            except Exception:
                # Neither exception text nor source responses are suitable for RQ failure storage/logs.
                with sessions() as db:
                    row = db.get(AnalysisRun, run_id)
                    active = row is not None and row.status in ACTIVE_STATUSES
                if active:
                    service.transition(run_id, "failed", error_code="analysis_failed")
                total_duration = round((perf_counter() - total_started) * 1000)
                logger.error("analysis_failed", extra={"analysis_id": analysis_id, "component": "worker",
                                                        "event": "analysis_failed", **timings,
                                                        "total_ms": total_duration})
                logger.error("worker_job_finished", extra={
                    "analysis_id": analysis_id,
                    "repository_id": getattr(repository, "id", None) if "repository" in locals() and repository else None,
                    "profile": profile if "profile" in locals() else None,
                    "queue": queue_name(profile) if "profile" in locals() else None,
                    "duration_ms": total_duration,
                    "status": "failed",
                    "component": "worker",
                    "event": "worker_job_finished",
                })
            finally:
                credentials.delete_analysis_credential(run_id)
                guard.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": lock_key(run_id)})
                guard.commit()
    finally:
        redis.close()
        engine.dispose()


def collect_mvp(context, settings, *, client=None, pat=None):
    """API facts обновляются независимо от SHA; общий time budget ограничивает fan-out."""
    from contextlib import nullcontext

    manager = nullcontext(client) if client is not None else SourceCraftClient(
        pat=pat or (settings.sourcecraft_pat.get_secret_value() if settings.sourcecraft_pat else None),
        timeout=min(settings.sourcecraft_timeout, 10), max_pages=min(settings.sourcecraft_max_pages, 5), deadline_seconds=120)
    facts, statuses = dict(context.sourcecraft_facts), dict(context.collection_statuses)
    collection = dict(context.metadata.get("collection", {}))
    timings = dict(context.metadata.get("stage_timings_ms", {}))
    with manager as client:
        for cls in (IssuesCollector, CICollector, PullRequestsCollector, ContributorsCollector, ReleasesCollector):
            collected = _timed_collection(cls.name, lambda cls=cls: cls(client).collect(context.repository), timings)
            facts[cls.name], statuses[cls.name] = collected.facts, collected.availability
            collection[cls.name] = {"collected_at": collected.collected_at, "schema_version": collected.schema_version,
                                    "error": collected.error}
    return replace(context, sourcecraft_facts=facts, collection_statuses=statuses,
                   metadata={**context.metadata, "collection": collection, "stage_timings_ms": timings})


def recover_abandoned(engine, sessions, settings) -> int:
    """Mark expired runs failed only after proving no worker still holds the lock."""
    with sessions() as db:
        ids = list(db.scalars(select(AnalysisRun.id).where(AnalysisRun.status.in_(ACTIVE_STATUSES[1:]),
                                                           AnalysisRun.deadline_at < datetime.now(UTC))))
    count = 0
    for run_id in ids:
        with engine.connect() as guard:
            if not guard.scalar(text("SELECT pg_try_advisory_lock(:key)"), {"key": lock_key(run_id)}):
                continue
            guard.commit()
            try:
                with sessions() as db:
                    run = db.get(AnalysisRun, run_id)
                    active = run is not None and run.status in ACTIVE_STATUSES[1:]
                if active:
                    AnalysisService(sessions, settings).transition(run_id, "failed", error_code="worker_interrupted")
                    count += 1
            finally:
                guard.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": lock_key(run_id)})
                guard.commit()
    return count


def queue_status(sessions, redis: Redis) -> dict:
    """Aggregate operational statistics without secrets or repository contents."""
    from datetime import timedelta

    from sqlalchemy import func

    q_analysis = Queue("analysis", connection=redis)
    q_code = Queue("analysis-code", connection=redis)
    try:
        analysis_len = len(q_analysis)
    except Exception:
        analysis_len = 0
    try:
        code_len = len(q_code)
    except Exception:
        code_len = 0
    with sessions() as db:
        counts = dict(db.execute(select(AnalysisRun.status, func.count()).group_by(AnalysisRun.status)).all())
        oldest_queued = db.scalar(select(func.min(AnalysisRun.queued_at)).where(AnalysisRun.status == "queued"))
        since_24h = datetime.now(UTC) - timedelta(hours=24)
        completed_24h = db.scalar(select(func.count()).select_from(AnalysisRun).where(
            AnalysisRun.status == "completed", AnalysisRun.completed_at >= since_24h)) or 0
        failed_24h = db.scalar(select(func.count()).select_from(AnalysisRun).where(
            AnalysisRun.status == "failed", AnalysisRun.completed_at >= since_24h)) or 0
    oldest_age = None
    if oldest_queued is not None:
        tz = UTC if oldest_queued.tzinfo is None else oldest_queued.tzinfo
        oldest_age = round(max(0.0, (datetime.now(UTC) - oldest_queued.replace(tzinfo=tz)).total_seconds()), 1)
    return {
        "analysis_queue_length": analysis_len,
        "analysis_code_queue_length": code_len,
        "queued_runs": counts.get("queued", 0),
        "collecting_runs": counts.get("collecting", 0),
        "analyzing_runs": counts.get("analyzing", 0),
        "scoring_runs": counts.get("scoring", 0),
        "oldest_queued_age_seconds": oldest_age,
        "failed_runs_24h": failed_24h,
        "completed_runs_24h": completed_24h,
    }
