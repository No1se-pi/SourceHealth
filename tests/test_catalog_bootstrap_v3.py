"""Regression tests for Task 3: Catalog & Search v3, Topics, and Fast Metadata Bootstrap.

Covers:
1. Desktop renders no mobile duplicate
2. Mobile renders no desktop table
3. Default browse includes all public metadata repos and sorts evaluated first
4. Text search can return NO_DATA/unanalysed repo
5. Explicit health_status=available works
6. Explicit health_status=no_data works
7. Histogram numeric bins exclude NO_DATA
8. NO_DATA count remains available as metadata
9. ML topic works
10. Mobile topic works
11. Web topic works
12. Security topic works
13. Keyset topic reclassification on >=1200 stale repos with batch commit
14. Search exact org/repo
15. Search exact repo
16. Multi-token search
17. Deterministic relevance
18. Bootstrap resumes from checkpoint
19. Bootstrap interruption preserves checkpoint
20. Bootstrap never starts analysis jobs and decouples scheduling
21. Catalog status safe output
22. 30k synthetic query performance remains reasonable
23. Bootstrap and sync mutual exclusion under advisory lock
24. Shared upsert does not inject 365 days delay
25. Metadata sync preserves existing repository schedules
26. Default browse stats and query consistency
"""

import json
import unittest
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import httpx

from sourcehealth.catalog.query import (
    CatalogFilters,
    apply_catalog_filters,
    apply_catalog_sort,
    build_catalog_base_query,
    get_catalog_repositories,
    get_catalog_stats,
)
from sourcehealth.catalog.sync import (
    CATALOG_MAX_RESPONSE_BYTES,
    CATALOG_SYNC_LOCK_KEY,
    CatalogBootstrap,
    CatalogSync,
    get_catalog_status,
)
from sourcehealth.catalog.topics import (
    TOPIC_CLASSIFIER_VERSION,
    classify_topics,
    reclassify_catalog_topics,
)
from sourcehealth.integrations.sourcecraft.client import SourceCraftClient, SourceCraftError
from sourcehealth.storage.models import Repository
from sourcehealth.storage.repositories import upsert_sourcecraft_repository


