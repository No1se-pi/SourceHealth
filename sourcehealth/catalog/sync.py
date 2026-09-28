"""Bounded, resumable public catalog synchronization."""

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select, text

from sourcehealth.integrations.sourcecraft.client import SourceCraftClient, SourceCraftError
from sourcehealth.integrations.sourcecraft.validation import normalize_repository_metadata
from sourcehealth.storage.models import AnalysisRun, CatalogSyncState
from sourcehealth.storage.repositories import RepositoryIdentityConflict, upsert_sourcecraft_repository

LOG = logging.getLogger(__name__)
CATALOG_SYNC_LOCK_KEY = 0x534F555243454843
# Public catalog rows can contain substantially more embedded metadata than
# ordinary collector responses. Keep this bulk-only allowance finite without
# weakening SourceCraftClient's 4 MiB default for every other endpoint.
CATALOG_MAX_RESPONSE_BYTES = 64 * 1024 * 1024


class CatalogSync:
    def __init__(self, sessions, settings, *, client_factory=SourceCraftClient):
        self.sessions, self.settings, self.client_factory = sessions, settings, client_factory

    def run(self) -> dict:
        """Process a bounded number of pages, committing the token only after each page."""
        # Lightweight unit fakes expose only begin(); real sessionmakers always
        # take the PostgreSQL session-scoped lock below.
        if not callable(self.sessions):
            return self._run_locked()
        with self.sessions() as guard:
            acquired = guard.scalar(text("SELECT pg_try_advisory_lock(:key)"), {"key": CATALOG_SYNC_LOCK_KEY})
            guard.commit()
            if not acquired:
                return {"skipped": True, "reason": "catalog_sync_already_running"}
            try:
                return self._run_locked()
            finally:
                guard.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": CATALOG_SYNC_LOCK_KEY})
                guard.commit()

    def _run_locked(self) -> dict:
        with self.sessions.begin() as db:
            state = db.get(CatalogSyncState, 1, with_for_update=True)
            if state is None:
                state = CatalogSyncState(id=1, cycle_started_at=datetime.now(UTC))
                db.add(state)
            elif (state.page_token is None and state.cycle_started_at is None and state.last_completed_at
                  and state.last_completed_at > datetime.now(UTC) - timedelta(
                      seconds=self.settings.catalog_cycle_interval_seconds)):
                return {"skipped": True, "reason": "catalog_cycle_not_due"}
            token = state.page_token
            if state.cycle_started_at is None:
                state.cycle_started_at = datetime.now(UTC)
        processed = repositories = 0
        seen_tokens = {token} if token else set()
        pat = self.settings.sourcecraft_pat.get_secret_value() if self.settings.sourcecraft_pat else None
        with self.client_factory(pat=pat, deadline_seconds=45,
                                 max_pages=self.settings.catalog_sync_max_pages,
                                 max_response_bytes=CATALOG_MAX_RESPONSE_BYTES) as client:
            for _ in range(self.settings.catalog_sync_max_pages):
                params = {"page_size": self.settings.catalog_sync_page_size, "sort_by": "created_at"}
                if token:
                    params["page_token"] = token
                payload = client.get("/repos", params=params)
                rows = payload.get("repositories")
                if not isinstance(rows, list) or len(rows) > self.settings.catalog_sync_page_size:
                    raise SourceCraftError("invalid_response")
                safe = []
                for row in rows:
                    if isinstance(row, dict) and row.get("visibility") in {"private", "internal"}:
                        continue
                    try:
                        safe.append(self._safe(row))
                    except SourceCraftError as exc:
                        # A malformed public catalog row must not pin the shared page token forever.
                        # Log only the stable validation code; the upstream DTO may contain private data.
                        LOG.warning("catalog_repository_skipped", extra={
                            "component": "catalog", "event": "catalog_repository_skipped",
                            "sourcecraft_error_code": exc.code,
                        })
                next_token = payload.get("next_page_token")
                if next_token not in (None, "") and (not isinstance(next_token, str)
                                                       or len(next_token) > 1024 or next_token in seen_tokens):
                    raise SourceCraftError("invalid_pagination")
                with self.sessions.begin() as db:
                    for values in safe:
                        self._upsert(db, values)
                    state = db.get(CatalogSyncState, 1, with_for_update=True)
                    state.page_token = next_token or None
                    state.updated_at = datetime.now(UTC)
                    if not next_token:
                        state.last_completed_at = state.updated_at
                        state.cycle_started_at = None
                processed += 1
                repositories += len(safe)
                LOG.info("catalog_page_processed", extra={"component": "catalog", "event": "catalog_page_processed",
                                                            "page_count": processed, "repo_count": len(safe)})
                token = next_token
                if not token:
                    break
                seen_tokens.add(token)
        return {"pages": processed, "repositories": repositories, "cycle_complete": not bool(token)}

    @staticmethod
    def _safe(row):
        from sourcehealth.catalog.topics import TOPIC_CLASSIFIER_VERSION, classify_topics

        metadata = normalize_repository_metadata(row, require_public=True)
        topics = classify_topics(
            metadata.repository_slug, metadata.description, metadata.project_slug, metadata.language
        )
        values = {
            "sourcecraft_id": metadata.sourcecraft_id,
            "organization_slug": metadata.organization_slug,
            "repository_slug": metadata.repository_slug,
            "canonical_url": metadata.canonical_url,
            "visibility": "public",
            "description": metadata.description,
            "logo_url": metadata.logo_url,
            "origin": metadata.origin or "unknown",
            "project_slug": metadata.project_slug,
            "topics": topics,
            "topic_classifier_version": TOPIC_CLASSIFIER_VERSION,
        }
        if metadata.default_branch is not None:
            values["default_branch"] = metadata.default_branch
        if metadata.language is not None:
            values["language"] = metadata.language
        if metadata.likes is not None:
            values["likes"] = metadata.likes
        return values

    @staticmethod
    def _upsert(db, values):
        try:
            return upsert_sourcecraft_repository(db, values)
        except RepositoryIdentityConflict:
            raise SourceCraftError("repository_identity_conflict") from None


