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
    from pydantic import SecretStr
    from redis import Redis
    from rq import Queue, SimpleWorker
    from rq.job import Job
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

    def test_sourcecraft_connection_lifecycle(self):
        import base64
        import json

        from sourcehealth.application.services import ServiceError
        from sourcehealth.auth.sourcecraft import SourceCraftConnection
        from sourcehealth.integrations.sourcecraft.client import SourceCraftClient

        settings = self.settings.model_copy(update={"sourcecraft_credential_key": SecretStr(
            base64.urlsafe_b64encode(os.urandom(32)).decode())})
        auth = AuthService(settings, self.redis, self.sessions)
        token, other = uuid4().hex, uuid4().hex
        credential = "unit-" + uuid4().hex
        for session in (token, other):
            self.redis.set(auth._key("session", session), json.dumps({"id": str(uuid4())}), ex=120)

        def respond(request):
            self.assertEqual(request.headers["authorization"], "Bearer " + credential)
            if request.url.path == "/user":
                return httpx.Response(200, json={"id": "user-1"})
            return httpx.Response(200, json={"repositories": [
                {"slug": "public-repo", "visibility": "public"},
                {"slug": "private-repo", "visibility": "private"}]})

        service = SourceCraftConnection(auth, client_factory=lambda **kw: SourceCraftClient(
            transport=httpx.MockTransport(respond), **kw))
        try:
            self.assertFalse(service.lease_for_analysis(None, uuid4()))
            result = service.connect(token, credential)
            self.assertTrue(result["connected"])
            self.assertLessEqual(result["expires_in"], 120)
            self.assertNotIn(credential.encode(), self.redis.get(auth._key("sourcecraft", token)))
            analysis_id = uuid4()
            self.assertTrue(service.lease_for_analysis(token, analysis_id))
            run_key = service._analysis_key(analysis_id)
            ciphertext = self.redis.get(run_key)
            self.assertNotIn(credential.encode(), ciphertext)
            self.assertGreater(self.redis.ttl(run_key), 0)
            self.assertEqual(service.analysis_credential(analysis_id), credential)
            copied_id = uuid4()
            copied_key = service._analysis_key(copied_id)
            self.redis.set(copied_key, ciphertext, ex=30)
            self.assertIsNone(service.analysis_credential(copied_id))  # AES-GCM AAD binds ciphertext to run key.
            self.assertFalse(service.lease_for_analysis(other, uuid4()))
            service.delete_analysis_credential(analysis_id)
            self.assertIsNone(self.redis.get(run_key))
            self.assertFalse(service.status(other)["connected"])
            repos = service.repositories(token, "test")
            self.assertEqual([r["can_analyze"] for r in repos["items"]], [True, False])
            cipher_key = auth._key("sourcecraft", token)
            self.redis.set(cipher_key, b"invalid-ciphertext", ex=30)
            with self.assertRaises(ServiceError):
                service.repositories(token, "test")
            self.assertIsNone(self.redis.get(cipher_key))
            service.connect(token, credential)
            self.redis.expire(cipher_key, 0)
            self.assertFalse(service.status(token)["connected"])
            service.disconnect(token)
            self.assertFalse(service.status(token)["connected"])
            service.connect(token, credential)
            auth.logout(token)
            self.assertIsNone(self.redis.get(auth._key("sourcecraft", token)))
            with self.assertRaises(ServiceError):
                service.connect(token, credential)
        finally:
            auth.logout(token)
            auth.logout(other)

    def test_connection_http_guards(self):
        import json

        auth = AuthService(self.settings, self.redis, self.sessions)
        token = uuid4().hex
        self.redis.set(auth._key("session", token), json.dumps({"id": str(uuid4())}), ex=60)
        try:
            with TestClient(create_app(self.settings, sessions=self.sessions, redis=self.redis),
                            base_url="https://testserver") as client:
                self.assertEqual(client.get("/api/v1/sourcecraft/connection").status_code, 401)
                client.cookies.set("sh_session", token)
                credential = "test-" + uuid4().hex
                response = client.post("/api/v1/sourcecraft/connection", json={"pat": credential},
                                       headers={"origin": "https://wrong.example"})
                self.assertEqual(response.status_code, 403)
                self.assertNotIn(credential, response.text)
                response = client.post("/api/v1/sourcecraft/connection", json={"pat": {"value": credential}},
                                       headers={"origin": "https://testserver"})
                self.assertEqual(response.status_code, 422)
                self.assertNotIn(credential, response.text)
                self.assertEqual(response.headers["cache-control"], "no-store")
        finally:
            auth.logout(token)

    def test_connected_pat_bypasses_no_data_cache_without_orphaning_cached_run(self):
        import base64
        import json

        from sourcehealth.auth.sourcecraft import SourceCraftConnection
        from sourcehealth.integrations.sourcecraft.client import SourceCraftClient

        settings = self.settings.model_copy(update={"sourcecraft_credential_key": SecretStr(
            base64.urlsafe_b64encode(os.urandom(32)).decode())})
        service = AnalysisService(self.sessions, settings)
        cached = service.request_analysis(self.repository_id)
        with self.sessions.begin() as db:
            row = db.get(AnalysisRun, cached.id)
            row.status, row.completed_at = "partial", datetime.now(UTC)
            row.results = {"checks": {"sourcecraft_appsec": {
                "source": "sourcecraft_appsec", "availability": "no_data", "metrics": {}}}}

        auth = AuthService(settings, self.redis, self.sessions)
        token = uuid4().hex
        self.redis.set(auth._key("session", token), json.dumps({"id": str(uuid4())}), ex=120)
        credential = "unit-" + uuid4().hex
        connection = SourceCraftConnection(auth, client_factory=lambda **kw: SourceCraftClient(
            transport=httpx.MockTransport(lambda _: httpx.Response(200, json={"id": "user-1"})), **kw))
        connection.connect(token, credential)
        app = create_app(settings, sessions=self.sessions, redis=self.redis)
        dispatched = []

        def assert_credential_precedes_dispatch(sessions, redis, timeout):
            if dispatched:
                return 0
            with sessions() as db:
                queued = db.scalar(select(AnalysisRun).where(
                    AnalysisRun.repository_id == self.repository_id, AnalysisRun.status == "queued"))
            self.assertIsNotNone(queued)
            self.assertEqual(connection.analysis_credential(queued.id), credential)
            dispatched.append(queued.id)
            return 0

        try:
            with (TestClient(app, base_url="https://testserver") as client,
                  patch("sourcehealth.api.routers.repositories.dispatch_pending",
                        side_effect=assert_credential_precedes_dispatch)):
                client.cookies.set("sh_session", token)
                response = client.post(f"/api/v1/repositories/{self.repository_id}/analyses", json={},
                                       headers={"Origin": "https://testserver"})
                self.assertEqual(response.status_code, 202, response.text)
                fresh_id = UUID(response.json()["id"])
                self.assertNotEqual(fresh_id, cached.id)
                self.assertEqual(dispatched, [fresh_id])
                self.assertIsNotNone(self.redis.get(connection._analysis_key(fresh_id)))

                connection.delete_analysis_credential(fresh_id)
                with self.sessions.begin() as db:
                    row = db.get(AnalysisRun, fresh_id)
                    row.status, row.completed_at = "partial", datetime.now(UTC)
                    row.results = {"checks": {"sourcecraft_appsec": {
                        "source": "sourcecraft_appsec", "availability": "available",
                        "metrics": {"complete": True, "open_by_severity": {}}}}}
                cached_response = client.post(
                    f"/api/v1/repositories/{self.repository_id}/analyses", json={},
                    headers={"Origin": "https://testserver"})
                self.assertEqual(cached_response.json()["id"], str(fresh_id))
                self.assertIsNone(self.redis.get(connection._analysis_key(fresh_id)))
        finally:
            auth.logout(token)

    def test_scheduled_active_run_cannot_be_upgraded_with_browser_credential(self):
        import base64
        import json

        from sourcehealth.auth.sourcecraft import SourceCraftConnection
        from sourcehealth.integrations.sourcecraft.client import SourceCraftClient

        settings = self.settings.model_copy(update={"sourcecraft_credential_key": SecretStr(
            base64.urlsafe_b64encode(os.urandom(32)).decode())})
        scheduled = AnalysisService(self.sessions, settings).request_analysis(
            self.repository_id, trigger="scheduled")
        auth = AuthService(settings, self.redis, self.sessions)
        token = uuid4().hex
        self.redis.set(auth._key("session", token), json.dumps({"id": str(uuid4())}), ex=120)
        credential = "unit-" + uuid4().hex
        connection = SourceCraftConnection(auth, client_factory=lambda **kw: SourceCraftClient(
            transport=httpx.MockTransport(lambda _: httpx.Response(200, json={"id": "user-1"})), **kw))
        connection.connect(token, credential)
        existing_keys = set(self.redis.scan_iter("auth:analysis-sourcecraft:*"))
        try:
            with (TestClient(create_app(settings, sessions=self.sessions, redis=self.redis),
                             base_url="https://testserver") as client,
                  patch("sourcehealth.api.routers.repositories.dispatch_pending", return_value=0)):
                client.cookies.set("sh_session", token)
                response = client.post(f"/api/v1/repositories/{self.repository_id}/analyses", json={},
                                       headers={"Origin": "https://testserver"})
            self.assertEqual(response.status_code, 202, response.text)
            self.assertEqual(response.json()["id"], str(scheduled.id))
            self.assertIsNone(connection.analysis_credential(scheduled.id))
            self.assertEqual(set(self.redis.scan_iter("auth:analysis-sourcecraft:*")), existing_keys)
        finally:
            auth.logout(token)

    def test_second_user_cannot_overwrite_first_users_analysis_credential(self):
        import base64
        import json

        from sourcehealth.auth.sourcecraft import SourceCraftConnection
        from sourcehealth.integrations.sourcecraft.client import SourceCraftClient

        settings = self.settings.model_copy(update={"sourcecraft_credential_key": SecretStr(
            base64.urlsafe_b64encode(os.urandom(32)).decode())})
        auth = AuthService(settings, self.redis, self.sessions)
        first_token, second_token = uuid4().hex, uuid4().hex
        for token in (first_token, second_token):
            self.redis.set(auth._key("session", token), json.dumps({"id": str(uuid4())}), ex=120)
        credentials = ("unit-a-" + uuid4().hex, "unit-b-" + uuid4().hex)
        connection = SourceCraftConnection(auth, client_factory=lambda **kw: SourceCraftClient(
            transport=httpx.MockTransport(lambda _: httpx.Response(200, json={"id": "user"})), **kw))
        connection.connect(first_token, credentials[0])
        connection.connect(second_token, credentials[1])
        existing_keys = set(self.redis.scan_iter("auth:analysis-sourcecraft:*"))
        try:
            with (TestClient(create_app(settings, sessions=self.sessions, redis=self.redis),
                             base_url="https://testserver") as client,
                  patch("sourcehealth.api.routers.repositories.dispatch_pending", return_value=0)):
                client.cookies.set("sh_session", first_token)
                first = client.post(f"/api/v1/repositories/{self.repository_id}/analyses", json={},
                                    headers={"Origin": "https://testserver"})
                client.cookies.set("sh_session", second_token)
                second = client.post(f"/api/v1/repositories/{self.repository_id}/analyses", json={},
                                     headers={"Origin": "https://testserver"})
            self.assertEqual(first.status_code, 202, first.text)
            self.assertEqual(second.status_code, 202, second.text)
            self.assertEqual(second.json()["id"], first.json()["id"])
            run_id = UUID(first.json()["id"])
            self.assertEqual(connection.analysis_credential(run_id), credentials[0])
            current_keys = set(self.redis.scan_iter("auth:analysis-sourcecraft:*"))
            self.assertEqual(current_keys - existing_keys, {connection._analysis_key(run_id).encode()})
            connection.delete_analysis_credential(run_id)
        finally:
            auth.logout(first_token)
            auth.logout(second_token)

    def test_credential_lease_failure_does_not_create_or_dispatch_run(self):
        import base64
        import json

        from sourcehealth.auth.sourcecraft import SourceCraftConnection
        from sourcehealth.integrations.sourcecraft.client import SourceCraftClient

        settings = self.settings.model_copy(update={"sourcecraft_credential_key": SecretStr(
            base64.urlsafe_b64encode(os.urandom(32)).decode())})
        auth = AuthService(settings, self.redis, self.sessions)
        token = uuid4().hex
        self.redis.set(auth._key("session", token), json.dumps({"id": str(uuid4())}), ex=120)
        connection = SourceCraftConnection(auth, client_factory=lambda **kw: SourceCraftClient(
            transport=httpx.MockTransport(lambda _: httpx.Response(200, json={"id": "user-1"})), **kw))
        connection.connect(token, "unit-" + uuid4().hex)
        try:
            with (TestClient(create_app(settings, sessions=self.sessions, redis=self.redis),
                             base_url="https://testserver") as client,
                  patch("sourcehealth.api.routers.repositories.SourceCraftConnection.lease_for_analysis",
                        return_value=False),
                  patch("sourcehealth.api.routers.repositories.dispatch_pending") as dispatch):
                client.cookies.set("sh_session", token)
                response = client.post(f"/api/v1/repositories/{self.repository_id}/analyses", json={},
                                       headers={"Origin": "https://testserver"})
            self.assertEqual(response.status_code, 409, response.text)
            dispatch.assert_not_called()
            with self.sessions() as db:
                self.assertIsNone(db.scalar(select(AnalysisRun).where(
                    AnalysisRun.repository_id == self.repository_id)))
        finally:
            auth.logout(token)

    def test_rating_import_updates_and_clears_unknown(self):
        from sourcehealth.integrations.sourcecraft.client import SourceCraftClient

        metadata = {"id": "rating-test", "slug": self.ref.repository_slug, "visibility": "public",
                    "rating": {"reaction_counts": [{"type": "positive_low", "count": "7"}]}}
        with SourceCraftClient(transport=httpx.MockTransport(lambda _: httpx.Response(200, json=metadata))) as client:
            self.service.import_public_repository(self.ref.canonical_url, client=client)
            with self.sessions() as db:
                self.assertEqual(db.get(Repository, self.repository_id).likes, 7)
            metadata.pop("rating")
            self.service.import_public_repository(self.ref.canonical_url, client=client)
            with self.sessions() as db:
                self.assertIsNone(db.get(Repository, self.repository_id).likes)

    def test_score_preview_never_changes_leaderboard_ranking(self):
        preview_ref = RepositoryRef.from_url(
            f"https://sourcecraft.dev/test/preview-{uuid4().hex}", visibility="public")
        preview_id = self.service.register_repository(preview_ref)
        categories = {
            name: {"category": name, "score": 90, "availability": "available",
                   "explanation": "test", "evidence_refs": []}
            for name in ("activity", "issues")
        }
        try:
            with self.sessions() as db:
                db.get(Repository, self.repository_id).health_score = 50
                run = AnalysisRun(repository_id=preview_id, status="completed", trigger="manual", profile="mvp-v1",
                                  fingerprint=uuid4().hex, completed_at=datetime.now(UTC),
                                  scoring_policy_version="mvp-score-v1.2", analyzer_contract_version="3.0",
                                  health_score=None, category_scores=categories)
                db.add(run)
                db.flush()
                db.get(Repository, preview_id).latest_analysis_id = run.id
                db.commit()
            with TestClient(create_app(self.settings, sessions=self.sessions, redis=self.redis)) as client:
                items = client.get("/api/v1/repositories", params={"limit": 100}).json()["items"]
            positions = {item["id"]: index for index, item in enumerate(items)}
            self.assertLess(positions[str(self.repository_id)], positions[str(preview_id)])
            preview = next(item for item in items if item["id"] == str(preview_id))
            self.assertIsNone(preview["health_score"])
            self.assertEqual(preview["score_preview"]["score"], 90)
        finally:
            with self.sessions.begin() as db:
                db.execute(update(Repository).where(Repository.id == preview_id).values(latest_analysis_id=None))
                db.execute(delete(AnalysisRun).where(AnalysisRun.repository_id == preview_id))
                db.execute(delete(Repository).where(Repository.id == preview_id))

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

    def test_dispatch_repairs_orphaned_queued_rq_job(self):
        run = self.service.request_analysis(self.repository_id)
        queue = Queue("analysis", connection=self.redis)
        dispatch_pending(self.sessions, self.redis)
        queue.remove(str(run.id))  # Keep the RQ job hash, reproducing dequeue-before-start shutdown.
        self.assertEqual(Job.fetch(str(run.id), connection=self.redis).get_status(refresh=True), "queued")
        self.assertNotIn(str(run.id), queue.job_ids)
        self.assertEqual(dispatch_pending(self.sessions, self.redis), 1)
        self.assertIn(str(run.id), queue.job_ids)

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
            self.assertEqual(payload["scoring_policy_version"], "mvp-score-v1.2")
            self.assertIsNone(payload["category_scores"]["security"]["score"])
            self.assertEqual(payload["category_scores"]["security"]["availability"], "no_data")
            self.assertEqual(payload["score_coverage"]["nominal_weight_percent"], 80)
            self.assertEqual(payload["score_coverage"]["unscored_categories"], ["security"])
            self.assertTrue(payload["score_preview"]["numeric"])
            self.assertEqual(payload["head_sha"], SHA)
            for forbidden in ("untrusted", "do-not-store", "private name", "error_messages"):
                self.assertNotIn(forbidden, result.text)
            markdown = client.get(f"/api/v1/analyses/{run_id}/report.md")
            self.assertEqual(markdown.status_code, 200)
            self.assertIn(r"mvp\-score\-v1\.2", markdown.text)
            listing = client.get("/api/v1/repositories", params={"limit": 100}).json()
            listed = next(row for row in listing["items"] if row["id"] == str(self.repository_id))
            self.assertEqual(listed["health_score"], payload["health_score"])
            self.assertEqual(listed["score_preview"], payload["score_preview"])
            cached = client.post(f"/api/v1/repositories/{self.repository_id}/analyses", json={}, headers=headers)
            self.assertEqual(cached.json()["id"], run_id)
            runtime.analyze.assert_called_once()
        with self.sessions() as db:
            row = db.get(AnalysisRun, UUID(run_id))
            self.assertEqual(row.head_sha, SHA)
            self.assertEqual(row.results["category_scores"], row.category_scores)
            self.assertEqual(row.results["recommendations"], row.recommendations)
            self.assertEqual(len(row.data_coverage), 6)

    def test_connected_pat_runs_appsec_pipeline_and_deletes_lease(self):
        import base64
        import json
        from unittest.mock import Mock

        from sourcehealth.auth.sourcecraft import SourceCraftConnection
        from sourcehealth.integrations.sourcecraft.appsec import SourceCraftAppSecClient
        from sourcehealth.integrations.sourcecraft.client import SourceCraftClient
        from tests.mvp_fixtures import runtime_payload, sourcecraft_transport

        class TestWorker(SimpleWorker):
            death_penalty_class = TimerDeathPenalty

        settings = self.settings.model_copy(update={
            "analysis_profile": "mvp-v1",
            "sourcecraft_credential_key": SecretStr(base64.urlsafe_b64encode(os.urandom(32)).decode()),
        })
        normal_transport = sourcecraft_transport(self.ref.repository_slug)
        auth = AuthService(settings, self.redis, self.sessions)
        token = uuid4().hex
        self.redis.set(auth._key("session", token), json.dumps({"id": str(uuid4())}), ex=120)
        credential = "unit-" + uuid4().hex
        connection = SourceCraftConnection(auth, client_factory=lambda **kw: SourceCraftClient(
            transport=httpx.MockTransport(lambda _: httpx.Response(200, json={"id": "user-1"})), **kw))
        connection.connect(token, credential)

        def normal_client(**kwargs):
            return SourceCraftClient(transport=normal_transport, **kwargs)

        sensitive_marker = "SUPER_SECRET_" + "VALUE_SHOULD_NEVER_PERSIST"

        def appsec_handler(request):
            if request.url.path == "/v1/scans/latest":
                return httpx.Response(200, json={"uuid": "scan-fixture"})
            if request.url.path == "/v1/scans/scan-fixture":
                return httpx.Response(200, json={"status": "FINISHED"})
            rows = ([{"uuid": "group-fixture", "codeBlock": sensitive_marker}]
                    if request.url.params.get("severity") == "MEDIUM" else [])
            return httpx.Response(200, json={"data": rows, "nextPageToken": "", "totalSize": len(rows)})

        def appsec_client(**kwargs):
            return SourceCraftAppSecClient(transport=httpx.MockTransport(appsec_handler), sleep=lambda _: None, **kwargs)

        runtime = Mock()
        runtime.analyze.return_value = runtime_payload()
        app = create_app(settings, sessions=self.sessions, redis=self.redis)
        try:
            with (TestClient(app, base_url="https://testserver") as client,
                  patch("sourcehealth.application.jobs.SourceCraftClient", side_effect=normal_client),
                  patch("sourcehealth.application.jobs.SourceCraftAppSecClient", side_effect=appsec_client),
                  patch("sourcehealth.application.jobs.Settings", return_value=settings),
                  patch("sourcehealth.application.jobs.configured_runtime", return_value=runtime)):
                client.cookies.set("sh_session", token)
                response = client.post(f"/api/v1/repositories/{self.repository_id}/analyses", json={},
                                       headers={"Origin": "https://testserver"})
                self.assertEqual(response.status_code, 202, response.text)
                run_id = UUID(response.json()["id"])
                self.assertIsNotNone(self.redis.get(connection._analysis_key(run_id)))
                TestWorker([Queue("analysis-code", connection=self.redis)], connection=self.redis).work(
                    burst=True, logging_level="WARNING")
                result = client.get(f"/api/v1/analyses/{run_id}")
                self.assertEqual(result.status_code, 200, result.text)
                payload = result.json()
                self.assertEqual(payload["category_scores"]["security"]["score"], 95)
                self.assertEqual(payload["checks"]["sourcecraft_appsec"]["metrics"]["total_open"], 1)
                self.assertNotIn(sensitive_marker, result.text)
                self.assertIsNone(self.redis.get(connection._analysis_key(run_id)))
        finally:
            auth.logout(token)

    def test_public_analysis_history_is_stable_paginated_and_private_safe(self):
        queued_at = datetime(2026, 9, 20, 12, tzinfo=UTC)
        ids = [UUID("10000000-0000-0000-0000-000000000001"),
               UUID("10000000-0000-0000-0000-000000000002"),
               UUID("10000000-0000-0000-0000-000000000003")]
        with self.sessions.begin() as db:
            db.add_all([
                AnalysisRun(id=ids[0], repository_id=self.repository_id, status="completed", trigger="manual",
                            profile="mvp-v1", fingerprint="1" * 64, queued_at=queued_at,
                            completed_at=queued_at, scoring_policy_version="mvp-score-v1.1"),
                AnalysisRun(id=ids[1], repository_id=self.repository_id, status="failed", trigger="system",
                            profile="platform-v1", fingerprint="2" * 64, queued_at=queued_at,
                            completed_at=queued_at, error_code="fixture_failure"),
                AnalysisRun(id=ids[2], repository_id=self.repository_id, status="queued", trigger="refresh",
                            profile="code-v1", fingerprint="3" * 64, queued_at=queued_at),
            ])
        with TestClient(create_app(self.settings, sessions=self.sessions, redis=self.redis),
                        base_url="https://testserver") as client:
            first = client.get(f"/api/v1/repositories/{self.repository_id}/analyses", params={"limit": 2})
            self.assertEqual(first.status_code, 200, first.text)
            self.assertEqual([item["id"] for item in first.json()["items"]], [str(ids[2]), str(ids[1])])
            self.assertEqual([item["profile"] for item in first.json()["items"]], ["code-v1", "platform-v1"])
            self.assertTrue(first.json()["has_more"])
            second = client.get(f"/api/v1/repositories/{self.repository_id}/analyses",
                                params={"limit": 2, "offset": 2}).json()
            self.assertEqual([item["id"] for item in second["items"]], [str(ids[0])])
            self.assertFalse(second["has_more"])
            with self.sessions.begin() as db:
                db.get(Repository, self.repository_id).visibility = "private"
            self.assertEqual(client.get(f"/api/v1/repositories/{self.repository_id}/analyses").status_code, 404)

    def test_accept_public_runs_existing_mvp_pipeline_and_validates_persistence(self):
        from unittest.mock import Mock

        from sourcehealth.application.acceptance import accept_public
        from sourcehealth.integrations.sourcecraft.client import SourceCraftClient
        from tests.mvp_fixtures import runtime_payload, sourcecraft_transport

        settings = self.settings.model_copy(update={"analysis_profile": "mvp-v1",
                                                    "sourcecraft_pat": SecretStr("test" + "-credential")})
        transport = sourcecraft_transport(self.ref.repository_slug)

        def source_client(**kwargs):
            return SourceCraftClient(transport=transport, **kwargs)

        runtime = Mock()
        runtime.analyze.return_value = runtime_payload()

        def execute_pending(sessions, redis, timeout):
            with sessions() as db:
                run_id = db.scalar(select(AnalysisRun.id).where(
                    AnalysisRun.repository_id == self.repository_id, AnalysisRun.status == "queued"))
            execute_analysis(str(run_id))

        env = {"DATABASE_URL": os.environ["TEST_DATABASE_URL"], "REDIS_URL": os.environ["TEST_REDIS_URL"]}
        with (SourceCraftClient(transport=transport) as client,
              patch.dict(os.environ, env),
              patch("sourcehealth.application.jobs.SourceCraftClient", side_effect=source_client),
              patch("sourcehealth.application.jobs.Settings", return_value=settings),
              patch("sourcehealth.application.jobs.configured_runtime", return_value=runtime)):
            result, code = accept_public(settings, self.ref.canonical_url, self.sessions, self.redis,
                                         client=client, dispatch=execute_pending, sleep=lambda _: None)
        self.assertEqual(code, 0, result)
        self.assertEqual(result["overall"], "ok")
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["score_coverage"]["nominal_weight_percent"], 80)
        self.assertEqual(result["categories"]["security"]["availability"], "no_data")

    def test_accept_timeout_keeps_durable_run_queued(self):
        from sourcehealth.application.acceptance import accept_public
        from sourcehealth.integrations.sourcecraft.client import SourceCraftClient
        from tests.mvp_fixtures import sourcecraft_transport

        settings = self.settings.model_copy(update={"analysis_profile": "mvp-v1",
                                                    "sourcecraft_pat": SecretStr("test" + "-credential")})
        ticks = iter((0.0, 0.0, 0.0, 2.0, 2.0))
        with SourceCraftClient(transport=sourcecraft_transport(self.ref.repository_slug)) as client:
            result, code = accept_public(settings, self.ref.canonical_url, self.sessions, self.redis, timeout=1,
                                         client=client, dispatch=lambda *args: None,
                                         clock=lambda: next(ticks), sleep=lambda _: None)
        self.assertEqual(code, 1)
        self.assertEqual(result["error"], "acceptance_timeout")
        with self.sessions() as db:
            self.assertEqual(db.get(AnalysisRun, UUID(result["analysis_id"])).status, "queued")

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
