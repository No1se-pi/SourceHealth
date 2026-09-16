"""Durable queued rows → RQ. PostgreSQL advisory lock fences duplicate deliveries."""

import logging
from dataclasses import asdict
from datetime import UTC, datetime
from uuid import UUID

from redis import Redis
from rq import Queue
from rq.exceptions import DuplicateJobError, NoSuchJobError
from rq.job import Job
from sqlalchemy import select, text

from sourcehealth.core import AnalysisContext
from sourcehealth.core.domain import ACTIVE_STATUSES, DataAvailability
from sourcehealth.integrations.sourcecraft.client import SourceCraftClient
from sourcehealth.integrations.sourcecraft.collectors import AppSecCollector, CollectedFacts, RepositoryCollector
from sourcehealth.runtime import configured_runtime
from sourcehealth.scoring.engine import ScoringEngine
from sourcehealth.settings import Settings
from sourcehealth.storage.database import create_database
from sourcehealth.storage.models import AnalysisRun, Repository

from .cache import JsonCache, platform_cache_key
from .connections import create_redis
from .pipeline import analyze_context
from .services import AnalysisService, repository_ref

logger = logging.getLogger(__name__)


def queue_name(profile: str) -> str:
    """Очередь определяется сохранённым профилем, не environment dispatcher."""
    return {"platform-v1": "analysis", "code-v1": "analysis-code"}[profile]


def dispatch_pending(sessions, redis: Redis, timeout: int = 600) -> int:
    """Коммит queued уже существует. Повторная доставка безопасна для execute_analysis."""
    with sessions() as db:
        rows = list(db.execute(select(AnalysisRun.id, AnalysisRun.profile).where(AnalysisRun.status == "queued")
                               .order_by(AnalysisRun.queued_at).limit(100)))
    count = 0
    for run_id, profile in rows:
        queue = Queue(queue_name(profile), connection=redis)
        job_id = str(run_id)
        try:
            job = Job.fetch(job_id, connection=redis)
            if job.get_status(refresh=True) in {"queued", "started", "deferred", "scheduled"}:
                continue
            job.delete()
        except NoSuchJobError:
            pass
        try:
            queue.enqueue(execute_analysis, job_id, job_id=job_id, job_timeout=timeout,
                          result_ttl=0, failure_ttl=86400, unique=True)
            count += 1
        except DuplicateJobError:
            pass  # Another dispatcher won the atomic Redis enqueue.
    return count


def lock_key(analysis_id: UUID) -> int:
    """Signed 64-bit key, stable across Python processes and restarts."""
    return int.from_bytes(analysis_id.bytes[:8], byteorder="big", signed=True)


def collect_platform(repository, settings, redis):
    """Один реальный vertical slice: API metadata + честная AppSec availability."""
    cache = JsonCache(redis)
    key = platform_cache_key(repository.id, "repository_metadata")
    cached = cache.get(key)
    metadata = None
    if cached:
        try:
            metadata = CollectedFacts(**{**cached, "availability": DataAvailability(cached["availability"])})
        except (ValueError, TypeError, KeyError):
            pass
    if metadata is None:
        with SourceCraftClient(pat=settings.sourcecraft_pat.get_secret_value() if settings.sourcecraft_pat else None,
                               timeout=settings.sourcecraft_timeout, max_pages=settings.sourcecraft_max_pages) as client:
            metadata = RepositoryCollector(client).collect(repository)
        if metadata.availability == DataAvailability.AVAILABLE:
            cache.put(key, asdict(metadata), settings.platform_cache_ttl)
    appsec = AppSecCollector().collect(repository)
    return AnalysisContext(repository=repository,
                           metadata={"collection": {"repository_metadata": {"collected_at": metadata.collected_at,
                                                                              "schema_version": metadata.schema_version}}},
                           sourcecraft_facts={"repository_metadata": metadata.facts, "appsec": appsec.facts},
                           collection_statuses={"repository_metadata": metadata.availability,
                                                "appsec": appsec.availability})


def execute_analysis(analysis_id: str) -> None:
    settings = Settings()
    engine, sessions = create_database(settings.database_url.get_secret_value())
    redis = create_redis(settings.redis_url.get_secret_value())
    service = AnalysisService(sessions, settings)
    run_id = UUID(analysis_id)
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
                context = collect_platform(repository, settings, redis)
                service.transition(run_id, "analyzing")
                report = analyze_context(context, include_code=profile == "code-v1",
                                         runtime=configured_runtime(settings) if profile == "code-v1" else None)
                service.transition(run_id, "scoring")
                ScoringEngine().apply(report)
                service.finish(run_id, report)
                logger.info("analysis_finished", extra={"analysis_id": analysis_id, "repository_id": repository.id,
                                                        "component": "worker", "event": "analysis_finished"})
            except Exception:
                # Neither exception text nor source responses are suitable for RQ failure storage/logs.
                with sessions() as db:
                    row = db.get(AnalysisRun, run_id)
                    active = row is not None and row.status in ACTIVE_STATUSES
                if active:
                    service.transition(run_id, "failed", error_code="analysis_failed")
                logger.error("analysis_failed", extra={"analysis_id": analysis_id, "component": "worker"})
            finally:
                guard.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": lock_key(run_id)})
                guard.commit()
    finally:
        redis.close()
        engine.dispose()


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
