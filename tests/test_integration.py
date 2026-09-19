"""Настоящие PostgreSQL/Redis, изолированные test DB. Никаких live credentials.

Применить Alembic к БД с суффиксом _test и задать TEST_DATABASE_URL,
TEST_REDIS_URL (Redis DB 15). Обычный unit CI пропускает эти проверки.
"""

import os
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit
from uuid import UUID, uuid4

from tests.test_runtime_pipeline import runtime_fixture

ENABLED = bool(os.environ.get("TEST_DATABASE_URL") and os.environ.get("TEST_REDIS_URL"))

if ENABLED:
    import httpx
    from fastapi.testclient import TestClient
    from redis import Redis
    from rq import Queue, SimpleWorker
    from rq.timeouts import TimerDeathPenalty
    from sqlalchemy import delete, select, text, update
    from sqlalchemy.engine import make_url
    from sqlalchemy.exc import IntegrityError

    from sourcehealth.api.app import create_app
    from sourcehealth.application.jobs import dispatch_pending, execute_analysis, lock_key, recover_abandoned
    from sourcehealth.application.services import AnalysisService
    from sourcehealth.auth.service import AuthService
    from sourcehealth.core import AnalysisContext
    from sourcehealth.core.domain import DataAvailability, RepositoryRef
    from sourcehealth.settings import Settings
    from sourcehealth.storage.database import create_database
    from sourcehealth.storage.models import AnalysisRun, Repository, User


