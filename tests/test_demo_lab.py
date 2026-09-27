"""Tests for the interactive SourceHealth Lab / demo simulator.

Verifies:
1. Canonical mvp-score-v1.2 aggregation semantics (all 100 -> 100.0, NO_DATA != 0, insufficient coverage -> null).
2. Category score changes deterministically update Health.
3. Presets are deterministic and valid.
4. API endpoints POST /api/v1/demo/simulate, GET /api/v1/demo/presets, GET /api/v1/demo/badge.svg.
5. Zero database persistence, zero external calls (no SourceCraft, no AI).
"""

import unittest

from starlette.testclient import TestClient

from sourcehealth.api.app import create_app
from sourcehealth.scoring.mvp import DEMO_PRESETS, WEIGHTS, calculate_mvp_health
from sourcehealth.settings import Settings


class DemoLabScoringTests(unittest.TestCase):
    def test_all_six_100_yields_perfect_health(self):
        scores = {k: 100.0 for k in WEIGHTS}
        result = calculate_mvp_health(scores)
        self.assertEqual(result["health_score"], 100.0)
        self.assertEqual(result["coverage"], 100.0)
        self.assertTrue(result["eligible"])
        self.assertEqual(result["measurable_count"], 6)
        self.assertEqual(result["active_weight"], 100)

    def test_no_data_does_not_become_zero(self):
        # When security is NO_DATA (None) and others are 100
        # If security were 0, health would be: (100*80 + 0*20) / 100 = 80.0
        # With proper renormalization: (100*80) / 80 = 100.0
        scores = {
            "documentation": 100.0,
            "cicd": 100.0,
            "security": None,
            "activity": 100.0,
            "issues": 100.0,
            "code_health": 100.0,
        }
        result = calculate_mvp_health(scores)
        self.assertEqual(result["health_score"], 100.0)
        self.assertEqual(result["coverage"], 80.0)
        self.assertTrue(result["eligible"])
        self.assertEqual(result["measurable_count"], 5)
        self.assertEqual(result["active_weight"], 80)
        self.assertFalse(result["categories"]["security"]["available"])
        self.assertIsNone(result["categories"]["security"]["score"])

    def test_category_score_change_is_deterministic(self):
        base_scores = {k: 80.0 for k in WEIGHTS}
        base_result = calculate_mvp_health(base_scores)
        self.assertEqual(base_result["health_score"], 80.0)

        # Increasing documentation from 80 to 100 (+20 on a weight of 15 out of 100) -> +3.0 to overall
        updated_scores = dict(base_scores)
        updated_scores["documentation"] = 100.0
        updated_result = calculate_mvp_health(updated_scores)
        self.assertEqual(updated_result["health_score"], 83.0)

    def test_insufficient_coverage_gate_three_categories(self):
        # Only 2 categories available: documentation (15) + cicd (15) = 30 weight
        scores = {
            "documentation": 80.0,
            "cicd": 90.0,
            "security": None,
            "activity": None,
            "issues": None,
            "code_health": None,
        }
        result = calculate_mvp_health(scores)
        self.assertIsNone(result["health_score"])
        self.assertFalse(result["eligible"])
        self.assertEqual(result["measurable_count"], 2)
        self.assertEqual(result["active_weight"], 30)
        self.assertIn("Health не рассчитывается", result["explanation"])

    def test_insufficient_coverage_gate_fifty_percent_weight(self):
        # 3 categories available, but weights: doc(15) + cicd(15) + act(15) = 45 < 50
        scores = {
            "documentation": 80.0,
            "cicd": 90.0,
            "security": None,
            "activity": 70.0,
            "issues": None,
            "code_health": None,
        }
        result = calculate_mvp_health(scores)
        self.assertIsNone(result["health_score"])
        self.assertFalse(result["eligible"])
        self.assertEqual(result["measurable_count"], 3)
        self.assertEqual(result["active_weight"], 45)

    def test_sufficient_coverage_gate_three_categories_with_fifty_weight(self):
        # 3 categories: security(20) + code_health(20) + documentation(15) = 55 >= 50
        scores = {
            "documentation": 100.0,
            "cicd": None,
            "security": 100.0,
            "activity": None,
            "issues": None,
            "code_health": 100.0,
        }
        result = calculate_mvp_health(scores)
        self.assertTrue(result["eligible"])
        self.assertEqual(result["health_score"], 100.0)
        self.assertEqual(result["active_weight"], 55)

    def test_all_presets_are_deterministic_and_valid(self):
        for preset in DEMO_PRESETS:
            res = calculate_mvp_health(preset["scores"])
            if preset["id"] == "low_data":
                self.assertFalse(res["eligible"])
                self.assertIsNone(res["health_score"])
            else:
                self.assertTrue(res["eligible"])
                self.assertIsNotNone(res["health_score"])
                self.assertGreaterEqual(res["health_score"], 0.0)
                self.assertLessEqual(res["health_score"], 100.0)


