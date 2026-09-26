"""Deterministic contracts for product growth batch one."""

import unittest
from contextlib import contextmanager
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

from sourcehealth.achievements.service import derive
from sourcehealth.analyzers.analytics import CIAnalyzer
from sourcehealth.catalog.scheduler import adaptive_interval, effective_interval
from sourcehealth.catalog.sync import CatalogSync
from sourcehealth.core.domain import DataAvailability as A
from sourcehealth.integrations.sourcecraft.client import SourceCraftError
from tests.mvp_fixtures import mvp_context


class AdaptiveSchedulerTests(unittest.TestCase):
    def test_activity_tiers_and_unknown(self):
        now = datetime(2026, 9, 27, tzinfo=UTC)
        cases = [(None, 24), (timedelta(days=1), 1), (timedelta(days=7), 6),
                 (timedelta(days=30), 24), (timedelta(days=180), 72),
                 (timedelta(days=181), 168)]
        for age, hours in cases:
            activity = None if age is None else now - age
            self.assertEqual(adaptive_interval(activity, now=now), timedelta(hours=hours))

    def test_active_preference_can_request_faster_but_never_below_one_hour(self):
        now = datetime(2026, 9, 27, tzinfo=UTC)
        old = now - timedelta(days=365)
        self.assertEqual(effective_interval(old, ["off", "6h"], now=now), timedelta(hours=6))
        self.assertEqual(effective_interval(old, ["adaptive"], now=now), timedelta(days=7))


class CISemanticsTests(unittest.TestCase):
    def test_complete_snapshot_proves_no_config_during_api_outage(self):
        context = deepcopy(mvp_context())
        context.sourcecraft_facts["cicd"]["items"] = []
        context.collection_statuses["cicd"] = A.SOURCE_UNAVAILABLE
        context.metadata.update(ci_configured=False, ci_config_complete=True)
        result = CIAnalyzer().analyze(context)
        self.assertEqual(result.availability, A.NOT_CONFIGURED)
        self.assertFalse(result.metrics["configured"])

    def test_runs_override_snapshot_and_partial_snapshot_proves_nothing(self):
        context = deepcopy(mvp_context())
        context.metadata.update(ci_configured=False, ci_config_complete=True)
        self.assertTrue(CIAnalyzer().analyze(context).metrics["configured"])
        context.sourcecraft_facts["cicd"]["items"] = []
        context.collection_statuses["cicd"] = A.SOURCE_UNAVAILABLE
        context.metadata["ci_config_complete"] = False
        result = CIAnalyzer().analyze(context)
        self.assertIsNone(result.metrics["configured"])
        self.assertNotEqual(result.availability, A.NOT_CONFIGURED)


