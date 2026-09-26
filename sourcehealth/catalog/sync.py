"""Bounded, resumable public catalog synchronization."""

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, or_, select, text

from sourcehealth.integrations.sourcecraft.analytics import identifier
from sourcehealth.integrations.sourcecraft.client import SourceCraftClient, SourceCraftError
from sourcehealth.storage.models import AnalysisRun, CatalogSyncState, Repository

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
                    safe.append(self._safe(row))
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
        if not isinstance(row, dict) or row.get("visibility") != "public":
            raise SourceCraftError("invalid_response")
        sourcecraft_id = identifier(row.get("id"))
        slug = identifier(row.get("slug"))
        organization = row.get("organization")
        organization_slug = identifier(organization.get("slug") if isinstance(organization, dict) else None)
        branch = row.get("default_branch")
        if branch is not None and (not isinstance(branch, str) or len(branch) > 256):
            raise SourceCraftError("invalid_response")
        language = row.get("language")
        language = language.get("name") if isinstance(language, dict) else None
        if language is not None and (not isinstance(language, str) or len(language) > 64):
            language = None
        values = {"sourcecraft_id": sourcecraft_id, "organization_slug": organization_slug,
                "repository_slug": slug, "canonical_url": f"https://sourcecraft.dev/{organization_slug}/{slug}",
                "visibility": "public", "next_analysis_at": datetime.now(UTC)}
        if branch is not None:
            values["default_branch"] = branch
        if language is not None:
            values["language"] = language
        return values

    @staticmethod
    def _upsert(db, values):
        row = db.scalar(select(Repository).where(
            Repository.sourcecraft_id == values["sourcecraft_id"]).with_for_update())
        collision = db.scalar(select(Repository).where(or_(
            Repository.canonical_url == values["canonical_url"],
            (Repository.organization_slug == values["organization_slug"])
            & (Repository.repository_slug == values["repository_slug"])
        )).with_for_update())
        if row is not None and collision is not None and collision.id != row.id:
            raise SourceCraftError("repository_identity_conflict")
        if row is None and collision is not None:
            if collision.sourcecraft_id not in {None, values["sourcecraft_id"]}:
                raise SourceCraftError("repository_identity_conflict")
            row = collision
        if row is None:
            db.add(Repository(**values))
            return
        row.sourcecraft_id = values["sourcecraft_id"]
        for key in ("organization_slug", "repository_slug", "canonical_url", "visibility",
                    "default_branch", "language"):
            if key in values:
                setattr(row, key, values[key])


def queue_backlog(sessions) -> int:
    with sessions() as db:
        return db.scalar(select(func.count()).select_from(AnalysisRun).where(
            AnalysisRun.status.in_(("queued", "collecting", "analyzing", "scoring")))) or 0