class CatalogBootstrap:
    """Safe, fast operator public metadata bootstrap."""

    def __init__(self, sessions, settings, *, client_factory=SourceCraftClient):
        self.sessions = sessions
        self.settings = settings
        self.client_factory = client_factory

    def run(
        self,
        *,
        max_pages: int = 50,
        time_budget_seconds: float = 300.0,
        page_size: int = 100,
    ) -> dict:
        """Run metadata bootstrap under CATALOG_SYNC_LOCK_KEY mutual exclusion."""
        if not callable(self.sessions):
            return self._run_locked(
                max_pages=max_pages,
                time_budget_seconds=time_budget_seconds,
                page_size=page_size,
            )
        with self.sessions() as guard:
            acquired = guard.scalar(text("SELECT pg_try_advisory_lock(:key)"), {"key": CATALOG_SYNC_LOCK_KEY})
            guard.commit()
            if not acquired:
                return {"skipped": True, "reason": "catalog_sync_already_running"}
            try:
                return self._run_locked(
                    max_pages=max_pages,
                    time_budget_seconds=time_budget_seconds,
                    page_size=page_size,
                )
            finally:
                guard.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": CATALOG_SYNC_LOCK_KEY})
                guard.commit()

    def _run_locked(
        self,
        *,
        max_pages: int = 50,
        time_budget_seconds: float = 300.0,
        page_size: int = 100,
    ) -> dict:
        import time

        start_time = time.monotonic()

        with self.sessions.begin() as db:
            state = db.get(CatalogSyncState, 1, with_for_update=True)
            if state is None:
                state = CatalogSyncState(id=1, cycle_started_at=datetime.now(UTC))
                db.add(state)
            token = state.page_token
            if state.cycle_started_at is None:
                state.cycle_started_at = datetime.now(UTC)

        processed_pages = 0
        imported_repos = 0
        seen_tokens = {token} if token else set()
        pat = self.settings.sourcecraft_pat.get_secret_value() if self.settings.sourcecraft_pat else None

        effective_page_size = min(100, max(1, page_size))
        with self.client_factory(
            pat=pat,
            deadline_seconds=45,
            max_pages=max_pages,
            max_response_bytes=CATALOG_MAX_RESPONSE_BYTES,
        ) as client:
            while processed_pages < max_pages:
                elapsed = time.monotonic() - start_time
                if elapsed >= time_budget_seconds:
                    LOG.info("catalog_bootstrap_time_budget_reached", extra={
                        "component": "catalog_bootstrap", "event": "time_budget_reached",
                        "pages": processed_pages, "repositories": imported_repos,
                    })
                    break

                params = {"page_size": effective_page_size, "sort_by": "created_at"}
                if token:
                    params["page_token"] = token

                try:
                    payload = client.get("/repos", params=params)
                except Exception as exc:
                    LOG.warning("catalog_bootstrap_page_fetch_failed", extra={
                        "component": "catalog_bootstrap", "event": "fetch_failed",
                        "error": str(exc), "pages_completed": processed_pages,
                    })
                    break

                rows = payload.get("repositories")
                if not isinstance(rows, list):
                    LOG.warning("catalog_bootstrap_invalid_payload", extra={
                        "component": "catalog_bootstrap", "event": "invalid_payload",
                    })
                    break

                safe_rows = []
                for row in rows:
                    if isinstance(row, dict) and row.get("visibility") in {"private", "internal"}:
                        continue
                    try:
                        safe_rows.append(CatalogSync._safe(row))
                    except SourceCraftError:
                        continue

                next_token = payload.get("next_page_token")
                if next_token not in (None, "") and (
                    not isinstance(next_token, str)
                    or len(next_token) > 1024
                    or next_token in seen_tokens
                ):
                    break

                # Atomic per-page commit preserving checkpoint
                with self.sessions.begin() as db:
                    for values in safe_rows:
                        CatalogSync._upsert(db, values)
                    state = db.get(CatalogSyncState, 1, with_for_update=True)
                    state.page_token = next_token or None
                    state.updated_at = datetime.now(UTC)
                    if not next_token:
                        state.last_completed_at = state.updated_at
                        state.cycle_started_at = None

                processed_pages += 1
                imported_repos += len(safe_rows)
                token = next_token
                if not token:
                    break
                seen_tokens.add(token)

        return {
            "pages": processed_pages,
            "repositories": imported_repos,
            "cycle_complete": not bool(token),
            "checkpoint_token_present": bool(token),
        }


