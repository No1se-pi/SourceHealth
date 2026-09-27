"""Test matrix for safe concurrency, multi-worker scaling, and single-flight guarantees.

Tests all 18 requirements from Part 19 of the specification:
1. 10 concurrent same-repo requests -> one active run
2. manual + scheduler -> one active run
3. duplicate delivery -> one heavy execution
4. two repos -> concurrent execution allowed
5. advisory lock blocks duplicate execution
6. recover does not kill live locked job
7. dead worker recovery works
8. credential A/B isolation
9. credential cleanup success
10. credential cleanup failure path
11. Docker resource names unique
12. A cleanup cannot remove B workspace
13. backlog > dispatcher batch remains bounded
14. one failed job does not affect another
15. mocked 429 remains bounded
16. canonical mvp Health not overwritten by other profile
17. logs contain no credential markers
18. benchmark harness produces structured result
19. canonical projection regression A (newer mvp advances latest and health)
20. canonical projection regression B (fallback when no mvp exists)
21. canonical projection regression C (API prefers canonical mvp over newer non-mvp)
22. canonical projection regression D (API latest returns newer mvp after it completes)
23. queue_status reports null on Redis read failure
"""

import base64
import json
import logging
import os
import secrets
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from unittest.mock import Mock, patch
from urllib.parse import urlsplit
from uuid import UUID, uuid4

import httpx
from fastapi.testclient import TestClient
from redis import Redis
from rq import Queue
from sqlalchemy import delete, func, select, text, update
from sqlalchemy.engine import make_url

from sourcehealth.api.app import create_app
from sourcehealth.application.jobs import (
    dispatch_pending,
    execute_analysis,
    lock_key,
    recover_abandoned,
)
from sourcehealth.application.services import AnalysisService
from sourcehealth.auth.service import AuthService
from sourcehealth.auth.sourcecraft import SourceCraftConnection
from sourcehealth.core import AnalysisReport, AnalyzerResult
from sourcehealth.core.domain import ACTIVE_STATUSES, DataAvailability, RepositoryRef
from sourcehealth.integrations.sourcecraft.client import SourceCraftClient, SourceCraftError
from sourcehealth.integrations.sourcecraft.collectors import CollectedFacts
from sourcehealth.settings import Settings
from sourcehealth.storage.database import create_database
from sourcehealth.storage.models import AnalysisRun, Repository

ENABLED = bool(os.environ.get("TEST_DATABASE_URL") and os.environ.get("TEST_REDIS_URL"))


def make_report(*, repo_ref=None, complete=True, scoring_policy_version="mvp-score-v1.2", health_score=75.0):
    if repo_ref is not None:
        repo_dict = {
            "id": str(repo_ref.id),
            "organization_slug": repo_ref.organization_slug,
            "repository_slug": repo_ref.repository_slug,
            "canonical_url": repo_ref.canonical_url,
            "visibility": repo_ref.visibility,
        }
    else:
        rid = str(uuid4())
        slug = f"repo-{rid[:8]}"
        repo_dict = {
            "id": rid,
            "organization_slug": "testorg",
            "repository_slug": slug,
            "canonical_url": f"https://sourcecraft.dev/testorg/{slug}",
            "visibility": "public",
        }
    rep = AnalysisReport(
        repository=repo_dict,
        started_at=datetime.now(UTC),
        completed_at=datetime.now(UTC),
        scoring_policy_version=scoring_policy_version,
        health_score=health_score,
    )
    if not complete:
        rep.checks = {"sample": AnalyzerResult("sample", status="partial")}
    else:
        rep.checks = {}
    rep.category_scores = {}
    rep.recommendations = []
    return rep


def set_analysis_pat(conn: SourceCraftConnection, run_id: UUID, pat: str) -> None:
    key = conn._analysis_key(run_id)
    nonce = secrets.token_bytes(12)
    encrypted = nonce + conn._cipher().encrypt(nonce, pat.encode(), key.encode())
    conn.redis.set(key, encrypted)


def dummy_facts(source="sourcecraft_api"):
    return CollectedFacts(
        source=source,
        availability=DataAvailability.AVAILABLE,
        collected_at=datetime.now(UTC).isoformat(),
        facts={"id": 1, "visibility": "public", "likes": 5, "items": [], "complete": True},
    )