@unittest.skipUnless(ENABLED, "set TEST_DATABASE_URL and TEST_REDIS_URL for PostgreSQL/Redis integration")
class PersistenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        database_url = os.environ["TEST_DATABASE_URL"]
        redis_url = os.environ["TEST_REDIS_URL"]
        if not make_url(database_url).database.endswith("_test") or urlsplit(redis_url).path != "/15":
            raise RuntimeError("integration tests require *_test database and Redis DB 15")
        cls.settings = Settings(_env_file=None, database_url=database_url, redis_url=redis_url,
                               yandex_client_id="test-client", yandex_client_secret="test-secret",
                               session_secret="x" * 48, public_origin="https://testserver",
                               yandex_redirect_uri="https://testserver/api/v1/auth/yandex/callback")
        cls.engine, cls.sessions = create_database(database_url)
        cls.redis = Redis.from_url(redis_url)
        cls.redis.ping()
        with cls.engine.connect() as db:
            if db.scalar(text("select version_num from alembic_version")) != "0001":
                raise RuntimeError("apply Alembic before integration tests")

    @classmethod
    def tearDownClass(cls):
        cls.redis.close()
        cls.engine.dispose()

    def setUp(self):
        self.service = AnalysisService(self.sessions, self.settings)
        self.ref = RepositoryRef.from_url(f"https://sourcecraft.dev/test/repo-{uuid4().hex}", visibility="public")
        self.repository_id = self.service.register_repository(self.ref)

    def tearDown(self):
        with self.sessions.begin() as db:
            ids = list(db.scalars(select(AnalysisRun.id).where(AnalysisRun.repository_id == self.repository_id)))
            db.execute(update(Repository).where(Repository.id == self.repository_id).values(latest_analysis_id=None))
            db.execute(delete(AnalysisRun).where(AnalysisRun.repository_id == self.repository_id))
            db.execute(delete(Repository).where(Repository.id == self.repository_id))
        for run_id in ids:
            Queue("analysis", connection=self.redis).remove(str(run_id))
            Queue("analysis-code", connection=self.redis).remove(str(run_id))
            self.redis.delete(f"rq:job:{run_id}")

    def context(self, repository, settings, redis):
        return AnalysisContext(repository=repository,
            sourcecraft_facts={"repository_metadata": {"visibility": "public", "id": "fixture"}},
            collection_statuses={"repository_metadata": DataAvailability.AVAILABLE, "appsec": DataAvailability.NO_DATA})

    def test_ten_simultaneous_requests_get_one_run_and_one_queue_job(self):
        with ThreadPoolExecutor(max_workers=10) as pool:
            ids = list(pool.map(lambda _: self.service.request_analysis(self.repository_id).id, range(10)))
        self.assertEqual(len(set(ids)), 1)
        with ThreadPoolExecutor(max_workers=5) as pool:
            list(pool.map(lambda _: dispatch_pending(self.sessions, self.redis), range(5)))
        self.assertEqual(Queue("analysis", connection=self.redis).job_ids.count(str(ids[0])), 1)

    def test_database_unique_index_protects_bypass(self):
        run = self.service.request_analysis(self.repository_id)
        with self.assertRaises(IntegrityError), self.sessions.begin() as db:
            db.add(AnalysisRun(repository_id=self.repository_id, trigger="manual", profile=run.profile,
                               fingerprint="a" * 64))
            db.flush()

    def test_queued_row_survives_before_dispatch(self):
        run = self.service.request_analysis(self.repository_id)
        self.assertNotIn(str(run.id), Queue("analysis", connection=self.redis).job_ids)
        dispatch_pending(self.sessions, self.redis)
        self.assertIn(str(run.id), Queue("analysis", connection=self.redis).job_ids)

    def test_worker_persists_public_report_and_cache_reuses_run(self):
        run = self.service.request_analysis(self.repository_id)
        env = {"DATABASE_URL": os.environ["TEST_DATABASE_URL"], "REDIS_URL": os.environ["TEST_REDIS_URL"]}
        with patch.dict(os.environ, env), patch("sourcehealth.application.jobs.collect_platform", self.context):
            execute_analysis(str(run.id))
            execute_analysis(str(run.id))  # duplicate delivery must be a no-op
        with self.sessions() as db:
            completed = db.get(AnalysisRun, run.id)
            self.assertEqual(completed.status, "partial")
            self.assertIsNone(completed.health_score)
            self.assertEqual(completed.results["schema_version"], "3.0")
            self.assertNotIn("path", completed.results["repository"])
            self.assertEqual(len(completed.category_scores), 6)
        self.assertEqual(self.service.request_analysis(self.repository_id).id, run.id)
        self.assertNotEqual(self.service.request_analysis(self.repository_id, force=True, trigger="refresh").id, run.id)

    def test_rq_delivery_executes_application_job(self):
        class TestWorker(SimpleWorker):
            death_penalty_class = TimerDeathPenalty

        run = self.service.request_analysis(self.repository_id)
        dispatch_pending(self.sessions, self.redis)
        env = {"DATABASE_URL": os.environ["TEST_DATABASE_URL"], "REDIS_URL": os.environ["TEST_REDIS_URL"]}
        with patch.dict(os.environ, env), patch("sourcehealth.application.jobs.collect_platform", self.context):
            TestWorker([Queue("analysis", connection=self.redis)], connection=self.redis).work(burst=True, logging_level="WARNING")
        with self.sessions() as db:
            self.assertEqual(db.get(AnalysisRun, run.id).status, "partial")

    def test_code_queue_runtime_persistence_and_http(self):
        """Real RQ/PG/HTTP with fake sandbox: success, partial and exception all retain metadata."""
        from unittest.mock import Mock

        class TestWorker(SimpleWorker):
            death_penalty_class = TimerDeathPenalty

        settings = self.settings.model_copy(update={"analysis_profile": "code-v1"})
        service = AnalysisService(self.sessions, settings)
        for mode in ("success", "partial", "failure", "disabled"):
            with self.subTest(mode=mode):
                run = service.request_analysis(self.repository_id, force=True)
                dispatch_pending(self.sessions, self.redis)
                self.assertIn(str(run.id), Queue("analysis-code", connection=self.redis).job_ids)
                self.assertNotIn(str(run.id), Queue("analysis", connection=self.redis).job_ids)
                runtime = Mock()
                runtime.analyze.return_value = runtime_fixture(partial=mode == "partial")
                if mode == "failure":
                    runtime.analyze.side_effect = RuntimeError("private runtime error")
                with (patch("sourcehealth.application.jobs.Settings", return_value=settings),
                      patch("sourcehealth.application.jobs.collect_platform", self.context),
                      patch("sourcehealth.application.jobs.configured_runtime", return_value=None if mode == "disabled" else runtime)):
                    TestWorker([Queue("analysis-code", connection=self.redis)], connection=self.redis).work(
                        burst=True, logging_level="WARNING")
                if mode != "disabled":
                    runtime.analyze.assert_called_once()
                with TestClient(create_app(settings, sessions=self.sessions, redis=self.redis)) as client:
                    response = client.get(f"/api/v1/analyses/{run.id}")
                    self.assertEqual(response.status_code, 200)
                    payload = response.json()
                    self.assertEqual(payload["status"], "partial")  # AppSec remains unavailable.
                    self.assertEqual(payload["checks"]["repository_metadata"]["status"], "ok")
                    self.assertEqual(payload["checks"]["sast"]["category"], "code_health")
                    self.assertEqual(payload["checks"]["sast"]["source"], "sourcehealth_local")
                    self.assertEqual(payload["checks"]["git_activity"]["status"],
                                     "ok" if mode in ("success", "partial") else "error")
                    self.assertEqual(payload["checks"]["sast"]["status"],
                                     {"success": "ok", "partial": "partial", "failure": "error", "disabled": "error"}[mode])
                    self.assertIsNone(payload["health_score"])
                    self.assertEqual(payload["category_scores"]["security"]["availability"], "no_data")
                    self.assertNotIn("private runtime error", response.text)
                    self.assertEqual(client.get(f"/api/v1/analyses/{run.id}/report.md").status_code, 200)

    def test_mvp_import_queue_report_leaderboard_and_cache(self):
        """Real HTTP/RQ/PostgreSQL/Redis; external platform and sandbox are fixtures."""
        from unittest.mock import Mock

        from sourcehealth.integrations.sourcecraft.client import SourceCraftClient
        from tests.mvp_fixtures import SHA, runtime_payload, sourcecraft_transport

        class TestWorker(SimpleWorker):
            death_penalty_class = TimerDeathPenalty

        settings = self.settings.model_copy(update={"analysis_profile": "mvp-v1"})
        transport = sourcecraft_transport(self.ref.repository_slug)

        def source_client(**kwargs):
            return SourceCraftClient(transport=transport, **kwargs)

        runtime = Mock()
        runtime.analyze.return_value = runtime_payload()
        app = create_app(settings, sessions=self.sessions, redis=self.redis)
        with (TestClient(app, base_url="https://testserver") as client,
              patch.object(app.state.auth, "current_user", return_value={"id": str(uuid4())}),
              patch("sourcehealth.integrations.sourcecraft.client.SourceCraftClient", side_effect=source_client),
              patch("sourcehealth.application.jobs.SourceCraftClient", side_effect=source_client),
              patch("sourcehealth.application.jobs.Settings", return_value=settings),
              patch("sourcehealth.application.jobs.configured_runtime", return_value=runtime)):
            headers = {"Origin": "https://testserver"}
            body = {"url": self.ref.canonical_url}
            self.assertEqual(client.post("/api/v1/repositories", json=body).status_code, 403)
            self.assertEqual(client.post("/api/v1/repositories", json={"url": "https://example.com/x/y"}, headers=headers).status_code, 422)
            imported = client.post("/api/v1/repositories", json=body, headers=headers)
            self.assertEqual(imported.status_code, 201, imported.text)
            self.assertEqual(imported.json()["id"], str(self.repository_id))
            self.assertEqual(imported.json()["language"], "Python")
            repeat = client.post("/api/v1/repositories", json=body, headers=headers)
            self.assertEqual(repeat.json()["id"], str(self.repository_id))
            response = client.post(f"/api/v1/repositories/{self.repository_id}/analyses", json={}, headers=headers)
            self.assertEqual(response.status_code, 202, response.text)
            run_id = response.json()["id"]
            self.assertIn(run_id, Queue("analysis-code", connection=self.redis).job_ids)
            self.assertNotIn(run_id, Queue("analysis", connection=self.redis).job_ids)
            TestWorker([Queue("analysis-code", connection=self.redis)], connection=self.redis).work(burst=True, logging_level="WARNING")
            result = client.get(f"/api/v1/analyses/{run_id}")
            self.assertEqual(result.status_code, 200, result.text)
            payload = result.json()
            self.assertEqual(payload["status"], "partial")  # Official AppSec is still unconfirmed.
            self.assertEqual(len(payload["category_scores"]), 6)
            self.assertIsInstance(payload["health_score"], (int, float))
            self.assertEqual(payload["scoring_policy_version"], "mvp-score-v1")
            self.assertIsNone(payload["category_scores"]["security"]["score"])
            self.assertEqual(payload["category_scores"]["security"]["availability"], "no_data")
            self.assertEqual(payload["head_sha"], SHA)
            for forbidden in ("untrusted", "do-not-store", "private name", "error_messages"):
                self.assertNotIn(forbidden, result.text)
            markdown = client.get(f"/api/v1/analyses/{run_id}/report.md")
            self.assertEqual(markdown.status_code, 200)
            self.assertIn(r"mvp\-score\-v1", markdown.text)
            listing = client.get("/api/v1/repositories", params={"limit": 100}).json()
            listed = next(row for row in listing["items"] if row["id"] == str(self.repository_id))
            self.assertEqual(listed["health_score"], payload["health_score"])
            cached = client.post(f"/api/v1/repositories/{self.repository_id}/analyses", json={}, headers=headers)
            self.assertEqual(cached.json()["id"], run_id)
            runtime.analyze.assert_called_once()
        with self.sessions() as db:
            row = db.get(AnalysisRun, UUID(run_id))
            self.assertEqual(row.head_sha, SHA)
            self.assertEqual(row.results["category_scores"], row.category_scores)
            self.assertEqual(row.results["recommendations"], row.recommendations)
            self.assertEqual(len(row.data_coverage), 6)

    def test_import_rejects_unverified_private_and_unauthenticated(self):
        from sourcehealth.application.services import ServiceError
        from sourcehealth.integrations.sourcecraft.client import SourceCraftClient

        app = create_app(self.settings, sessions=self.sessions, redis=self.redis)
        with TestClient(app, base_url="https://testserver") as client:
            self.assertEqual(client.post("/api/v1/repositories", json={"url": self.ref.canonical_url},
                                         headers={"Origin": "https://testserver"}).status_code, 401)
        for status, payload in ((200, {"visibility": "private"}), (401, {}), (404, {}), (503, {})):
            with self.subTest(status=status):
                with SourceCraftClient(transport=httpx.MockTransport(lambda request: httpx.Response(status, json=payload)), sleep=lambda _: None) as source:
                    with self.assertRaises(ServiceError) as error:
                        self.service.import_public_repository(self.ref.canonical_url, client=source)
                    self.assertEqual(error.exception.code, "public_repository_unverified")
        with self.sessions() as db:
            self.assertIsNone(db.get(Repository, self.repository_id).sourcecraft_id)

    def test_recovery_does_not_fail_live_lock_holder(self):
        run = self.service.request_analysis(self.repository_id)
        self.service.transition(run.id, "collecting")
        with self.sessions.begin() as db:
            db.get(AnalysisRun, run.id).deadline_at = datetime.now(UTC) - timedelta(seconds=1)
        with self.engine.connect() as guard:
            guard.execute(text("SELECT pg_advisory_lock(:key)"), {"key": lock_key(run.id)})
            guard.commit()
            self.assertEqual(recover_abandoned(self.engine, self.sessions, self.settings), 0)
            guard.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": lock_key(run.id)})
            guard.commit()
        self.assertEqual(recover_abandoned(self.engine, self.sessions, self.settings), 1)
        with self.sessions() as db:
            self.assertEqual(db.get(AnalysisRun, run.id).error_code, "worker_interrupted")

    def test_api_public_read_private_denial_and_markdown(self):
        run = self.service.request_analysis(self.repository_id)
        env = {"DATABASE_URL": os.environ["TEST_DATABASE_URL"], "REDIS_URL": os.environ["TEST_REDIS_URL"]}
        with patch.dict(os.environ, env), patch("sourcehealth.application.jobs.collect_platform", self.context):
            execute_analysis(str(run.id))
        with TestClient(create_app(self.settings, sessions=self.sessions, redis=self.redis), base_url="https://testserver") as client:
            self.assertEqual(client.get(f"/api/v1/repositories/{self.repository_id}").status_code, 200)
            response = client.get(f"/api/v1/analyses/{run.id}")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["status"], "partial")
            self.assertIn("NO_DATA", client.get(f"/api/v1/analyses/{run.id}/report.md").text)
            with self.sessions.begin() as db:
                db.get(Repository, self.repository_id).visibility = "private"
            self.assertEqual(client.get(f"/api/v1/analyses/{run.id}").status_code, 404)
            self.assertEqual(client.get(f"/api/v1/analyses/{run.id}/report.md").status_code, 404)

    def test_oauth_pkce_cookie_state_session_and_logout(self):
        yandex_id = "test-" + uuid4().hex
        requests = []

        def handler(request):
            requests.append(request)
            return httpx.Response(200, json={"access_token": "temporary-oauth-value"} if request.url.host == "oauth.yandex.ru"
                                  else {"id": yandex_id})

        auth = AuthService(self.settings, self.redis, self.sessions, transport=httpx.MockTransport(handler))
        url, pending = auth.login()
        query = parse_qs(urlsplit(url).query)
        self.assertEqual(query["code_challenge_method"], ["S256"])
        token = auth.callback(browser_token=pending, state=query["state"][0], code="test-code")
        user = auth.current_user(token)
        self.assertIsNotNone(user)
        self.assertNotIn("temporary-oauth-value", str(user))
        with self.assertRaisesRegex(Exception, "invalid_oauth_state"):
            auth.callback(browser_token=pending, state=query["state"][0], code="test-code")
        self.assertIn(b"code_verifier=", requests[0].content)
        app = create_app(self.settings, sessions=self.sessions, redis=self.redis)
        with TestClient(app, base_url="https://testserver") as client:
            login = client.get("/api/v1/auth/yandex/login", follow_redirects=False)
            self.assertIn("HttpOnly", login.headers["set-cookie"])
            self.assertIn("Secure", login.headers["set-cookie"])
            client.cookies.set("sh_session", token)
            self.assertEqual(client.get("/api/v1/me").status_code, 200)
            self.assertEqual(client.post("/api/v1/auth/logout").status_code, 403)
            self.assertEqual(client.post("/api/v1/auth/logout", headers={"Origin": "https://testserver"}).status_code, 204)
        self.assertIsNone(auth.current_user(token))
        with self.sessions.begin() as db:
            db.execute(delete(User).where(User.id == UUID(user["id"])))