class CatalogValidationTests(unittest.TestCase):
    def test_catalog_allowlist_and_public_only(self):
        row = {"id": "repo-1", "slug": "project", "visibility": "public",
               "organization": {"slug": "team"}, "default_branch": "main",
               "description": "must not survive", "language": {"name": "Python"}}
        safe = CatalogSync._safe(row)
        self.assertEqual(safe["canonical_url"], "https://sourcecraft.dev/team/project")
        self.assertNotIn("description", safe)
        with self.assertRaises(SourceCraftError):
            CatalogSync._safe({**row, "visibility": "private"})

    def test_checkpoint_after_page_failure(self):
        state = SimpleNamespace(page_token=None, cycle_started_at=datetime.now(UTC),
                                last_completed_at=None, updated_at=datetime.now(UTC))

        class DB:
            def get(self, model, key, **kwargs):
                return state

            def execute(self, statement):
                return None

        class Sessions:
            @contextmanager
            def begin(self):
                yield DB()

        class Client:
            calls = 0

            def __enter__(self): return self
            def __exit__(self, *args): return None

            def get(self, path, params=None):
                self.calls += 1
                if self.calls == 2:
                    raise SourceCraftError("source_unavailable")
                return {"repositories": [{"id": "repo-1", "slug": "project", "visibility": "public",
                                           "organization": {"slug": "team"}}],
                        "next_page_token": "page-2"}

        settings = SimpleNamespace(sourcecraft_pat=None, catalog_sync_max_pages=2, catalog_sync_page_size=100)
        with self.assertRaises(SourceCraftError):
            CatalogSync(Sessions(), settings, client_factory=lambda **kwargs: Client()).run()
        self.assertEqual(state.page_token, "page-2")

    def test_complete_page_closes_cycle(self):
        state = SimpleNamespace(page_token="last", cycle_started_at=datetime.now(UTC),
                                last_completed_at=None, updated_at=datetime.now(UTC))

        class DB:
            def get(self, model, key, **kwargs): return state
            def execute(self, statement): return None

        class Sessions:
            @contextmanager
            def begin(self): yield DB()

        class Client:
            def __enter__(self): return self
            def __exit__(self, *args): return None
            def get(self, path, params=None): return {"repositories": [], "next_page_token": None}

        settings = SimpleNamespace(sourcecraft_pat=None, catalog_sync_max_pages=1, catalog_sync_page_size=100)
        result = CatalogSync(Sessions(), settings, client_factory=lambda **kwargs: Client()).run()
        self.assertTrue(result["cycle_complete"])
        self.assertIsNone(state.page_token)
        self.assertIsNone(state.cycle_started_at)
        self.assertIsNotNone(state.last_completed_at)

    def test_repeated_page_token_is_rejected(self):
        state = SimpleNamespace(page_token=None, cycle_started_at=datetime.now(UTC),
                                last_completed_at=None, updated_at=datetime.now(UTC))

        class DB:
            def get(self, model, key, **kwargs): return state
            def execute(self, statement): return None

        class Sessions:
            @contextmanager
            def begin(self): yield DB()

        class Client:
            def __enter__(self): return self
            def __exit__(self, *args): return None
            def get(self, path, params=None): return {"repositories": [], "next_page_token": "same"}

        settings = SimpleNamespace(sourcecraft_pat=None, catalog_sync_max_pages=3, catalog_sync_page_size=100)
        with self.assertRaisesRegex(SourceCraftError, "invalid_pagination"):
            CatalogSync(Sessions(), settings, client_factory=lambda **kwargs: Client()).run()


class AchievementTests(unittest.TestCase):
    def make_run(self, score=None, categories=None, completed=None):
        return SimpleNamespace(id=uuid4(), repository_id=uuid4(), status="completed",
                               queued_at=completed, completed_at=completed, health_score=score,
                               scoring_policy_version="mvp-score-v1.2", category_scores=categories or {})

    def test_boundaries_security_and_old_history(self):
        tracked = datetime(2026, 1, 2, tzinfo=UTC)
        relation = SimpleNamespace(created_at=tracked)
        old = self.make_run(100, completed=tracked - timedelta(days=1))
        first = self.make_run(79.99, {"security": {"score": 100, "availability": "no_data"}}, tracked)
        second = self.make_run(80, {"security": {"score": 100, "availability": "available"}}, tracked + timedelta(days=1))
        second.repository_id = first.repository_id
        unlocked = {item["id"]: item["unlocked"] for item in derive([(old, relation), (first, relation), (second, relation)])}
        self.assertTrue(unlocked["healthy_project"])
        self.assertTrue(unlocked["clean_scan"])
        self.assertTrue(unlocked["first_checkup"])

    def test_recovery_exactly_twenty(self):
        tracked = datetime(2026, 1, 1, tzinfo=UTC)
        relation = SimpleNamespace(created_at=tracked)
        first = self.make_run(60, completed=tracked)
        second = self.make_run(80, completed=tracked + timedelta(days=1))
        second.repository_id = first.repository_id
        result = {item["id"]: item for item in derive([(first, relation), (second, relation)])}
        self.assertTrue(result["recovery"]["unlocked"])
        self.assertEqual(result["recovery"]["unlocked_at"], second.completed_at)


if __name__ == "__main__":
    unittest.main()
