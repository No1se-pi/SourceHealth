"""Контрактные проверки foundation без PostgreSQL, Redis и настоящих credentials."""

import json
import unittest
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import Mock, patch

from sourcehealth.analyzers import SASTAnalyzerAdapter
from sourcehealth.core import AnalysisContext, AnalyzerResult
from sourcehealth.core.domain import Category, DataAvailability, Evidence, RepositoryRef, validate_transition
from sourcehealth.markdown import render_markdown
from sourcehealth.runner import AnalysisRunner
from sourcehealth.scoring.engine import CategoryScore, ScoreResult, ScoringEngine


class CoreFoundationTests(unittest.TestCase):
    def test_repository_identity_and_url_validation(self):
        ref = RepositoryRef.from_url("https://git@git.sourcecraft.dev/team/repo.git")
        self.assertEqual(ref.canonical_url, "https://sourcecraft.dev/team/repo")
        self.assertNotIn("path", ref.to_dict())
        for url in ("http://sourcecraft.dev/team/repo", "https://sourcecraft.dev.evil/team/repo",
                    "https://password@sourcecraft.dev/team/repo", "https://sourcecraft.dev/team/repo?token=secret"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                RepositoryRef.from_url(url)

    def test_api_only_context_does_not_collect_git_or_require_workspace(self):
        ref = RepositoryRef.from_url("https://sourcecraft.dev/team/repo")
        with patch("sourcehealth.runner.GitCollector", side_effect=AssertionError):
            context = AnalysisContext(repository=ref)
            report = AnalysisRunner([SASTAnalyzerAdapter()]).analyze_context(context)
        self.assertIsNone(context.workspace)
        self.assertEqual(report.checks["sast"].availability, DataAvailability.NO_DATA)
        payload = report.to_public_dict()
        self.assertEqual(payload["schema_version"], "3.0")
        self.assertNotIn("path", payload["repository"])
        self.assertEqual(payload["checks"]["sast"]["category"], "code_health")

    def test_public_report_rejects_local_cli_identity(self):
        from sourcehealth.core import AnalysisReport

        now = datetime.now(UTC)
        with self.assertRaises((ValueError, TypeError)):
            AnalysisReport({"path": "private-local-directory"}, now, now).to_public_dict()

    def test_context_requires_identity_and_aware_clock(self):
        with self.assertRaises(ValueError):
            AnalysisContext()
        with self.assertRaises(ValueError):
            AnalysisContext(Path("."), started_at=datetime(2026, 1, 1))

    def test_availability_is_not_score_zero(self):
        for availability in (DataAvailability.NO_DATA, DataAvailability.SOURCE_UNAVAILABLE,
                             DataAvailability.ERROR, DataAvailability.NOT_APPLICABLE):
            with self.subTest(availability=availability), self.assertRaises(ValueError):
                CategoryScore(Category.SECURITY, 0, availability, evidence_refs=("e",))
        result = ScoringEngine().score({})
        self.assertIsNone(result.health_score)
        self.assertEqual(len(result.categories), 6)
        self.assertTrue(all(c.score is None for c in result.categories.values()))

    def test_security_cannot_use_local_scanner(self):
        observed = {}

        class Policy:
            version = "test"

            def evaluate(self, results):
                observed.update(results)
                return ScoreResult(self.version, {c.value: CategoryScore(c) for c in Category})

        ScoringEngine(Policy()).score({"sast": AnalyzerResult("sast", category="security", source="sourcehealth_local")})
        self.assertEqual(observed, {})

    def test_numeric_security_without_appsec_evidence_is_rejected(self):
        class Policy:
            version = "test"

            def evaluate(self, results):
                categories = {c.value: CategoryScore(c) for c in Category}
                categories["security"] = CategoryScore(Category.SECURITY, 100, DataAvailability.AVAILABLE,
                                                        evidence_refs=("local",))
                return ScoreResult(self.version, categories, 100)

        with self.assertRaises(ValueError):
            ScoringEngine(Policy()).score({})

    def test_lifecycle_no_resurrection_or_skipped_stage(self):
        for current, target in (("queued", "collecting"), ("collecting", "analyzing"),
                                ("analyzing", "scoring"), ("scoring", "partial")):
            validate_transition(current, target)
        for current, target in (("completed", "queued"), ("queued", "completed"), ("failed", "collecting")):
            with self.assertRaises(ValueError):
                validate_transition(current, target)

    def test_evidence_survives_runner_copy_and_markdown_is_deterministic(self):
        analyzer = Mock()
        analyzer.name = "metadata"
        analyzer.analyze.return_value = AnalyzerResult("metadata", evidence=[Evidence(
            "e1", "sourcecraft", "repository_metadata", "ref", "<script>alert(1)</script>")])
        report = AnalysisRunner([analyzer]).analyze_context(AnalysisContext(
            repository=RepositoryRef.from_url("https://sourcecraft.dev/team/repo")))
        ScoringEngine().apply(report)
        markdown = render_markdown(report)
        self.assertEqual(markdown, render_markdown(json.loads(json.dumps(report.to_public_dict()))))
        self.assertIn("NO_DATA", markdown)
        self.assertNotIn("<script>", markdown)
        self.assertEqual(report.checks["metadata"].evidence[0].id, "e1")


try:
    import httpx
    from fastapi.testclient import TestClient

    from sourcehealth.api.app import create_app
    from sourcehealth.application.cache import code_cache_key, fingerprint, platform_cache_key
    from sourcehealth.integrations.sourcecraft.client import SourceCraftClient, SourceCraftError
    from sourcehealth.settings import Settings
    SERVER_AVAILABLE = True
except ImportError:
    SERVER_AVAILABLE = False


@unittest.skipUnless(SERVER_AVAILABLE, "install .[server] for HTTP/client tests")
class ServerFoundationTests(unittest.TestCase):
    def test_cache_fingerprints_include_version_and_not_key_order(self):
        self.assertEqual(fingerprint("x", a=1, b=2), fingerprint("x", b=2, a=1))
        key = code_cache_key("r", "sha", "analyzer", "1", "config")
        self.assertNotEqual(key, code_cache_key("r", "sha", "analyzer", "2", "config"))
        self.assertNotEqual(key, code_cache_key("r", "sha2", "analyzer", "1", "config"))
        self.assertNotEqual(platform_cache_key("r", "issues"), platform_cache_key("r", "issues", "user-1"))
        with self.assertRaises(ValueError):
            code_cache_key("r", "", "analyzer", "1", "config")

    def test_health_and_validation_do_not_need_persistent_services(self):
        with TestClient(create_app(Settings(_env_file=None), sessions=Mock(), redis=Mock())) as client:
            health = client.get("/api/v1/health")
            self.assertEqual(health.status_code, 200)
            self.assertEqual(health.json()["status"], "ok")
            self.assertIn("x-request-id", health.headers)
            for path in ("/api/v1/repositories/not-a-uuid", "/api/v1/repositories?limit=1000"):
                response = client.get(path)
                self.assertEqual(response.status_code, 422)
                self.assertEqual(set(response.json()), {"code", "message", "request_id"})
                self.assertNotIn("not-a-uuid", response.text)
            self.assertEqual(client.get("/api/v1/me").status_code, 401)
            self.assertEqual(client.get("/api/v1/auth/yandex/login").status_code, 503)

    def test_openapi_exposes_backend_owned_score_preview(self):
        schemas = create_app(Settings(_env_file=None), sessions=Mock(), redis=Mock()).openapi()["components"]["schemas"]
        self.assertIn("ScorePreviewDTO", schemas)
        for name in ("AnalysisDetails", "RepositorySummary", "RepositoryDetails"):
            self.assertIn("score_preview", schemas[name]["properties"])

    def test_database_exception_does_not_leak_credentials(self):
        from sqlalchemy.exc import OperationalError

        sessions = Mock(side_effect=OperationalError("password=private-value", {}, Exception("secret")))
        with TestClient(create_app(sessions=sessions, redis=Mock())) as client:
            response = client.get("/api/v1/repositories")
            self.assertEqual(response.status_code, 503)
            self.assertNotIn("private-value", response.text)
            self.assertNotIn("secret", response.text)

    def test_pagination_follows_tokens_and_preserves_params(self):
        requests = []

        def handler(request):
            requests.append(request)
            body = {"issues": [{"id": "2"}]} if request.url.params.get("page_token") else {
                "issues": [{"id": "1"}], "next_page_token": "second"}
            return httpx.Response(200, json=body)

        with SourceCraftClient(transport=httpx.MockTransport(handler)) as client:
            result = list(client.iter_items("/repos/team/repo/issues", "issues", params={"filter": "status=open"}))
        self.assertEqual([item["id"] for item in result], ["1", "2"])
        self.assertEqual(requests[1].url.params["filter"], "status=open")

    def test_repeated_page_token_is_an_error_and_partial_items_survive(self):
        with SourceCraftClient(transport=httpx.MockTransport(lambda r: httpx.Response(
            200, json={"issues": [{"id": "1"}], "next_page_token": "loop"}))) as client:
            items = client.iter_items("/repos/team/repo/issues", "issues")
            self.assertEqual(next(items)["id"], "1")
            with self.assertRaises(SourceCraftError):
                next(items)

    def test_retries_429_5xx_and_error_redaction(self):
        statuses = iter([429, 503, 200])
        sleeps = []
        with SourceCraftClient(pat="test-only", sleep=sleeps.append, transport=httpx.MockTransport(
            lambda r: httpx.Response(next(statuses), headers={"Retry-After": "0"}, json={"ok": True}))) as client:
            self.assertTrue(client.get("/user")["ok"])
        self.assertEqual(len(sleeps), 2)
        for status in (401, 403, 404, 302):
            with SourceCraftClient(transport=httpx.MockTransport(lambda r: httpx.Response(status, text="raw secret"))) as client:
                with self.assertRaises(SourceCraftError) as caught:
                    client.get("/user")
                self.assertNotIn("raw secret", str(caught.exception))

    def test_response_size_and_path_boundaries(self):
        with SourceCraftClient(max_response_bytes=8, transport=httpx.MockTransport(
            lambda r: httpx.Response(200, json={"payload": "too large"}))) as client:
            with self.assertRaises(SourceCraftError):
                client.get("/user")
            with self.assertRaises(ValueError):
                client.get("https://evil.invalid")
