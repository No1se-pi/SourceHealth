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
                                 max_pages=self.settings.catalog_sync_max_pages) as client:
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
        metadata = normalize_repository_metadata(row, require_public=True)
        values = {"sourcecraft_id": metadata.sourcecraft_id,
                "organization_slug": metadata.organization_slug,
                "repository_slug": metadata.repository_slug, "canonical_url": metadata.canonical_url,
                "visibility": "public", "next_analysis_at": datetime.now(UTC)}
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


def queue_backlog(sessions) -> int:
    with sessions() as db:
        return db.scalar(select(func.count()).select_from(AnalysisRun).where(
            AnalysisRun.status.in_(("queued", "collecting", "analyzing", "scoring")))) or 0