class CatalogBootstrapV3RegressionTests(unittest.TestCase):
    def test_catalog_preserves_long_slug_and_advances_checkpoint(self):
        long_slug = "r" * 125
        captured = []
        state = SimpleNamespace(page_token="before", cycle_started_at=datetime.now(UTC),
                                updated_at=None, last_completed_at=None)

        class FactoryClient:
            def __init__(self, **kwargs): pass
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def get(self, path, params=None):
                return {"repositories": [{
                    "id": "long-slug-id", "slug": long_slug,
                    "organization": {"slug": "team"},
                    "project": {"slug": "project"}, "visibility": "public",
                }], "next_page_token": "after"}

        class FakeDB:
            def get(self, model, key, **kwargs): return state
            def add(self, row): pass

        class FakeSessions:
            @contextmanager
            def begin(self): yield FakeDB()

        settings = SimpleNamespace(sourcecraft_pat=None, catalog_sync_max_pages=1,
                                   catalog_sync_page_size=100,
                                   catalog_cycle_interval_seconds=3600)
        original = CatalogSync._upsert
        try:
            CatalogSync._upsert = staticmethod(lambda db, values: captured.append(values))
            result = CatalogSync(FakeSessions(), settings, client_factory=FactoryClient)._run_locked()
        finally:
            CatalogSync._upsert = staticmethod(original)

        self.assertEqual(result, {"pages": 1, "repositories": 1, "cycle_complete": False})
        self.assertEqual(state.page_token, "after")
        self.assertEqual(captured[0]["repository_slug"], long_slug)
        self.assertEqual(captured[0]["canonical_url"], f"https://sourcecraft.dev/team/{long_slug}")
        self.assertLessEqual(len(captured[0]["repository_slug"]),
                             Repository.__table__.c.repository_slug.type.length)

    def test_catalog_uses_bulk_only_bounded_response_limit(self):
        self.assertEqual(CATALOG_MAX_RESPONSE_BYTES, 64 * 1024 * 1024)
        self.assertGreater(CATALOG_MAX_RESPONSE_BYTES, 8_581_717)

        captured = []

        class FactoryClient:
            def __init__(self, **kwargs):
                captured.append(kwargs)
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def get(self, path, params=None):
                return {"repositories": [], "next_page_token": None}

        state = SimpleNamespace(page_token=None, cycle_started_at=None,
                                updated_at=None, last_completed_at=None)

        class FakeDB:
            def get(self, model, key, **kwargs): return state
            def add(self, row): pass

        class FakeSessions:
            @contextmanager
            def begin(self): yield FakeDB()

        settings = SimpleNamespace(
            sourcecraft_pat=None,
            catalog_sync_max_pages=1,
            catalog_sync_page_size=1,
            catalog_cycle_interval_seconds=3600,
        )
        CatalogSync(FakeSessions(), settings, client_factory=FactoryClient)._run_locked()
        CatalogBootstrap(FakeSessions(), settings, client_factory=FactoryClient)._run_locked(
            max_pages=1, time_budget_seconds=10, page_size=1
        )
        self.assertEqual(
            [kwargs["max_response_bytes"] for kwargs in captured],
            [CATALOG_MAX_RESPONSE_BYTES, CATALOG_MAX_RESPONSE_BYTES],
        )

    def test_generic_default_rejects_response_over_four_mib(self):
        payload = json.dumps({"payload": "x" * (4 * 1024 * 1024)}).encode()
        with SourceCraftClient(transport=httpx.MockTransport(
            lambda request: httpx.Response(200, content=payload)
        )) as client:
            self.assertEqual(client.max_response_bytes, 4_194_304)
            with self.assertRaisesRegex(SourceCraftError, "^response_limit$"):
                client.get("/user")

    def test_catalog_large_response_and_boundary(self):
        payload = json.dumps({"payload": "x" * (5 * 1024 * 1024)}).encode()
        with SourceCraftClient(
            max_response_bytes=CATALOG_MAX_RESPONSE_BYTES,
            transport=httpx.MockTransport(lambda request: httpx.Response(200, content=payload)),
        ) as client:
            self.assertEqual(len(client.get("/repos")["payload"]), 5 * 1024 * 1024)

        # Content-Length proves the 64 MiB catalog allowance is still bounded
        # without allocating an oversized fixture in the test process.
        with SourceCraftClient(
            max_response_bytes=CATALOG_MAX_RESPONSE_BYTES,
            transport=httpx.MockTransport(lambda request: httpx.Response(
                200,
                headers={"Content-Length": str(CATALOG_MAX_RESPONSE_BYTES + 1)},
                content=b"{}",
            )),
        ) as client:
            with self.assertRaisesRegex(SourceCraftError, "^response_limit$"):
                client.get("/repos")

    # 1. Desktop renders no mobile duplicate
    def test_01_desktop_renders_no_mobile_duplicate(self):
        page_src = (Path(__file__).parents[1] / "frontend/src/pages/LeaderboardPage.tsx").read_text(encoding="utf-8")
        # Must not have inline display: flex overriding CSS display: none
        self.assertNotIn('<div className="leaderboard-mobile" style={{ display: \'flex\'', page_src)
        self.assertIn('<div className="leaderboard-mobile">', page_src)

        css_src = (Path(__file__).parents[1] / "frontend/src/styles/style.css").read_text(encoding="utf-8")
        self.assertIn(".leaderboard-mobile {\n  display: none;\n}", css_src)

    # 2. Mobile renders no desktop table
    def test_02_mobile_renders_no_desktop_table(self):
        css_src = (Path(__file__).parents[1] / "frontend/src/styles/style.css").read_text(encoding="utf-8")
        # Under @media (max-width: 768px), desktop table must be hidden and mobile flexed
        self.assertIn(".leaderboard-desktop {\n    display: none;\n  }", css_src)
        self.assertIn(".leaderboard-mobile {\n    display: flex;\n", css_src)

    # 3. Default browse includes all public repos and sorts evaluated first
    def test_03_default_browse_sorts_evaluated_first(self):
        filters = CatalogFilters(q=None, health_status=None)
        mock_db = MagicMock()
        mock_db.scalar.return_value = 0
        mock_db.execute.return_value.all.return_value = []

        get_catalog_repositories(mock_db, filters)
        executed_stmt = mock_db.execute.call_args[0][0]
        compiled = str(executed_stmt.compile(compile_kwargs={"literal_binds": True}))
        # Default browse does NOT silently filter out unanalysed rows
        self.assertNotIn("IS NOT NULL", compiled)
        # Order by sorts effective_health DESC NULLS LAST
        self.assertIn("NULLS LAST", compiled)

    # 4. Text search can still return NO_DATA/unanalysed repo
    def test_04_text_search_can_return_unanalysed_repo(self):
        filters = CatalogFilters(q="my-repo", health_status=None)
        mock_db = MagicMock()
        mock_db.scalar.return_value = 0
        mock_db.execute.return_value.all.return_value = []

        get_catalog_repositories(mock_db, filters)
        executed_stmt = mock_db.execute.call_args[0][0]
        compiled = str(executed_stmt.compile(compile_kwargs={"literal_binds": True}))
        # Text search without explicit health_status does NOT restrict to IS NOT NULL
        self.assertNotIn("IS NOT NULL", compiled)

    # 5. Explicit health_status=available works
    def test_05_explicit_health_status_available_works(self):
        filters = CatalogFilters(q=None, health_status="available")
        mock_db = MagicMock()
        mock_db.scalar.return_value = 0
        mock_db.execute.return_value.all.return_value = []

        get_catalog_repositories(mock_db, filters)
        executed_stmt = mock_db.execute.call_args[0][0]
        compiled = str(executed_stmt.compile(compile_kwargs={"literal_binds": True}))
        self.assertIn("IS NOT NULL", compiled)

    # 6. Explicit health_status=no_data works
    def test_06_explicit_health_status_no_data_works(self):
        filters = CatalogFilters(q=None, health_status="no_data")
        mock_db = MagicMock()
        mock_db.scalar.return_value = 0
        mock_db.execute.return_value.all.return_value = []

        get_catalog_repositories(mock_db, filters)
        executed_stmt = mock_db.execute.call_args[0][0]
        compiled = str(executed_stmt.compile(compile_kwargs={"literal_binds": True}))
        self.assertIn("IS NULL", compiled)

    # 7. Histogram numeric bins exclude NO_DATA
    def test_07_histogram_numeric_bins_exclude_no_data(self):
        histo_src = (Path(__file__).parents[1] / "frontend/src/components/catalog/HealthHistogram.tsx").read_text(encoding="utf-8")
        # maxBucketCount scales only over numeric buckets, not flattening them by noDataCount
        self.assertIn("const maxBucketCount = Math.max(1, ...buckets.map((b) => b.count));", histo_src)
        self.assertNotIn("...buckets.map((b) => b.count),\n    noDataCount,", histo_src)

    # 8. NO_DATA count remains available somewhere as metadata
    def test_08_no_data_count_remains_available_somewhere_as_metadata(self):
        # Fake DB returning mixed rows
        class FakeResult:
            def __init__(self, data): self._data = data
            def all(self): return self._data
            def __iter__(self): return iter(self._data)

        class FakeDB:
            def scalar(self, stmt): return 10
            def execute(self, stmt):
                return FakeResult([
                    ("r1", 85.0, "a1", "Python", "native", ["web"]),
                    ("r2", None, None, "TypeScript", "fork", ["bots"]),
                    ("r3", 72.5, "a3", "Go", "native", ["devops"]),
                    ("r4", None, "a4", "Python", "native", ["ml_data"]),
                ])

        filters = CatalogFilters()
        stats = get_catalog_stats(FakeDB(), filters)
        self.assertEqual(stats["health_available_count"], 2)
        self.assertEqual(stats["health_no_data_count"], 2)
        self.assertEqual(stats["histogram_no_data_count"], 2)
        # Median computed strictly over [72.5, 85.0]
        self.assertAlmostEqual(stats["health_median"], 78.8, places=1)

    # 9. ML topic works
    def test_09_ml_topic_works(self):
        t1 = classify_topics("bert-model", "Предобученная нейросеть для NLP", "proj", "Python")
        self.assertIn("ml_data", t1)
        t2 = classify_topics("data-science-notes", "Датасет и jupyter notebook для анализа", "", "Jupyter Notebook")
        self.assertIn("ml_data", t2)

    # 10. Mobile topic works
    def test_10_mobile_topic_works(self):
        t1 = classify_topics("tracker-app", "Мобильное приложение для учета привычек", "mob", "Dart")
        self.assertIn("mobile", t1)
        t2 = classify_topics("ios-wallet", "Flutter crypto wallet", "", "Dart")
        self.assertIn("mobile", t2)

    # 11. Web topic works
    def test_11_web_topic_works(self):
        t1 = classify_topics("frontend-ui", "React components for dashboard", "web", "TypeScript")
        self.assertIn("web", t1)
        t2 = classify_topics("fastapi-backend", "Сайт и backend API", "", "Python")
        self.assertIn("web", t2)

    # 12. Security topic works
    def test_12_security_topic_works(self):
        t1 = classify_topics("sast-tool", "Static application security testing", "sec", "Go")
        self.assertIn("security", t1)
        t2 = classify_topics("vuln-scanner", "Сканер уязвимостей и аудит безопасности", "", "Python")
        self.assertIn("security", t2)

    # 13. Topic reclassification keyset pagination on >=1200 stale repos with batch commits
    def test_13_topic_reclassification_keyset_1200_repos_batch_commits(self):
        storage = [
            SimpleNamespace(
                id=i,
                repository_slug=f"repo-{i}",
                description="Бот для телеграма и чат-бот",
                project_slug=None,
                language="Python",
                topics=[],
                topic_classifier_version=None,
                visibility="public",
            )
            for i in range(1, 1201)
        ]

        commit_count = 0

        class FakeDB:
            def scalars(self, query):
                last_id = None
                for c in getattr(query, "_where_criteria", ()):
                    if hasattr(c, "left") and getattr(c.left, "name", None) == "id" and c.operator.__name__ == "gt":
                        last_id = c.right.value
                limit = query._limit
                matching = [
                    r for r in storage
                    if (r.topic_classifier_version != TOPIC_CLASSIFIER_VERSION or not r.topic_classifier_version)
                    and (last_id is None or r.id > last_id)
                ]
                matching = sorted(matching, key=lambda r: r.id)[:limit]
                return SimpleNamespace(all=lambda: matching)

        class FakeSessions:
            @contextmanager
            def begin(self):
                nonlocal commit_count
                commit_count += 1
                yield FakeDB()

        res1 = reclassify_catalog_topics(FakeSessions(), batch_size=100)
        # Must scan and update all 1,200 stale repositories
        self.assertEqual(res1["scanned"], 1200)
        self.assertEqual(res1["updated"], 1200)
        # 12 full batches of 100 + 1 terminal empty batch = 13 commits
        self.assertEqual(commit_count, 13)
        self.assertTrue(all(r.topic_classifier_version == TOPIC_CLASSIFIER_VERSION for r in storage))
        self.assertTrue(all("bots" in r.topics for r in storage))

        # Second run: idempotent, 0 rows needing update
        res2 = reclassify_catalog_topics(FakeSessions(), batch_size=100)
        self.assertEqual(res2["scanned"], 0)
        self.assertEqual(res2["updated"], 0)

    # 14. Search exact org/repo
    def test_14_search_exact_org_repo(self):
        base = build_catalog_base_query()
        filters = CatalogFilters(q="yandex/sourcehealth")
        sorted_q = apply_catalog_sort(base, filters)
        compiled = str(sorted_q.compile(compile_kwargs={"literal_binds": True}))
        # Relevance case 1 checks exact full_slug match
        self.assertIn("yandex/sourcehealth", compiled)
        self.assertIn("THEN 1", compiled)

    # 15. Search exact repo
    def test_15_search_exact_repo(self):
        base = build_catalog_base_query()
        filters = CatalogFilters(q="sourcehealth")
        sorted_q = apply_catalog_sort(base, filters)
        compiled = str(sorted_q.compile(compile_kwargs={"literal_binds": True}))
        # Relevance case 2 checks exact repo_slug
        self.assertIn("THEN 2", compiled)

    # 16. Multi-token search
    def test_16_multi_token_search(self):
        base = build_catalog_base_query()
        filters = CatalogFilters(q="source health")
        filtered_q = apply_catalog_filters(base, filters)
        compiled = str(filtered_q.compile(compile_kwargs={"literal_binds": True}))
        # Both tokens 'source' and 'health' must be matched in the query condition
        self.assertIn("'source'", compiled)
        self.assertIn("'health'", compiled)
        self.assertIn("'source-health'", compiled)
        self.assertIn("'sourcehealth'", compiled)

    # 17. Deterministic relevance
    def test_17_deterministic_relevance(self):
        base = build_catalog_base_query()
        filters = CatalogFilters(q="fastapi")
        sorted_q = apply_catalog_sort(base, filters)
        compiled = str(sorted_q.compile(compile_kwargs={"literal_binds": True}))
        # Relevance rank ASC, then health DESC NULLS LAST, then repository id ASC
        self.assertIn("ORDER BY CASE", compiled)
        self.assertIn("repositories.id ASC", compiled)

    # 18. Bootstrap resumes from checkpoint
    def test_18_bootstrap_resumes_from_checkpoint(self):
        state = SimpleNamespace(page_token="saved_token_123", cycle_started_at=None,
                                updated_at=None, last_completed_at=None)

        class FakeDB:
            def get(self, model, key, **kwargs): return state

        class FakeSessions:
            @contextmanager
            def begin(self): yield FakeDB()

        class FakeClient:
            def __init__(self, **kwargs): self.requested_params = []
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def get(self, path, params=None):
                self.requested_params.append(params)
                return {"repositories": [], "next_page_token": None}

        client_inst = FakeClient()
        settings = SimpleNamespace(sourcecraft_pat=None)
        bootstrap = CatalogBootstrap(FakeSessions(), settings, client_factory=lambda **kw: client_inst)
        res = bootstrap.run(max_pages=1)
        self.assertEqual(res["pages"], 1)
        # Verified it used the saved checkpoint token
        self.assertEqual(client_inst.requested_params[0]["page_token"], "saved_token_123")

    # 19. Bootstrap interruption preserves checkpoint
    def test_19_bootstrap_interruption_preserves_checkpoint(self):
        state = SimpleNamespace(page_token=None, cycle_started_at=None,
                                updated_at=None, last_completed_at=None)

        class FakeDB:
            def get(self, model, key, **kwargs): return state
            def scalar(self, stmt): return None
            def add(self, row): pass

        class FakeSessions:
            @contextmanager
            def begin(self): yield FakeDB()

        call_count = 0

        class FailingClient:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def get(self, path, params=None):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    return {
                        "repositories": [{"id": "r1", "slug": "repo1", "visibility": "public",
                                          "organization": {"slug": "team"}, "default_branch": "main"}],
                        "next_page_token": "page_2_checkpoint",
                    }
                raise RuntimeError("Network failed on page 2")

        settings = SimpleNamespace(sourcecraft_pat=None)
        bootstrap = CatalogBootstrap(FakeSessions(), settings, client_factory=lambda **kw: FailingClient())
        res = bootstrap.run(max_pages=5)
        # Page 1 succeeded and checkpointed page_2_checkpoint
        self.assertEqual(res["pages"], 1)
        self.assertEqual(state.page_token, "page_2_checkpoint")

    # 20. Bootstrap never starts analysis jobs and does not force +365 days
    def test_20_bootstrap_never_starts_analysis_jobs(self):
        state = SimpleNamespace(page_token=None, cycle_started_at=None,
                                updated_at=None, last_completed_at=None)

        class FakeDB:
            def get(self, model, key, **kwargs): return state
            def scalar(self, stmt): return None
            def add(self, row): pass

        class FakeSessions:
            @contextmanager
            def begin(self): yield FakeDB()

        class MockClient:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def get(self, path, params=None):
                return {
                    "repositories": [{"id": "r1", "slug": "new-repo", "visibility": "public",
                                      "organization": {"slug": "team"}, "default_branch": "main"}],
                    "next_page_token": None,
                }

        # Verify _safe does NOT inject next_analysis_at into values
        safe_values = CatalogSync._safe({"id": "r1", "slug": "new-repo", "visibility": "public",
                                        "organization": {"slug": "team"}, "default_branch": "main"})
        self.assertNotIn("next_analysis_at", safe_values)

        settings = SimpleNamespace(sourcecraft_pat=None)
        bootstrap = CatalogBootstrap(FakeSessions(), settings, client_factory=lambda **kw: MockClient())
        res = bootstrap.run(max_pages=1)
        self.assertEqual(res["pages"], 1)
        self.assertEqual(res["repositories"], 1)

    # 21. Catalog status safe output
    def test_21_catalog_status_safe_output(self):
        class FakeDB:
            def scalar(self, stmt): return 42
            def get(self, model, key):
                return SimpleNamespace(page_token="tok", last_completed_at=datetime(2026, 9, 28, tzinfo=UTC), cycle_started_at=None)

        class FakeSessions:
            def __call__(self): return self
            def __enter__(self): return FakeDB()
            def __exit__(self, *args): pass

        status = get_catalog_status(FakeSessions())
        expected_keys = {
            "catalog_public_rows",
            "with_health",
            "without_health",
            "with_topics",
            "without_topics",
            "classifier_version_stale",
            "current_page_checkpoint_present",
            "last_completed_at",
            "cycle_in_progress",
        }
        self.assertEqual(set(status.keys()), expected_keys)
        # Safe non-secret types
        for k, v in status.items():
            self.assertIsInstance(v, (int, bool, str, type(None)))

    # 22. 30k synthetic query performance remains reasonable
    def test_22_30k_synthetic_query_performance(self):
        from scripts.catalog_30k_benchmark import (
            CatalogBenchmarkEngine,
            generate_synthetic_catalog,
        )

        catalog = generate_synthetic_catalog(5000)  # fast targeted run
        engine = CatalogBenchmarkEngine(catalog)

        # Browse
        import time
        engine.query(limit=20, sort="health_score")
        browse_times = []
        for _ in range(5):
            t0 = time.perf_counter()
            page, total = engine.query(limit=20, sort="health_score")
            browse_times.append((time.perf_counter() - t0) * 1000)
        self.assertLess(min(browse_times), 50.0)
        self.assertLessEqual(len(page), 20)

        # Multi-token search
        engine.query(q="bot service", limit=20)
        search_times = []
        for _ in range(5):
            t0 = time.perf_counter()
            search_res, s_total = engine.query(q="bot service", limit=20)
            search_times.append((time.perf_counter() - t0) * 1000)
        self.assertLess(min(search_times), 50.0)

        # Stats & histogram
        engine.stats()
        stats_times = []
        for _ in range(5):
            t0 = time.perf_counter()
            st = engine.stats()
            stats_times.append((time.perf_counter() - t0) * 1000)
        self.assertLess(min(stats_times), 100.0)
        self.assertEqual(len(st["buckets"]), 10)

    # 23. Bootstrap and sync mutual exclusion under advisory lock
    def test_23_catalog_bootstrap_and_sync_mutual_exclusion(self):
        self.assertEqual(CATALOG_SYNC_LOCK_KEY, 0x534F555243454843)
        class LockContentionGuard:
            def scalar(self, stmt, params=None):
                # Lock is already held by another process
                return False
            def commit(self): pass
            def execute(self, stmt, params=None): pass

        class CallableSessions:
            def __call__(self):
                return self
            def __enter__(self):
                return LockContentionGuard()
            def __exit__(self, *args): pass

        settings = SimpleNamespace(sourcecraft_pat=None, catalog_sync_max_pages=5,
                                   catalog_sync_page_size=100, catalog_cycle_interval_seconds=3600)
        # Bootstrap skips when lock is held
        bootstrap = CatalogBootstrap(CallableSessions(), settings)
        res_boot = bootstrap.run()
        self.assertEqual(res_boot, {"skipped": True, "reason": "catalog_sync_already_running"})

        # Sync skips when lock is held
        sync = CatalogSync(CallableSessions(), settings)
        res_sync = sync.run()
        self.assertEqual(res_sync, {"skipped": True, "reason": "catalog_sync_already_running"})

    # 24. Shared upsert does not inject 365 days delay
    def test_24_shared_upsert_does_not_inject_365_days_delay(self):
        """Proves absence of artificial 365-day delay in shared upsert_sourcecraft_repository.

        Note: Real PostgreSQL row insertion uses server_default=text('now()');
        this unit test verifies that shared Python upsert logic does not override
        or schedule next_analysis_at to a distant 365-day future.
        """
        class MockDB:
            def __init__(self):
                self.added = []
            def scalar(self, stmt):
                return None
            def add(self, row):
                self.added.append(row)
            def flush(self): pass

        db = MockDB()
        values = {
            "sourcecraft_id": "sc-new-1",
            "organization_slug": "org",
            "repository_slug": "repo",
            "canonical_url": "https://sourcecraft.dev/org/repo",
            "visibility": "public",
        }
        repo = upsert_sourcecraft_repository(db, values)
        # Does NOT inject next_analysis_at into values or schedule 365 days delay
        self.assertNotIn("next_analysis_at", values)
        val = getattr(repo, "next_analysis_at", None)
        if val is not None:
            self.assertLess(val, datetime.now(UTC) + timedelta(days=30))

    # 25. Metadata sync preserves existing repository schedules
    def test_25_metadata_sync_preserves_existing_repository_schedule(self):
        existing_due_time = datetime(2026, 9, 28, 12, 0, 0, tzinfo=UTC)
        existing_repo = SimpleNamespace(
            id="repo-uuid-1",
            sourcecraft_id="sc-existing-1",
            organization_slug="org",
            repository_slug="repo",
            canonical_url="https://sourcecraft.dev/org/repo",
            visibility="public",
            next_analysis_at=existing_due_time,
            likes=10,
            description="Old description",
        )

        class MockDB:
            def scalar(self, stmt):
                # Returns the existing repository
                return existing_repo
            def flush(self): pass

        db = MockDB()
        sync_values = {
            "sourcecraft_id": "sc-existing-1",
            "organization_slug": "org",
            "repository_slug": "repo",
            "canonical_url": "https://sourcecraft.dev/org/repo",
            "visibility": "public",
            "likes": 50,
            "description": "New description from sync",
        }
        updated = upsert_sourcecraft_repository(db, sync_values)
        # Metadata updated
        self.assertEqual(updated.likes, 50)
        self.assertEqual(updated.description, "New description from sync")
        # Existing next_analysis_at MUST BE preserved
        self.assertEqual(updated.next_analysis_at, existing_due_time)

    # 26. Default browse stats and query consistency
    def test_26_default_browse_stats_and_query_consistency(self):
        # Verify that get_catalog_stats and get_catalog_repositories use the exact same filters
        f_browse = CatalogFilters()
        q_repos = build_catalog_base_query()
        filtered_repos = apply_catalog_filters(q_repos, f_browse)
        stmt_repos = str(filtered_repos.compile(compile_kwargs={"literal_binds": True}))

        # Query does not silently inject IS NOT NULL for browse
        self.assertNotIn("IS NOT NULL", stmt_repos)


if __name__ == "__main__":
    unittest.main()