def get_catalog_status(sessions) -> dict:
    """Safe, non-secret overview of catalog size and ingestion progress."""
    from sqlalchemy import or_

    from sourcehealth.catalog.topics import TOPIC_CLASSIFIER_VERSION
    from sourcehealth.storage.models import CatalogSyncState, Repository

    with sessions() as db:
        catalog_public_rows = db.scalar(
            select(func.count(Repository.id)).where(Repository.visibility == "public")
        ) or 0

        with_health = db.scalar(
            select(func.count(Repository.id)).where(
                Repository.visibility == "public",
                Repository.health_score.isnot(None),
            )
        ) or 0
        without_health = catalog_public_rows - with_health

        with_topics = db.scalar(
            select(func.count(Repository.id)).where(
                Repository.visibility == "public",
                Repository.topics.isnot(None),
                Repository.topics != [],
            )
        ) or 0
        without_topics = catalog_public_rows - with_topics

        classifier_version_stale = db.scalar(
            select(func.count(Repository.id)).where(
                Repository.visibility == "public",
                or_(
                    Repository.topic_classifier_version != TOPIC_CLASSIFIER_VERSION,
                    Repository.topic_classifier_version.is_(None),
                ),
            )
        ) or 0

        state = db.get(CatalogSyncState, 1)
        checkpoint_present = bool(state and state.page_token)
        last_completed_at = state.last_completed_at.isoformat() if (state and state.last_completed_at) else None
        cycle_in_progress = bool(state and state.cycle_started_at is not None and state.page_token is not None)

    return {
        "catalog_public_rows": catalog_public_rows,
        "with_health": with_health,
        "without_health": without_health,
        "with_topics": with_topics,
        "without_topics": without_topics,
        "classifier_version_stale": classifier_version_stale,
        "current_page_checkpoint_present": checkpoint_present,
        "last_completed_at": last_completed_at,
        "cycle_in_progress": cycle_in_progress,
    }


def queue_backlog(sessions) -> int:
    with sessions() as db:
        return db.scalar(select(func.count()).select_from(AnalysisRun).where(
            AnalysisRun.status.in_(("queued", "collecting", "analyzing", "scoring")))) or 0
