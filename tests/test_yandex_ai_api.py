import unittest
from contextlib import contextmanager
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

from fastapi.testclient import TestClient
from pydantic import SecretStr

from sourcehealth.ai.contracts import AISummaryResult, GroundedAction, GroundedStatement
from sourcehealth.api.app import create_app
from sourcehealth.settings import Settings
from sourcehealth.storage.models import AnalysisRun


class FakeSessions:
    def __init__(self, run, repo): self.run, self.repo = run, repo
    @contextmanager
    def __call__(self):
        db = Mock()
        db.get.side_effect = lambda model, _id: self.run if model is AnalysisRun else self.repo
        yield db


class AISummaryAPITests(unittest.TestCase):
    def setUp(self):
        self.analysis_id, self.repository_id = uuid4(), uuid4()
        self.repo = SimpleNamespace(id=self.repository_id, visibility="public", organization_slug="org",
                                    repository_slug="repo")
        self.run = SimpleNamespace(
            id=self.analysis_id, repository_id=self.repository_id, status="completed", health_score=80.0,
            scoring_policy_version="mvp-score-v1.2", category_scores={
                "documentation": {"score": 80, "availability": "available", "explanation": "README есть",
                                  "evidence_refs": ["doc:readme"]}},
            recommendations=[], results={"checks": {"documentation": {"metrics": {}, "evidence": [
                {"id": "doc:readme", "kind": "documentation", "summary": "README найден", "value": True}
            ]}}}, completed_at=datetime.now(UTC),
        )
        self.redis = Mock()
        self.redis.get.return_value = None
        self.redis.incr.return_value = 1
        settings = Settings(_env_file=None, public_origin="https://testserver", yandex_ai_folder_id="folder",
                            yandex_ai_api_key=SecretStr("secret"))
        self.app = create_app(settings, sessions=FakeSessions(self.run, self.repo), redis=self.redis)
        self.app.state.auth.current_user = Mock(return_value={"id": str(uuid4())})
        provider = Mock()
        provider.summarize.return_value = AISummaryResult(
            executive_summary="README найден.", strengths=[GroundedStatement(
                text="Документация доступна.", evidence_refs=["doc:readme"])], risks=[],
            actions=[GroundedAction(
                id="action-1", title="README", priority=2, why="Needs detail.",
                action="Expand README.", implementation_steps=["Edit README."],
                expected_result="Clear setup.", recommendation_ids=[], evidence_refs=["doc:readme"],
            )], limitations=[])
        self.app.state.ai_provider = provider

    def post(self, body=None):
        with TestClient(self.app, base_url="https://testserver") as client:
            return client.post(f"/api/v1/analyses/{self.analysis_id}/ai-summary",
                               json=body or {"model": "lite"},
                               headers={"Origin": "https://testserver"})

    def post_report(self, body=None):
        with TestClient(self.app, base_url="https://testserver") as client:
            return client.post(f"/api/v1/analyses/{self.analysis_id}/ai-report",
                               json=body or {"model": "lite"},
                               headers={"Origin": "https://testserver"})

    def test_legacy_request_and_response_contract_remain_v1(self):
        response = self.post()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["model_name"], "YandexGPT 5 Lite")
        self.assertNotIn("detail", response.json())
        self.assertEqual(response.json()["summary"]["schema_version"], "ai-summary-v1")
        self.assertNotIn("category_analysis", response.json()["summary"])
        self.assertEqual(
            set(response.json()["summary"]["actions"][0]),
            {"text", "recommendation_ids", "evidence_refs"},
        )
        self.assertTrue(response.json()["grounding_validated"])
        self.redis.set.assert_called_once()

    def test_new_report_endpoint_returns_v2(self):
        response = self.post_report({"model": "lite", "detail": "detailed"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["detail"], "detailed")
        self.assertEqual(response.json()["summary"]["schema_version"], "ai-report-v2")

    def test_second_same_depth_request_uses_cache(self):
        first = self.post_report({"model": "lite", "detail": "detailed"})
        cached_payload = self.redis.set.call_args.args[1]
        self.redis.get.return_value = cached_payload
        second = self.post_report({"model": "lite", "detail": "detailed"})
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertTrue(second.json()["cached"])
        self.assertEqual(self.app.state.ai_provider.summarize.call_count, 1)

    def test_detail_values_and_model_are_independent(self):
        for detail in ("brief", "detailed", "expert"):
            with self.subTest(detail=detail):
                response = self.post_report({"model": "pro", "detail": detail})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["mode"], "pro")
                self.assertEqual(response.json()["detail"], detail)
        self.assertEqual(self.post_report({"model": "lite", "detail": "unknown"}).status_code, 422)

    def test_cache_key_differs_by_detail(self):
        from sourcehealth.api.routers.ai_summary import _cache_key
        self.assertNotEqual(
            _cache_key(self.analysis_id, "pro", "brief"),
            _cache_key(self.analysis_id, "pro", "expert"),
        )
        self.assertNotEqual(
            _cache_key(self.analysis_id, "flash", "brief"),
            _cache_key(self.analysis_id, "pro", "brief"),
        )

    def test_authentication_and_terminal_status_are_required(self):
        self.app.state.auth.current_user.return_value = None
        self.assertEqual(self.post().status_code, 401)
        self.app.state.auth.current_user.return_value = {"id": str(uuid4())}
        self.run.status = "analyzing"
        self.assertEqual(self.post().status_code, 409)


if __name__ == "__main__":
    unittest.main()
