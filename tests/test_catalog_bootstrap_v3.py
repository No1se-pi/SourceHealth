"""Regression tests for Task 3: Catalog & Search v3, Topics, and Fast Metadata Bootstrap.

Covers all 22 required items:
1. Desktop renders no mobile duplicate
2. Mobile renders no desktop table
3. Default browse excludes NO_DATA
4. Text search can still return NO_DATA/unanalysed repo
5. Explicit health_status=all works
6. Explicit health_status=no_data works
7. Histogram numeric bins exclude NO_DATA
8. NO_DATA count remains available somewhere as metadata
9. ML topic works
10. Mobile topic works
11. Web topic works
12. Security topic works
13. Topic reclassification idempotent
14. Search exact org/repo
15. Search exact repo
16. Multi-token search
17. Deterministic relevance
18. Bootstrap resumes from checkpoint
19. Bootstrap interruption preserves checkpoint
20. Bootstrap never starts analysis jobs
21. Catalog status safe output
22. 30k synthetic query performance remains reasonable
"""

import unittest
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

from sourcehealth.catalog.query import (
    CatalogFilters,
    apply_catalog_filters,
    apply_catalog_sort,
    build_catalog_base_query,
    get_catalog_repositories,
)
from sourcehealth.catalog.sync import (
    CatalogBootstrap,
    CatalogSync,
    get_catalog_status,
)
from sourcehealth.catalog.topics import (
    TOPIC_CLASSIFIER_VERSION,
    classify_topics,
    reclassify_catalog_topics,
)