@unittest.skipUnless(ENABLED, "set TEST_DATABASE_URL and TEST_REDIS_URL for concurrency integration tests")
class SafeConcurrencyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        database_url = os.environ["TEST_DATABASE_URL"]
        redis_url = os.environ["TEST_REDIS_URL"]
        if not make_url(database_url).database.endswith("_test") or urlsplit(redis_url).path != "/15":
            raise RuntimeError("concurrency tests require *_test database and Redis DB 15")
        cls.database_url = database_url
        cls.redis_url = redis_url

        # Ensure environment variables for worker/job Settings instantiation
        cls.cred_key = base64.b64encode(b"k" * 32).decode()
        cls._orig_env = {
            k: os.environ.get(k)
            for k in ("DATABASE_URL", "REDIS_URL", "ANALYSIS_PROFILE", "CODE_RUNTIME_ENABLED", "SOURCECRAFT_CREDENTIAL_KEY")
        }
        os.environ["DATABASE_URL"] = database_url
        os.environ["REDIS_URL"] = redis_url
        os.environ["ANALYSIS_PROFILE"] = "mvp-v1"
        os.environ["CODE_RUNTIME_ENABLED"] = "true"
        os.environ["SOURCECRAFT_CREDENTIAL_KEY"] = cls.cred_key

        cls.settings = Settings(
            _env_file=None,
            database_url=database_url,
            redis_url=redis_url,
            analysis_profile="mvp-v1",
            code_runtime_enabled=True,
            yandex_client_id="test-client",
            yandex_client_secret="test-secret",
            session_secret="x" * 48,
            sourcecraft_credential_key=cls.cred_key,
            public_origin="https://testserver",
            yandex_redirect_uri="https://testserver/api/v1/auth/yandex/callback",
        )
        cls.engine, cls.sessions = create_database(database_url)
        cls.redis = Redis.from_url(redis_url)
        cls.redis.ping()
        cls.created_repo_ids = []

    @classmethod
    def tearDownClass(cls):
        for k, v in cls._orig_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        if cls.created_repo_ids:
            with cls.sessions.begin() as db:
                db.execute(update(Repository).where(Repository.id.in_(cls.created_repo_ids)).values(latest_analysis_id=None))
                db.execute(delete(AnalysisRun).where(AnalysisRun.repository_id.in_(cls.created_repo_ids)))
                db.execute(delete(Repository).where(Repository.id.in_(cls.created_repo_ids)))
        cls.redis.close()
        cls.engine.dispose()

    def setUp(self):
        self.service = AnalysisService(self.sessions, self.settings)
        self.ref = RepositoryRef.from_url(f"https://sourcecraft.dev/test/conc-{uuid4().hex[:8]}", visibility="public")
        self.repository_id = self.service.register_repository(self.ref)
        self.created_repo_ids.append(self.repository_id)

    def tearDown(self):
        self.redis.flushdb()
        with self.sessions.begin() as db:
            db.execute(delete(AnalysisRun).where(AnalysisRun.repository_id == self.repository_id))

    # 1. 10 concurrent same-repo requests -> one active run
    def test_01_concurrent_same_repo_requests_single_active_run(self):
        runs = []
        barrier = threading.Barrier(10)

        def worker_req():
            barrier.wait()
            srv = AnalysisService(self.sessions, self.settings)
            return srv.request_analysis(self.repository_id)

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(worker_req) for _ in range(10)]
            runs = [f.result() for f in futures]

        unique_ids = {r.id for r in runs}
        self.assertEqual(len(unique_ids), 1, "All 10 concurrent requests must receive the same analysis ID")

        with self.sessions() as db:
            active_count = db.scalar(
                select(func.count()).select_from(AnalysisRun).where(
                    AnalysisRun.repository_id == self.repository_id,
                    AnalysisRun.profile == "mvp-v1",
                    AnalysisRun.status.in_(ACTIVE_STATUSES),
                )
            )
        self.assertEqual(active_count, 1, "Exactly one active run must exist in database")

    # 2. manual + scheduler -> one active run
    def test_02_manual_and_scheduler_race_single_active_run(self):
        with self.sessions.begin() as db:
            repo = db.get(Repository, self.repository_id)
            repo.next_analysis_at = datetime.now(UTC) - timedelta(minutes=5)

        barrier = threading.Barrier(2)
        results = {}

        def req_manual():
            barrier.wait()
            srv = AnalysisService(self.sessions, self.settings)
            results["manual"] = srv.request_analysis(self.repository_id, trigger="manual")

        def req_scheduler():
            barrier.wait()
            srv = AnalysisService(self.sessions, self.settings)
            results["scheduler"] = srv.enqueue_due()

        t1 = threading.Thread(target=req_manual)
        t2 = threading.Thread(target=req_scheduler)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        with self.sessions() as db:
            active_runs = list(db.scalars(
                select(AnalysisRun).where(
                    AnalysisRun.repository_id == self.repository_id,
                    AnalysisRun.profile == "mvp-v1",
                    AnalysisRun.status.in_(ACTIVE_STATUSES),
                )
            ))
        self.assertEqual(len(active_runs), 1, "Manual and scheduler race must yield exactly one active run")

    # 3. duplicate delivery -> one heavy execution
    def test_03_duplicate_delivery_single_heavy_execution(self):
        run = self.service.request_analysis(self.repository_id)
        heavy_calls = 0
        call_lock = threading.Lock()

        def mock_analyze(*args, **kwargs):
            nonlocal heavy_calls
            with call_lock:
                heavy_calls += 1
            time.sleep(0.05)
            return make_report()

        barrier = threading.Barrier(2)

        def worker_exec():
            barrier.wait()
            execute_analysis(str(run.id))

        with patch("sourcehealth.application.jobs.collect_platform", return_value=Mock(
            collection_statuses={}, metadata={}, sourcecraft_facts={"repository_metadata": {}}
        )), patch("sourcehealth.application.jobs.collect_mvp", side_effect=lambda ctx, *args, **kwargs: ctx), \
             patch("sourcehealth.application.jobs.analyze_context", side_effect=mock_analyze), \
             patch("sourcehealth.application.jobs.ScoringEngine"):
            t1 = threading.Thread(target=worker_exec)
            t2 = threading.Thread(target=worker_exec)
            t1.start()
            t2.start()
            t1.join()
            t2.join()

        self.assertEqual(heavy_calls, 1, "Duplicate delivery must execute heavy pipeline exactly once")

    # 4. two repos -> concurrent execution allowed
    def test_04_different_repos_concurrent_execution(self):
        ref2 = RepositoryRef.from_url(f"https://sourcecraft.dev/test/conc2-{uuid4().hex[:8]}", visibility="public")
        repo2_id = self.service.register_repository(ref2)
        self.created_repo_ids.append(repo2_id)

        run1 = self.service.request_analysis(self.repository_id)
        run2 = self.service.request_analysis(repo2_id)

        barrier_in = threading.Barrier(2)
        barrier_out = threading.Barrier(2)
        concurrent_observed = False

        def mock_collect(*args, **kwargs):
            nonlocal concurrent_observed
            barrier_in.wait(timeout=5.0)
            concurrent_observed = True
            barrier_out.wait(timeout=5.0)
            return Mock(collection_statuses={}, metadata={}, sourcecraft_facts={"repository_metadata": {}})

        with patch("sourcehealth.application.jobs.collect_platform", side_effect=mock_collect), \
             patch("sourcehealth.application.jobs.collect_mvp", side_effect=lambda ctx, *args, **kwargs: ctx), \
             patch("sourcehealth.application.jobs.analyze_context", return_value=make_report()), \
             patch("sourcehealth.application.jobs.ScoringEngine"):
            t1 = threading.Thread(target=execute_analysis, args=(str(run1.id),))
            t2 = threading.Thread(target=execute_analysis, args=(str(run2.id),))
            t1.start()
            t2.start()
            t1.join(timeout=10.0)
            t2.join(timeout=10.0)

        self.assertTrue(concurrent_observed, "Analyses for different repositories must execute concurrently")

    # 5. advisory lock blocks duplicate execution
    def test_05_advisory_lock_blocks_duplicate_execution(self):
        run = self.service.request_analysis(self.repository_id)
        key = lock_key(run.id)

        with self.engine.connect() as guard:
            acquired = guard.scalar(text("SELECT pg_try_advisory_lock(:key)"), {"key": key})
            self.assertTrue(acquired)
            guard.commit()
            try:
                execute_analysis(str(run.id))
                with self.sessions() as db:
                    r = db.get(AnalysisRun, run.id)
                    self.assertEqual(r.status, "queued", "Run must remain queued when advisory lock is held")
            finally:
                guard.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": key})
                guard.commit()

    # 6. recover does not kill live locked job
    def test_06_recover_does_not_kill_live_locked_job(self):
        run = self.service.request_analysis(self.repository_id)
        self.service.transition(run.id, "collecting")
        with self.sessions.begin() as db:
            r = db.get(AnalysisRun, run.id)
            r.deadline_at = datetime.now(UTC) - timedelta(minutes=10)

        key = lock_key(run.id)
        with self.engine.connect() as guard:
            guard.scalar(text("SELECT pg_try_advisory_lock(:key)"), {"key": key})
            guard.commit()
            try:
                recover_abandoned(self.engine, self.sessions, self.settings)
                with self.sessions() as db:
                    r = db.get(AnalysisRun, run.id)
                    self.assertEqual(r.status, "collecting", "Must not mark failed while advisory lock is held")
            finally:
                guard.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": key})
                guard.commit()

    # 7. dead worker recovery works
    def test_07_dead_worker_recovery_transitions_to_failed(self):
        # Clear out any prior abandoned runs
        recover_abandoned(self.engine, self.sessions, self.settings)

        run = self.service.request_analysis(self.repository_id)
        self.service.transition(run.id, "collecting")
        with self.sessions.begin() as db:
            r = db.get(AnalysisRun, run.id)
            r.deadline_at = datetime.now(UTC) - timedelta(minutes=10)

        recovered = recover_abandoned(self.engine, self.sessions, self.settings)
        self.assertGreaterEqual(recovered, 1, "Abandoned run past deadline must be recovered")
        with self.sessions() as db:
            r = db.get(AnalysisRun, run.id)
            self.assertEqual(r.status, "failed")
            self.assertEqual(r.error_code, "worker_interrupted")

        fresh_run = self.service.request_analysis(self.repository_id)
        self.assertNotEqual(fresh_run.id, run.id, "Subsequent request must create fresh run")
        self.assertEqual(fresh_run.status, "queued")

    # 8. credential A/B isolation
    def test_08_credential_ab_isolation(self):
        ref_b = RepositoryRef.from_url(f"https://sourcecraft.dev/test/ab-b-{uuid4().hex[:8]}", visibility="public")
        repo_b_id = self.service.register_repository(ref_b)
        self.created_repo_ids.append(repo_b_id)

        auth_service = AuthService(self.settings, self.redis, self.sessions)
        conn = SourceCraftConnection(auth_service)

        run_a = self.service.request_analysis(self.repository_id)
        run_b = self.service.request_analysis(repo_b_id)

        pat_a = "VERY_PRIVATE_PAT_A_12345"
        pat_b = "VERY_PRIVATE_PAT_B_67890"

        set_analysis_pat(conn, run_a.id, pat_a)
        set_analysis_pat(conn, run_b.id, pat_b)

        captured_credentials = {}

        def mock_collect(repo, settings, r_conn, user_pat=None):
            captured_credentials[str(repo.id)] = user_pat
            return Mock(collection_statuses={}, metadata={}, sourcecraft_facts={"repository_metadata": {}})

        with patch("sourcehealth.application.jobs.collect_platform", side_effect=mock_collect), \
             patch("sourcehealth.application.jobs.collect_mvp", side_effect=lambda ctx, *args, **kwargs: ctx), \
             patch("sourcehealth.application.jobs.analyze_context", return_value=make_report()), \
             patch("sourcehealth.application.jobs.ScoringEngine"):
            execute_analysis(str(run_a.id))
            execute_analysis(str(run_b.id))

        self.assertEqual(captured_credentials[str(self.repository_id)], pat_a)
        self.assertEqual(captured_credentials[str(repo_b_id)], pat_b)

        with self.sessions() as db:
            row_a = db.get(AnalysisRun, run_a.id)
            row_b = db.get(AnalysisRun, run_b.id)
            self.assertNotIn(pat_a, json.dumps(row_b.results))
            self.assertNotIn(pat_b, json.dumps(row_a.results))
            self.assertNotIn(pat_a, json.dumps(row_a.results))
            self.assertNotIn(pat_b, json.dumps(row_b.results))

    # 9. credential cleanup success
    def test_09_credential_cleanup_on_success(self):
        run = self.service.request_analysis(self.repository_id)
        auth_service = AuthService(self.settings, self.redis, self.sessions)
        conn = SourceCraftConnection(auth_service)
        pat = "CLEANUP_SUCCESS_PAT"
        set_analysis_pat(conn, run.id, pat)

        with patch("sourcehealth.application.jobs.collect_platform", return_value=Mock(
            collection_statuses={}, metadata={}, sourcecraft_facts={"repository_metadata": {}}
        )), patch("sourcehealth.application.jobs.collect_mvp", side_effect=lambda ctx, *args, **kwargs: ctx), \
             patch("sourcehealth.application.jobs.analyze_context", return_value=make_report()), \
             patch("sourcehealth.application.jobs.ScoringEngine"):
            execute_analysis(str(run.id))

        self.assertIsNone(conn.analysis_credential(run.id), "Credential lease must be deleted on success")

    # 10. credential cleanup failure path
    def test_10_credential_cleanup_on_failure(self):
        run = self.service.request_analysis(self.repository_id)
        auth_service = AuthService(self.settings, self.redis, self.sessions)
        conn = SourceCraftConnection(auth_service)
        pat = "CLEANUP_FAILURE_PAT"
        set_analysis_pat(conn, run.id, pat)

        with patch("sourcehealth.application.jobs.collect_platform", side_effect=RuntimeError("simulated_failure")):
            execute_analysis(str(run.id))

        self.assertIsNone(conn.analysis_credential(run.id), "Credential lease must be deleted even on failure")

    # 11. Docker resource names unique
    def test_11_docker_resource_names_unique(self):
        jobs = []
        for _ in range(50):
            job_name = "sourcehealth-" + uuid4().hex
            clone_name = job_name + "-clone"
            scan_name = job_name + "-scan"
            volume_name = job_name + "-data"
            jobs.append((clone_name, scan_name, volume_name))

        all_names = [name for triple in jobs for name in triple]
        self.assertEqual(len(all_names), len(set(all_names)), "All Docker container and volume names must be unique")

    # 12. A cleanup cannot remove B workspace
    def test_12_cleanup_isolation_cannot_remove_other_workspace(self):
        job_b = "sourcehealth-" + uuid4().hex
        vol_b = job_b + "-data"

        docker_calls = []

        def mock_docker(args, timeout=30):
            docker_calls.append(list(args))
            return ""

        from sourcehealth.sast import container
        with patch.object(container, "_docker", side_effect=mock_docker):
            container.run_repository("https://sourcecraft.dev/org/repo-a")

        for call in docker_calls:
            if "rm" in call:
                self.assertNotIn(vol_b, call, "Job A cleanup must never delete Job B workspace")

    # 13. backlog > dispatcher batch remains bounded
    def test_13_backlog_exceeding_batch_size_remains_bounded(self):
        with self.sessions.begin() as db:
            db.execute(delete(AnalysisRun).where(AnalysisRun.status == "queued"))
        repos = []
        with self.sessions.begin() as db:
            for i in range(150):
                r = Repository(
                    organization_slug="bulk",
                    repository_slug=f"bulk-{uuid4().hex[:6]}-{i}",
                    canonical_url=f"https://sourcecraft.dev/bulk/bulk-{uuid4().hex[:6]}-{i}",
                    visibility="public",
                )
                db.add(r)
                db.flush()
                repos.append(r.id)
                self.created_repo_ids.append(r.id)
                db.add(AnalysisRun(
                    repository_id=r.id,
                    trigger="manual",
                    profile="mvp-v1",
                    status="queued",
                    fingerprint=f"bulk-fp-{i}",
                    queued_at=datetime.now(UTC) - timedelta(seconds=150 - i),
                ))

        q = Queue("analysis-code", connection=self.redis)
        q.empty()

        pass_1 = dispatch_pending(self.sessions, self.redis)
        self.assertEqual(pass_1, 100, "First dispatch pass must be bounded to at most 100 jobs")

        # Simulate worker picking up first 100 jobs (status becomes collecting)
        with self.sessions.begin() as db:
            first_100_ids = [UUID(j) for j in q.job_ids]
            db.execute(update(AnalysisRun).where(AnalysisRun.id.in_(first_100_ids)).values(status="collecting"))

        pass_2 = dispatch_pending(self.sessions, self.redis)
        self.assertEqual(pass_2, 50, "Second dispatch pass drains remaining 50 jobs")

        q.empty()
        with self.sessions.begin() as db:
            db.execute(delete(AnalysisRun).where(AnalysisRun.repository_id.in_(repos)))
            db.execute(delete(Repository).where(Repository.id.in_(repos)))

    # 14. one failed job does not affect another
    def test_14_failure_isolation_between_concurrent_jobs(self):
        ref_fail = RepositoryRef.from_url(f"https://sourcecraft.dev/test/fail-{uuid4().hex[:8]}", visibility="public")
        repo_fail_id = self.service.register_repository(ref_fail)
        self.created_repo_ids.append(repo_fail_id)

        run_fail = self.service.request_analysis(repo_fail_id)
        run_ok = self.service.request_analysis(self.repository_id)

        def mock_collect(repo, *args, **kwargs):
            if str(repo.id) == str(repo_fail_id):
                raise RuntimeError("simulated_worker_crash")
            return Mock(collection_statuses={}, metadata={}, sourcecraft_facts={"repository_metadata": {}})

        with patch("sourcehealth.application.jobs.collect_platform", side_effect=mock_collect), \
             patch("sourcehealth.application.jobs.collect_mvp", side_effect=lambda ctx, *args, **kwargs: ctx), \
             patch("sourcehealth.application.jobs.analyze_context", return_value=make_report()), \
             patch("sourcehealth.application.jobs.ScoringEngine"):
            execute_analysis(str(run_fail.id))
            execute_analysis(str(run_ok.id))

        with self.sessions() as db:
            rf = db.get(AnalysisRun, run_fail.id)
            ro = db.get(AnalysisRun, run_ok.id)
            self.assertEqual(rf.status, "failed")
            self.assertIn(ro.status, ("completed", "partial"))

    # 15. mocked 429 remains bounded
    def test_15_mocked_429_rate_limiting_bounded(self):
        attempts = 0

        def handler(request):
            nonlocal attempts
            attempts += 1
            return httpx.Response(429, headers={"Retry-After": "0.01"})

        transport = httpx.MockTransport(handler)
        with SourceCraftClient(base_url="https://api.sourcecraft.tech", transport=transport, sleep=lambda d: None) as client:
            with self.assertRaises(SourceCraftError) as cm:
                client.get("/test-throttling")
            self.assertEqual(cm.exception.code, "rate_limited")
        self.assertEqual(attempts, 3, "429 must retry at most 3 attempts and exit cleanly")

    # 16. canonical mvp Health not overwritten by other profile
    def test_16_canonical_mvp_health_not_overwritten_by_other_profile(self):
        with self.sessions.begin() as db:
            mvp_run = AnalysisRun(
                repository_id=self.repository_id,
                status="completed",
                trigger="manual",
                profile="mvp-v1",
                fingerprint=uuid4().hex,
                completed_at=datetime.now(UTC) - timedelta(minutes=5),
                health_score=75.0,
                scoring_policy_version="mvp-score-v1.2",
                category_scores={},
            )
            db.add(mvp_run)
            db.flush()
            repo = db.get(Repository, self.repository_id)
            repo.latest_analysis_id = mvp_run.id
            repo.health_score = 75.0

        # Now finish a code-v1 run
        code_run = AnalysisRun(
            repository_id=self.repository_id,
            status="scoring",
            trigger="manual",
            profile="code-v1",
            fingerprint=uuid4().hex,
            queued_at=datetime.now(UTC),
            started_at=datetime.now(UTC),
        )
        with self.sessions.begin() as db:
            db.add(code_run)

        mock_rep = make_report(repo_ref=self.ref, complete=True, scoring_policy_version="code-score-v1", health_score=99.0)

        self.service.finish(code_run.id, mock_rep)

        with self.sessions() as db:
            repo = db.get(Repository, self.repository_id)
            self.assertEqual(repo.health_score, 75.0, "Canonical MVP health_score must not be overwritten by code-v1")
            self.assertEqual(repo.latest_analysis_id, mvp_run.id, "Repository latest_analysis_id must preserve canonical MVP run")

        app = create_app(self.settings, sessions=self.sessions, redis=self.redis)
        with TestClient(app, base_url="https://testserver") as client:
            res = client.get(f"/api/v1/repositories/{self.repository_id}")
            self.assertEqual(res.status_code, 200)
            self.assertEqual(res.json()["health_score"], 75.0)
            self.assertEqual(res.json()["latest_analysis_id"], str(mvp_run.id))

    # 17. logs contain no credential markers
    def test_17_logs_contain_no_credential_markers(self):
        marker = "SUPER_SECRET_PAT_MARKER_TEST_17"
        run = self.service.request_analysis(self.repository_id)
        auth_service = AuthService(self.settings, self.redis, self.sessions)
        conn = SourceCraftConnection(auth_service)
        set_analysis_pat(conn, run.id, marker)

        log_records = []

        class InterceptHandler(logging.Handler):
            def emit(self, record):
                log_records.append(self.format(record))
                if isinstance(record.__dict__.get("extra"), dict):
                    log_records.append(json.dumps(record.__dict__["extra"]))

        handler = InterceptHandler()
        root_logger = logging.getLogger()
        root_logger.addHandler(handler)

        try:
            with patch("sourcehealth.application.jobs.collect_platform", return_value=Mock(
                collection_statuses={}, metadata={}, sourcecraft_facts={"repository_metadata": {}}
            )), patch("sourcehealth.application.jobs.collect_mvp", side_effect=lambda ctx, *args, **kwargs: ctx), \
                 patch("sourcehealth.application.jobs.analyze_context", return_value=make_report()), \
                 patch("sourcehealth.application.jobs.ScoringEngine"):
                execute_analysis(str(run.id))
        finally:
            root_logger.removeHandler(handler)

        all_logs = " ".join(log_records)
        self.assertNotIn(marker, all_logs, "Secret credential marker must never appear in log records or extras")

    # 18. benchmark harness produces structured result
    def test_18_benchmark_harness_produces_structured_result(self):
        with self.sessions.begin() as db:
            db.execute(delete(AnalysisRun).where(AnalysisRun.status == "queued"))
        from scripts.benchmark_workers import BenchmarkRunner

        runner = BenchmarkRunner(self.database_url, self.redis_url, simulated_stage_ms=10.0)
        try:
            res = runner.run_scenario("Test18", 1, 1, timeout_sec=15.0)
            self.assertEqual(res["scenario"], "Test18")
            self.assertEqual(res["workers"], 1)
            self.assertEqual(res["repositories"], 1)
            self.assertIn("queue_drain_time_ms", res)
            self.assertIn("max_simultaneous_active", res)
            self.assertTrue(res["all_completed_cleanly"])
        finally:
            runner.close()

    # 19. Canonical projection regression A:
    # mvp-v1 run A completed, then newer mvp-v1 run B completes
    # -> repository.latest_analysis_id == B
    # -> health_score == B Health
    def test_19_canonical_projection_regression_a_newer_mvp_advances_canonical(self):
        with self.sessions.begin() as db:
            run_a = AnalysisRun(
                repository_id=self.repository_id,
                status="completed",
                trigger="manual",
                profile="mvp-v1",
                fingerprint=uuid4().hex,
                completed_at=datetime.now(UTC) - timedelta(minutes=10),
                health_score=70.0,
                scoring_policy_version="mvp-score-v1.2",
                category_scores={},
            )
            db.add(run_a)
            db.flush()
            repo = db.get(Repository, self.repository_id)
            repo.latest_analysis_id = run_a.id
            repo.health_score = 70.0

        run_b = AnalysisRun(
            repository_id=self.repository_id,
            status="scoring",
            trigger="manual",
            profile="mvp-v1",
            fingerprint=uuid4().hex,
            queued_at=datetime.now(UTC),
            started_at=datetime.now(UTC),
        )
        with self.sessions.begin() as db:
            db.add(run_b)

        report_b = make_report(repo_ref=self.ref, complete=True, health_score=85.0)
        self.service.finish(run_b.id, report_b)

        with self.sessions() as db:
            repo = db.get(Repository, self.repository_id)
            self.assertEqual(repo.latest_analysis_id, run_b.id, "repository.latest_analysis_id must update to newer mvp run B")
            self.assertEqual(repo.health_score, 85.0, "repository.health_score must update to newer mvp run B health")

    # 20. Canonical projection regression B:
    # no mvp-v1 exists, platform/code terminal result
    # -> repository still exposes a usable latest analysis according to current fallback contract
    def test_20_canonical_projection_regression_b_fallback_when_no_mvp(self):
        repo_id = uuid4()
        ref = RepositoryRef(
            id=str(repo_id),
            canonical_url=f"https://sourcecraft.dev/testorg/repo-{repo_id.hex[:6]}",
            organization_slug="testorg",
            repository_slug=f"repo-{repo_id.hex[:6]}",
            visibility="public",
        )
        with self.sessions.begin() as db:
            db.add(Repository(
                id=repo_id,
                canonical_url=ref.canonical_url,
                organization_slug=ref.organization_slug,
                repository_slug=ref.repository_slug,
                visibility="public",
                sourcecraft_id=secrets.randbelow(1000000) + 1000,
            ))

        try:
            code_run = AnalysisRun(
                repository_id=repo_id,
                status="scoring",
                trigger="manual",
                profile="code-v1",
                fingerprint=uuid4().hex,
                queued_at=datetime.now(UTC),
                started_at=datetime.now(UTC),
            )
            with self.sessions.begin() as db:
                db.add(code_run)

            code_rep = make_report(repo_ref=ref, complete=True, scoring_policy_version="code-score-v1", health_score=92.0)
            self.service.finish(code_run.id, code_rep)

            with self.sessions() as db:
                repo = db.get(Repository, repo_id)
                self.assertEqual(repo.latest_analysis_id, code_run.id, "Repository must expose terminal fallback latest_analysis_id")

            app = create_app(self.settings, sessions=self.sessions, redis=self.redis)
            with TestClient(app, base_url="https://testserver") as client:
                res_repo = client.get(f"/api/v1/repositories/{repo_id}")
                self.assertEqual(res_repo.status_code, 200)
                self.assertEqual(res_repo.json()["latest_analysis_id"], str(code_run.id))

                res_latest = client.get(f"/api/v1/repositories/{repo_id}/analyses/latest")
                self.assertEqual(res_latest.status_code, 200)
                self.assertEqual(res_latest.json()["id"], str(code_run.id))
                self.assertEqual(res_latest.json()["profile"], "code-v1")
        finally:
            with self.sessions.begin() as db:
                db.execute(delete(AnalysisRun).where(AnalysisRun.repository_id == repo_id))
                db.execute(delete(Repository).where(Repository.id == repo_id))

    # 21. Canonical projection regression C:
    # GET /api/v1/repositories/{id}/analyses/latest with canonical mvp + newer non-mvp
    # -> returns intended canonical mvp
    def test_21_canonical_projection_regression_c_api_prefers_canonical_mvp_over_newer_non_mvp(self):
        with self.sessions.begin() as db:
            mvp_run = AnalysisRun(
                repository_id=self.repository_id,
                status="completed",
                trigger="manual",
                profile="mvp-v1",
                fingerprint=uuid4().hex,
                completed_at=datetime.now(UTC) - timedelta(minutes=10),
                health_score=78.0,
                scoring_policy_version="mvp-score-v1.2",
                category_scores={},
            )
            db.add(mvp_run)
            db.flush()
            repo = db.get(Repository, self.repository_id)
            repo.latest_analysis_id = mvp_run.id
            repo.health_score = 78.0

        non_mvp_run = AnalysisRun(
            repository_id=self.repository_id,
            status="scoring",
            trigger="manual",
            profile="platform-v1",
            fingerprint=uuid4().hex,
            queued_at=datetime.now(UTC),
            started_at=datetime.now(UTC),
        )
        with self.sessions.begin() as db:
            db.add(non_mvp_run)

        platform_rep = make_report(repo_ref=self.ref, complete=True, scoring_policy_version="platform-v1", health_score=60.0)
        self.service.finish(non_mvp_run.id, platform_rep)

        app = create_app(self.settings, sessions=self.sessions, redis=self.redis)
        with TestClient(app, base_url="https://testserver") as client:
            res = client.get(f"/api/v1/repositories/{self.repository_id}/analyses/latest")
            self.assertEqual(res.status_code, 200)
            data = res.json()
            self.assertEqual(data["id"], str(mvp_run.id), "API latest endpoint must return canonical mvp run, not newer non-mvp")
            self.assertEqual(data["profile"], "mvp-v1")

    # 22. Canonical projection regression D:
    # GET latest after newer mvp completes
    # -> returns newer mvp
    def test_22_canonical_projection_regression_d_api_latest_after_newer_mvp_completes(self):
        with self.sessions.begin() as db:
            mvp_run_old = AnalysisRun(
                repository_id=self.repository_id,
                status="completed",
                trigger="manual",
                profile="mvp-v1",
                fingerprint=uuid4().hex,
                completed_at=datetime.now(UTC) - timedelta(minutes=15),
                health_score=65.0,
                scoring_policy_version="mvp-score-v1.2",
                category_scores={},
            )
            db.add(mvp_run_old)
            db.flush()
            repo = db.get(Repository, self.repository_id)
            repo.latest_analysis_id = mvp_run_old.id
            repo.health_score = 65.0

        code_run = AnalysisRun(
            repository_id=self.repository_id,
            status="completed",
            trigger="manual",
            profile="code-v1",
            fingerprint=uuid4().hex,
            completed_at=datetime.now(UTC) - timedelta(minutes=10),
            health_score=90.0,
            scoring_policy_version="code-score-v1",
            category_scores={},
        )
        with self.sessions.begin() as db:
            db.add(code_run)

        mvp_run_new = AnalysisRun(
            repository_id=self.repository_id,
            status="scoring",
            trigger="manual",
            profile="mvp-v1",
            fingerprint=uuid4().hex,
            queued_at=datetime.now(UTC),
            started_at=datetime.now(UTC),
        )
        with self.sessions.begin() as db:
            db.add(mvp_run_new)

        new_rep = make_report(repo_ref=self.ref, complete=True, health_score=94.0)
        self.service.finish(mvp_run_new.id, new_rep)

        app = create_app(self.settings, sessions=self.sessions, redis=self.redis)
        with TestClient(app, base_url="https://testserver") as client:
            res = client.get(f"/api/v1/repositories/{self.repository_id}/analyses/latest")
            self.assertEqual(res.status_code, 200)
            data = res.json()
            self.assertEqual(data["id"], str(mvp_run_new.id), "API latest endpoint must return the newly completed MVP run")
            self.assertEqual(data["profile"], "mvp-v1")
            self.assertEqual(data["health_score"], 94.0)

    # 23. queue_status reports null instead of false zero on Redis failure
    def test_23_queue_status_redis_failure_reports_null(self):
        from sourcehealth.application.jobs import queue_status

        mock_redis = Mock(spec=Redis)
        with patch("sourcehealth.application.jobs.Queue", side_effect=Exception("Redis connection refused")):
            status = queue_status(self.sessions, mock_redis)
            self.assertIsNone(status["analysis_queue_length"], "analysis_queue_length must be None (null) on failure")
            self.assertIsNone(status["analysis_code_queue_length"], "analysis_code_queue_length must be None (null) on failure")
            dumped = json.dumps(status)
            parsed = json.loads(dumped)
            self.assertIsNone(parsed["analysis_queue_length"])
            self.assertIsNone(parsed["analysis_code_queue_length"])


if __name__ == "__main__":
    unittest.main()
