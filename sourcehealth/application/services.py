"""Транзакционные операции запуска и чтения. Никаких расчётов внутри HTTP router."""

import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import func, select, update

from sourcehealth.catalog.scheduler import effective_interval
from sourcehealth.core.domain import ACTIVE_STATUSES, RepositoryRef, validate_transition
from sourcehealth.scoring.mvp import MVPPolicy
from sourcehealth.storage.models import AnalysisRun, Repository, UserRepository
from sourcehealth.storage.repositories import RepositoryIdentityConflict, upsert_sourcecraft_repository

from .cache import fingerprint

LOG = logging.getLogger(__name__)


class ServiceError(RuntimeError):
    def __init__(self, code: str, status: int = 400) -> None:
        self.code, self.status = code, status
        super().__init__(code)


def repository_ref(row: Repository) -> RepositoryRef:
    return RepositoryRef(id=str(row.id), sourcecraft_id=row.sourcecraft_id, organization_slug=row.organization_slug,
                         repository_slug=row.repository_slug, canonical_url=row.canonical_url,
                         visibility=row.visibility, default_branch=row.default_branch, head_sha=row.head_sha)


class AnalysisService:
    def __init__(self, sessions, settings) -> None:
        self.sessions, self.settings = sessions, settings

    def register_repository(self, ref: RepositoryRef) -> UUID:
        """Операторский import; HTTP не может самостоятельно объявить чужой repo публичным."""
        with self.sessions.begin() as db:
            values = ref.to_dict()
            values["id"] = UUID(ref.id)
            if ref.sourcecraft_id:
                try:
                    return upsert_sourcecraft_repository(db, values).id
                except RepositoryIdentityConflict:
                    raise ServiceError("repository_identity_conflict", 409) from None
            row = db.scalar(select(Repository).where(Repository.canonical_url == ref.canonical_url))
            if row is None:
                row = Repository(**values)
                db.add(row)
                db.flush()
            return row.id

    def import_public_repository(self, url: str, *, client=None, request_id: str | None = None) -> UUID:
        """HTTP/CLI import проверяет публичность у платформы; сессия Я ID не даёт private прав."""
        from contextlib import nullcontext

        from sourcehealth.integrations.sourcecraft.client import SourceCraftClient
        from sourcehealth.integrations.sourcecraft.collectors import RepositoryCollector

        try:
            ref = RepositoryRef.from_url(url)
        except ValueError:
            raise ServiceError("invalid_sourcecraft_url", 422) from None
        manager = nullcontext(client) if client is not None else SourceCraftClient(
            pat=self.settings.sourcecraft_pat.get_secret_value() if self.settings.sourcecraft_pat else None,
            timeout=self.settings.sourcecraft_timeout, deadline_seconds=45)
        with manager as source:
            collected = RepositoryCollector(source).collect(ref)
        if collected.availability != "available":
            LOG.warning("sourcecraft_repository_import_failed", extra={
                "component": "sourcecraft", "event": "sourcecraft_repository_import_failed",
                "request_id": request_id, "endpoint": "repository_metadata",
                "sourcecraft_error_code": collected.error, "availability": str(collected.availability),
                "organization_slug": ref.organization_slug, "repository_slug": ref.repository_slug,
            })
            if collected.error in {"public_repository_required", "not_found", "access_denied"}:
                with self.sessions.begin() as db:
                    db.execute(update(Repository).where(
                        Repository.canonical_url == ref.canonical_url).values(visibility="unknown"))
            if collected.error in {"public_repository_required", "not_found", "access_denied"}:
                raise ServiceError("public_repository_unverified", 404)
            if collected.error == "authentication_required":
                raise ServiceError("sourcecraft_credential_unverified", 409)
            if collected.error == "invalid_response":
                raise ServiceError("sourcecraft_invalid_response", 502)
            raise ServiceError("public_repository_unverified", 503)
        ref = RepositoryRef.from_url(ref.canonical_url, sourcecraft_id=collected.facts["id"],
                                     default_branch=collected.facts.get("default_branch"), visibility="public")
        repository_id = self.register_repository(ref)
        with self.sessions.begin() as db:
            row = db.get(Repository, repository_id)
            if "language" in collected.facts:
                row.language = collected.facts["language"]
            row.likes = collected.facts.get("likes")
            if "description" in collected.facts:
                row.description = collected.facts["description"]
            if "logo_url" in collected.facts:
                row.logo_url = collected.facts["logo_url"]
            if "origin" in collected.facts:
                row.origin = collected.facts["origin"]
            if "project_slug" in collected.facts:
                row.project_slug = collected.facts["project_slug"]
            if "topics" in collected.facts:
                row.topics = collected.facts["topics"]
                row.topic_classifier_version = collected.facts.get("topic_classifier_version")
        return repository_id

    def request_analysis(self, repository_id: UUID, *, trigger: str = "manual", force: bool = False,
                         require_official_security: bool = False,
                         preallocated_id: UUID | None = None) -> AnalysisRun:
        if trigger not in {"manual", "scheduled", "refresh", "system"}:
            raise ValueError("invalid trigger")
        now = datetime.now(UTC)
        with self.sessions.begin() as db:
            # Row lock serializes first-run and cached-run decisions across all API instances.
            # A partial unique index is the second invariant if another caller bypasses this service.
            repo = db.scalar(select(Repository).where(Repository.id == repository_id).with_for_update())
            if repo is None or repo.visibility != "public":
                raise ServiceError("repository_not_found", 404)
            active = db.scalar(select(AnalysisRun).where(AnalysisRun.repository_id == repo.id,
                               AnalysisRun.profile == self.settings.analysis_profile,
                               AnalysisRun.status.in_(ACTIVE_STATUSES)))
            if active:
                return active
            key = fingerprint("run-v1", repository_id=str(repo.id), head_sha=repo.head_sha,
                              profile=self.settings.analysis_profile,
                              policy=MVPPolicy.version if self.settings.analysis_profile == "mvp-v1" else "unconfigured-v1", contract="3.0")
            if not force:
                cached = db.scalar(select(AnalysisRun).where(
                    AnalysisRun.fingerprint == key, AnalysisRun.status.in_(("completed", "partial")),
                    AnalysisRun.completed_at >= now - timedelta(seconds=self.settings.result_cache_ttl),
                ).order_by(AnalysisRun.completed_at.desc()).limit(1))
                if cached and (not require_official_security or self._has_official_security(cached)):
                    return cached
            run = AnalysisRun(id=preallocated_id or uuid4(), repository_id=repo.id,
                              trigger=trigger, profile=self.settings.analysis_profile,
                              fingerprint=key, head_sha=repo.head_sha, queued_at=now)
            db.add(run)
            db.flush()
            # queued itself is a durable outbox: dispatcher can always retry after Redis loss.
            return run

    @staticmethod
    def _has_official_security(run: AnalysisRun) -> bool:
        """A cached run is reusable for a connected PAT only after official AppSec completed."""
        results = run.results if isinstance(run.results, dict) else {}
        check = results.get("checks", {}).get("sourcecraft_appsec", {})
        metrics = check.get("metrics", {}) if isinstance(check, dict) else {}
        return (check.get("source") == "sourcecraft_appsec"
                and check.get("availability") == "available"
                and metrics.get("complete") is True)

    def transition(self, analysis_id: UUID, target: str, *, error_code: str | None = None) -> None:
        now = datetime.now(UTC)
        with self.sessions.begin() as db:
            run = db.get(AnalysisRun, analysis_id, with_for_update=True)
            if run is None:
                raise ServiceError("analysis_not_found", 404)
            validate_transition(run.status, target)
            run.status = target
            if target == "collecting":
                run.started_at = now
                run.deadline_at = now + timedelta(seconds=self.settings.analysis_timeout + 60)
            if target in ("completed", "partial", "failed"):
                run.completed_at = now
                run.error_code = error_code
                if target == "failed":
                    repo = db.get(Repository, run.repository_id, with_for_update=True)
                    repo.next_analysis_at = now + timedelta(seconds=self.settings.scheduler_failed_retry_seconds)

    def finish(self, analysis_id: UUID, report) -> None:
        payload = report.to_public_dict()
        with self.sessions.begin() as db:
            run = db.get(AnalysisRun, analysis_id, with_for_update=True)
            target = "completed" if report.complete else "partial"
            validate_transition(run.status, target)
            run.status, run.completed_at = target, datetime.now(UTC)
            run.results, run.category_scores = payload, payload["category_scores"]
            run.scoring_policy_version, run.health_score = report.scoring_policy_version, report.health_score
            run.recommendations = payload["recommendations"]
            run.data_coverage = {name: check.availability.value for name, check in report.checks.items()}
            if run.profile == "mvp-v1":
                run.data_coverage = {name: category["availability"] for name, category in report.category_scores.items()}
                run.head_sha = report.repository.get("head_sha")
            repo = db.get(Repository, run.repository_id, with_for_update=True)
            repo.latest_analysis_id, repo.health_score = run.id, run.health_score
            if run.profile == "mvp-v1":
                repo.head_sha = run.head_sha
                # The first request may not know HEAD yet. Cache the completed
                # observation under its actual snapshot, as subsequent requests do.
                run.fingerprint = fingerprint("run-v1", repository_id=str(repo.id), head_sha=run.head_sha,
                                              profile=run.profile, policy=report.scoring_policy_version, contract="3.0")
                git = report.checks.get("git_activity")
                if git and git.metrics.get("last_commit_date"):
                    repo.last_activity_at = datetime.fromisoformat(git.metrics["last_commit_date"])
            preferences = list(db.scalars(select(UserRepository.refresh_preference).where(
                UserRepository.repository_id == repo.id, UserRepository.refresh_preference != "off")))
            repo.next_analysis_at = run.completed_at + effective_interval(repo.last_activity_at, preferences,
                                                                           now=run.completed_at)

    def enqueue_due(self, connection=None) -> list[UUID]:
        """Scheduler планирует задания. Он никогда не запускает анализ сам."""
        with self.sessions() as db:
            backlog = db.scalar(select(func.count()).select_from(AnalysisRun).where(
                AnalysisRun.status.in_(ACTIVE_STATUSES))) or 0
            capacity = max(0, self.settings.catalog_sync_queue_limit - backlog)
            limit = min(self.settings.scheduler_batch_size, capacity)
            ids = list(db.scalars(select(Repository.id).where(Repository.visibility == "public",
                                  Repository.next_analysis_at <= datetime.now(UTC)).order_by(
                                      Repository.next_analysis_at, Repository.id).limit(
                                          limit))) if limit else []
        runs = []
        for repository_id in ids:
            candidate = uuid4()
            leased = lease_scheduled_credential(self.sessions, connection, repository_id, candidate) if connection else False
            try:
                run = self.request_analysis(repository_id, trigger="scheduled", preallocated_id=candidate)
            except Exception:
                if leased:
                    connection.delete_analysis_credential(candidate)
                raise
            if run.id != candidate:
                if leased:
                    connection.delete_analysis_credential(candidate)
            else:
                runs.append(run.id)
            with self.sessions.begin() as db:
                repo = db.get(Repository, repository_id, with_for_update=True)
                # Reservation prevents repeated enqueue attempts while the durable run is active.
                repo.next_analysis_at = datetime.now(UTC) + timedelta(
                    seconds=max(300, self.settings.scheduler_failed_retry_seconds))
        LOG.info("scheduler_backpressure", extra={"component": "scheduler", "event": "scheduler_backpressure",
                                                   "backlog": backlog, "capacity": capacity,
                                                   "scheduled_count": len(runs)})
        return runs


def lease_scheduled_credential(sessions, connection, repository_id, analysis_id):
    """Lease the first usable consenting credential without mutating another run."""
    if connection is None:
        return False
    with sessions() as db:
        trackers = list(db.scalars(select(UserRepository.user_id).where(
            UserRepository.repository_id == repository_id,
            UserRepository.use_pat_for_scheduled_analysis.is_(True),
        ).order_by(UserRepository.created_at, UserRepository.user_id).limit(100)))
    for user_id in trackers:
        try:
            if connection.lease_user_for_analysis(user_id, analysis_id):
                return True
        except ServiceError as exc:
            if exc.code in {"sourcecraft_connection_not_configured", "sourcecraft_connection_key_invalid"}:
                raise
    return False