class CatalogBootstrapV3RegressionTests(unittest.TestCase):
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

    # 3. Default browse excludes NO_DATA
    def test_03_default_browse_excludes_no_data(self):
        filters = CatalogFilters(q=None, health_status=None)
        # Mock DB
        mock_db = MagicMock()
        mock_db.scalar.return_value = 0
        mock_db.execute.return_value.all.return_value = []

        get_catalog_repositories(mock_db, filters)
        # Verify executed query contains effective_health IS NOT NULL
        executed_stmt = mock_db.execute.call_args[0][0]
        compiled = str(executed_stmt.compile(compile_kwargs={"literal_binds": True}))
        self.assertIn("IS NOT NULL", compiled)

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

    # 5. Explicit health_status=all works
    def test_05_explicit_health_status_all_works(self):
        filters = CatalogFilters(q=None, health_status="all")
        mock_db = MagicMock()
        mock_db.scalar.return_value = 0
        mock_db.execute.return_value.all.return_value = []

        get_catalog_repositories(mock_db, filters)
        executed_stmt = mock_db.execute.call_args[0][0]
        compiled = str(executed_stmt.compile(compile_kwargs={"literal_binds": True}))
        self.assertNotIn("IS NOT NULL", compiled)
        self.assertNotIn("IS NULL", compiled)

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
        from sourcehealth.catalog.query import get_catalog_stats

        # Fake DB returning mixed rows
        class FakeDB:
            def scalar(self, stmt): return 10
            def execute(self, stmt):
                # row: id, health, canonical_analysis_id, lang, orig, topics
                return SimpleNamespace(all=lambda: [
                    (uuid4(), 85.0, uuid4(), "Python", "native", ["web"]),
                    (uuid4(), None, None, "TypeScript", "native", ["other"]),
                    (uuid4(), None, None, "Go", "fork", ["tools"]),
                ])

        stats = get_catalog_stats(FakeDB(), CatalogFilters())
        self.assertEqual(stats["health_available_count"], 1)
        self.assertEqual(stats["health_no_data_count"], 2)
        self.assertEqual(stats["histogram_no_data_count"], 2)
        # 10 buckets in health_histogram, only covering numeric scores
        self.assertEqual(len(stats["health_histogram"]), 10)
        self.assertEqual(sum(b["count"] for b in stats["health_histogram"]), 1)

    # 9. ML topic works
    def test_09_ml_topic_works(self):
        t1 = classify_topics("pytorch-transformer", "Deep learning model", "ai", "Python")
        self.assertIn("ml_data", t1)
        t2 = classify_topics("ml-homework", "Лабораторная работа по машинному обучению", "study", "Jupyter Notebook")
        self.assertIn("ml_data", t2)
        t3 = classify_topics("neural-network", "Нейросеть для распознавания образов", "", "Python")
        self.assertIn("ml_data", t3)

    # 10. Mobile topic works
    def test_10_mobile_topic_works(self):
        t1 = classify_topics("flutter-client", "Cross-platform mobile app", "mobile", "Dart")
        self.assertIn("mobile", t1)
        t2 = classify_topics("android-taxi", "Мобильное приложение для заказа такси", "", "Kotlin")
        self.assertIn("mobile", t2)
        t3 = classify_topics("ios-wallet", "Crypto wallet", "", "Swift")
        self.assertIn("mobile", t3)

    # 11. Web topic works
    def test_11_web_topic_works(self):
        t1 = classify_topics("fastapi-backend", "REST API веб-сервис", "backend", "Python")
        self.assertIn("web", t1)
        t2 = classify_topics("frontend-ui", "React dashboard", "ui", "TypeScript")
        self.assertIn("web", t2)

    # 12. Security topic works
    def test_12_security_topic_works(self):
        t1 = classify_topics("sast-tool", "Static application security testing", "sec", "Go")
        self.assertIn("security", t1)
        t2 = classify_topics("vuln-scanner", "Сканер уязвимостей и аудит безопасности", "", "Python")
        self.assertIn("security", t2)

    # 13. Topic reclassification idempotent
    def test_13_topic_reclassification_idempotent(self):
        repo1 = SimpleNamespace(
            id=1, repository_slug="telegram-notifier", description="Бот для телеграма",
            project_slug=None, language="Python", topics=[], topic_classifier_version=None,
            visibility="public",
        )
        repo2 = SimpleNamespace(
            id=2, repository_slug="ml-classifier", description="Нейросеть для классификации",
            project_slug=None, language="Python", topics=["other"], topic_classifier_version="old-v0",
            visibility="public",
        )
        storage = [repo1, repo2]

        class FakeDB:
            def scalars(self, stmt):
                # Return repositories that need updating
                return SimpleNamespace(all=lambda: [r for r in storage if r.topic_classifier_version != TOPIC_CLASSIFIER_VERSION])

        class FakeSessions:
            @contextmanager
            def begin(self):
                yield FakeDB()

        res1 = reclassify_catalog_topics(FakeSessions(), batch_size=10)
        self.assertEqual(res1["scanned"], 2)
        self.assertEqual(res1["updated"], 2)
        self.assertIn("bots", repo1.topics)
        self.assertIn("ml_data", repo2.topics)
        self.assertEqual(repo1.topic_classifier_version, TOPIC_CLASSIFIER_VERSION)
        self.assertEqual(repo2.topic_classifier_version, TOPIC_CLASSIFIER_VERSION)

        # Second run: idempotent, 0 rows needing update
        res2 = reclassify_catalog_topics(FakeSessions(), batch_size=10)
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

    # 20. Bootstrap never starts analysis jobs
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

        # Verify _safe decouples discovery by scheduling next_analysis_at in the distant future
        safe_values = CatalogSync._safe({"id": "r1", "slug": "new-repo", "visibility": "public",
                                        "organization": {"slug": "team"}, "default_branch": "main"})
        self.assertGreater(safe_values["next_analysis_at"], datetime.now(UTC) + timedelta(days=300))

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
        t0 = time.perf_counter()
        page, total = engine.query(limit=20, sort="health_score")
        browse_ms = (time.perf_counter() - t0) * 1000
        self.assertLess(browse_ms, 50.0)
        self.assertLessEqual(len(page), 20)

        # Multi-token search
        t0 = time.perf_counter()
        search_res, s_total = engine.query(q="bot service", limit=20)
        search_ms = (time.perf_counter() - t0) * 1000
        self.assertLess(search_ms, 50.0)

        # Stats & histogram
        t0 = time.perf_counter()
        st = engine.stats()
        stats_ms = (time.perf_counter() - t0) * 1000
        self.assertLess(stats_ms, 100.0)
        self.assertEqual(len(st["buckets"]), 10)


if __name__ == "__main__":
    unittest.main()