class DemoLabApiTests(unittest.TestCase):
    def setUp(self):
        # Lightweight app with dummy sessions/redis to ensure no dependencies are hit
        from unittest.mock import MagicMock
        self.dummy_sessions = MagicMock()
        self.dummy_redis = MagicMock()
        settings = Settings(
            database_url="postgresql+psycopg://test:test@localhost:5432/test",
            redis_url="redis://localhost:6379/0",
            sourcecraft_token="test-token",
            yandex_client_id="test-id",
            yandex_client_secret="test-secret",
            auth_redirect_uri="http://localhost:5173/auth/callback",
            secret_key="test-key-32-bytes-minimum-length-ok!",
        )
        self.app = create_app(settings, sessions=self.dummy_sessions, redis=self.dummy_redis)
        self.client = TestClient(self.app)

    def test_simulate_endpoint_calculates_without_db(self):
        # Verify dummy_sessions is NOT called at all
        response = self.client.post(
            "/api/v1/demo/simulate",
            json={
                "scores": {
                    "documentation": 80.0,
                    "cicd": 90.0,
                    "security": None,
                    "activity": 70.0,
                    "issues": 60.0,
                    "code_health": 85.0,
                }
            },
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["policy_version"], "mvp-score-v1.2")
        self.assertTrue(data["eligible"])
        self.assertEqual(data["measurable_count"], 5)
        self.assertEqual(data["active_weight"], 80)
        self.assertEqual(data["coverage"], 80.0)
        # Expected: (15*80 + 15*90 + 15*70 + 15*60 + 20*85) / 80 = (1200+1350+1050+900+1700)/80 = 6200/80 = 77.5
        self.assertEqual(data["health_score"], 77.5)
        self.assertFalse(data["categories"]["security"]["available"])
        self.assertIsNone(data["categories"]["security"]["score"])
        self.dummy_sessions.assert_not_called()
        self.dummy_redis.assert_not_called()

    def test_presets_endpoint(self):
        response = self.client.get("/api/v1/demo/presets")
        self.assertEqual(response.status_code, 200)
        presets = response.json()
        self.assertEqual(len(presets), 6)
        preset_ids = [p["id"] for p in presets]
        self.assertIn("healthy", preset_ids)
        self.assertIn("no_security", preset_ids)
        self.assertIn("broken_ci", preset_ids)
        self.assertIn("poor_docs", preset_ids)
        self.assertIn("high_debt", preset_ids)
        self.assertIn("low_data", preset_ids)

    def test_badge_svg_endpoint(self):
        # Health 78 -> green (#2e7d32)
        response = self.client.get("/api/v1/demo/badge.svg?score=78")
        self.assertEqual(response.status_code, 200)
        self.assertIn("image/svg+xml", response.headers["Content-Type"])
        self.assertIn("SourceHealth", response.text)
        self.assertIn("78", response.text)
        self.assertIn("#2e7d32", response.text)

        # No score -> grey (#888888)
        response_null = self.client.get("/api/v1/demo/badge.svg")
        self.assertEqual(response_null.status_code, 200)
        self.assertIn("no score", response_null.text)
        self.assertIn("#888888", response_null.text)


if __name__ == "__main__":
    unittest.main()
