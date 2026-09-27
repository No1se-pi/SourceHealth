"""Deterministic contracts for product growth batch one."""

import json
import unittest
from contextlib import contextmanager
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from sourcehealth.achievements.service import derive
from sourcehealth.analyzers.analytics import CIAnalyzer
from sourcehealth.application.services import AnalysisService, ServiceError
from sourcehealth.auth.sourcecraft import SourceCraftConnection
from sourcehealth.catalog.scheduler import adaptive_interval, effective_interval
from sourcehealth.catalog.sync import CatalogSync
from sourcehealth.core.domain import DataAvailability as A
from sourcehealth.integrations.sourcecraft.client import SourceCraftError
from sourcehealth.logging_config import EventFormatter
from tests.mvp_fixtures import mvp_context


class ProfileSourceCraftTests(unittest.TestCase):
    @staticmethod
    def service(client_factory):
        service = SourceCraftConnection.__new__(SourceCraftConnection)
        service.client_factory = client_factory
        service._keys = lambda token: (None, "credential-key", None)
        service._decrypt = lambda key: "unit-pat"
        return service

    def test_my_repositories_success(self):
        payload = {"repositories": [
            {"id": "repo-1", "slug": "project", "visibility": "public",
             "organization": {"slug": "team"}, "default_branch": "разработка"},
            {"id": "repo-2", "slug": "empty", "visibility": "public",
             "organization": {"slug": "team"}, "default_branch": "", "is_empty": True},
        ]}

        class Client:
            def __enter__(self): return self
            def __exit__(self, *args): return None
            def get(self, path, params=None):
                self.path, self.params = path, params
                return payload

        result = self.service(lambda **kwargs: Client()).my_repositories("session")
        self.assertEqual(result["items"][0]["url"], "https://sourcecraft.dev/team/project")
        self.assertEqual(result["items"][0]["default_branch"], "разработка")
        self.assertIsNone(result["items"][1]["default_branch"])
        self.assertTrue(result["items"][1]["is_empty"])
        self.assertFalse(result["has_more"])

    def test_my_repositories_requires_connection(self):
        service = self.service(lambda **kwargs: self.fail("network must not be called"))
        service._decrypt = lambda key: None
        with self.assertRaises(ServiceError) as caught:
            service.my_repositories("session")
        self.assertEqual((caught.exception.code, caught.exception.status),
                         ("sourcecraft_connection_required", 409))

    def test_expired_import_credential_falls_back(self):
        service = self.service(lambda **kwargs: self.fail("expired credential must not create a PAT client"))
        service._decrypt = lambda key: None
        self.assertIsNone(service.client_for_repository_import("session"))

    def test_upstream_auth_failure_is_safe_and_logs_only_stable_code(self):
        secret = "test-pat"

        class Client:
            def __enter__(self): return self
            def __exit__(self, *args): return None
            def get(self, path, params=None): raise SourceCraftError("authentication_required")

        service = self.service(lambda **kwargs: Client())
        service._decrypt = lambda key: secret
        with self.assertLogs("sourcehealth.auth.sourcecraft", level="WARNING") as logs:
            with self.assertRaises(ServiceError) as caught:
                service.my_repositories("session")
        self.assertEqual((caught.exception.code, caught.exception.status),
                         ("sourcecraft_repositories_unavailable", 503))
        record = logs.records[0]
        self.assertEqual(record.endpoint, "me/repos")
        self.assertEqual(record.sourcecraft_error_code, "authentication_required")
        self.assertNotIn(secret, logs.output[0])
        rendered = EventFormatter().format(record)
        self.assertEqual(json.loads(rendered)["sourcecraft_error_code"], "authentication_required")
        self.assertNotIn(secret, rendered)

    def test_profile_frontend_separates_loading_error_and_retry(self):
        source = (Path(__file__).parents[1] / "frontend/src/pages/ProfilePage.tsx").read_text(encoding="utf-8")
        for contract in ("availableLoading", "availableError", "setAvailableError(reason)",
                         'title="Не удалось загрузить репозитории SourceCraft"',
                         "onRetry={() => void loadAvailable()}", "setLoadMoreError(reason)",
                         "setTrackingError(reason)", 'title="Не удалось добавить репозиторий"'):
            self.assertIn(contract, source)
        self.assertNotIn(".catch(() => setAvailable(null))", source)

    def test_import_failure_log_contains_only_stable_diagnostics(self):
        import httpx

        from sourcehealth.integrations.sourcecraft.client import SourceCraftClient

        settings = SimpleNamespace(sourcecraft_pat=None, sourcecraft_timeout=1)
        service = AnalysisService(SimpleNamespace(), settings)
        client = SourceCraftClient(transport=httpx.MockTransport(
            lambda _: httpx.Response(200, json={"broken": "private-body"})))
        try:
            with self.assertLogs("sourcehealth.application.services", level="WARNING") as logs:
                with self.assertRaises(ServiceError):
                    service.import_public_repository("https://sourcecraft.dev/team/repo", client=client,
                                                     request_id="request-1")
            record = logs.records[0]
            self.assertEqual(record.event, "sourcecraft_repository_import_failed")
            self.assertEqual(record.endpoint, "repository_metadata")
            self.assertEqual(record.sourcecraft_error_code, "invalid_response")
            self.assertEqual(record.request_id, "request-1")
            rendered = EventFormatter().format(record)
            self.assertNotIn("private-body", rendered)
        finally:
            client.close()


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
    def test_concurrent_invocation_skips_before_network(self):
        class Guard:
            def __enter__(self): return self
            def __exit__(self, *args): return None
            def scalar(self, statement, params): return False
            def commit(self): return None

        class Sessions:
            def __call__(self): return Guard()

        result = CatalogSync(Sessions(), SimpleNamespace()).run()
        self.assertEqual(result, {"skipped": True, "reason": "catalog_sync_already_running"})

    def test_recent_completed_cycle_skips_without_network(self):
        state = SimpleNamespace(page_token=None, cycle_started_at=None,
                                last_completed_at=datetime.now(UTC), updated_at=datetime.now(UTC))

        class DB:
            def get(self, model, key, **kwargs): return state

        class Sessions:
            @contextmanager
            def begin(self): yield DB()

        settings = SimpleNamespace(catalog_cycle_interval_seconds=3600)
        result = CatalogSync(Sessions(), settings,
                             client_factory=lambda **kwargs: self.fail("network must not be called")).run()
        self.assertEqual(result, {"skipped": True, "reason": "catalog_cycle_not_due"})

    def test_upsert_preserves_optional_metadata_and_identity_on_rename(self):
        repository_id = uuid4()
        row = SimpleNamespace(id=repository_id, sourcecraft_id="repo-1", organization_slug="team",
                              repository_slug="old", canonical_url="https://sourcecraft.dev/team/old",
                              visibility="public", default_branch="main", language="Python", likes=42)

        class DB:
            def __init__(self): self.calls = 0
            def scalar(self, statement):
                self.calls += 1
                return row
            def add(self, value): self.fail("existing row must not be replaced")

        CatalogSync._upsert(DB(), {"sourcecraft_id": "repo-1", "organization_slug": "team",
                                   "repository_slug": "renamed",
                                   "canonical_url": "https://sourcecraft.dev/team/renamed",
                                   "visibility": "public", "next_analysis_at": datetime.now(UTC)})
        self.assertEqual(row.id, repository_id)
        self.assertEqual(row.repository_slug, "renamed")
        self.assertEqual(row.likes, 42)
        self.assertEqual(row.language, "Python")
        self.assertEqual(row.default_branch, "main")

    def test_upsert_rejects_identity_collision(self):
        first = SimpleNamespace(id=uuid4(), sourcecraft_id="repo-1")
        second = SimpleNamespace(id=uuid4(), sourcecraft_id="repo-2")

        class DB:
            def __init__(self): self.values = iter((first, second))
            def scalar(self, statement): return next(self.values)

        with self.assertRaisesRegex(SourceCraftError, "repository_identity_conflict"):
            CatalogSync._upsert(DB(), {"sourcecraft_id": "repo-1", "organization_slug": "team",
                                       "repository_slug": "taken",
                                       "canonical_url": "https://sourcecraft.dev/team/taken",
                                       "visibility": "public", "next_analysis_at": datetime.now(UTC)})

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

            def scalar(self, statement):
                return None

            def add(self, row):
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

    def test_malformed_catalog_row_does_not_pin_page_checkpoint(self):
        state = SimpleNamespace(page_token=None, cycle_started_at=datetime.now(UTC),
                                last_completed_at=None, updated_at=datetime.now(UTC))
        stored = []

        class DB:
            def get(self, model, key, **kwargs): return state
            def execute(self, statement): return None
            def scalar(self, statement): return None
            def add(self, row): stored.append(row)

        class Sessions:
            @contextmanager
            def begin(self): yield DB()

        class Client:
            def __enter__(self): return self
            def __exit__(self, *args): return None
            def get(self, path, params=None):
                return {"repositories": [
                    {"id": "broken", "slug": None, "visibility": "public",
                     "organization": {"slug": "team"}},
                    {"id": "repo-1", "slug": "project", "visibility": "public",
                     "organization": {"slug": "team"}},
                ], "next_page_token": "page-2"}

        settings = SimpleNamespace(sourcecraft_pat=None, catalog_sync_max_pages=1,
                                   catalog_sync_page_size=100)
        result = CatalogSync(Sessions(), settings, client_factory=lambda **kwargs: Client()).run()
        self.assertEqual(result, {"pages": 1, "repositories": 1, "cycle_complete": False})
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
                               scoring_policy_version="mvp-score-v1.2", category_scores=categories or {},
                               results={"checks": {"sourcecraft_appsec": {
                                   "source": "sourcecraft_appsec", "availability": "available",
                                   "metrics": {"complete": True}}}})

    def test_clean_scan_requires_official_appsec_provenance(self):
        tracked = datetime(2026, 1, 2, tzinfo=UTC)
        relation = SimpleNamespace(created_at=tracked)
        run = self.make_run(100, {"security": {"score": 100, "availability": "available"}}, tracked)
        run.results = {}
        unlocked = {item["id"]: item["unlocked"] for item in derive([(run, relation)])}
        self.assertFalse(unlocked["clean_scan"])

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
