"""Unit tests for Achievements v2 and Profile Summary."""

import unittest
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

from sourcehealth.achievements.service import DEFINITIONS, derive


class AchievementsV2Tests(unittest.TestCase):
    def make_run(self, score=None, categories=None, completed=None, repo_id=None, profile="mvp-v1"):
        return SimpleNamespace(
            id=uuid4(),
            repository_id=repo_id or uuid4(),
            status="completed",
            profile=profile,
            queued_at=completed,
            completed_at=completed,
            health_score=score,
            scoring_policy_version="mvp-score-v1.2",
            category_scores=categories or {},
            results={"checks": {"sourcecraft_appsec": {
                "source": "sourcecraft_appsec",
                "availability": "available",
                "metrics": {"complete": True},
            }}},
        )

    def test_definitions_metadata_complete(self):
        self.assertGreaterEqual(len(DEFINITIONS), 14)
        for item in DEFINITIONS:
            self.assertIn(item.category, {"start", "quality", "security", "automation", "progress", "exploration"})
            self.assertIn(item.rarity, {"common", "uncommon", "rare", "epic"})
            self.assertTrue(len(item.icon_key) > 0)
            self.assertTrue(len(item.hint) > 0)

    def test_full_house_requires_all_six_numeric(self):
        tracked = datetime(2026, 1, 2, tzinfo=UTC)
        relation = SimpleNamespace(created_at=tracked, repository_id=uuid4())

        # All 6 numeric -> unlocked
        all_six = {
            "security": {"score": 85, "availability": "available"},
            "cicd": {"score": 90, "availability": "available"},
            "activity": {"score": 75, "availability": "available"},
            "documentation": {"score": 80, "availability": "available"},
            "issues": {"score": 70, "availability": "available"},
            "code_health": {"score": 95, "availability": "available"},
        }
        run_full = self.make_run(82.5, all_six, tracked + timedelta(hours=1), repo_id=relation.repository_id)
        res_full = {item["id"]: item for item in derive([(run_full, relation)])}
        self.assertTrue(res_full["full_house"]["unlocked"])
        self.assertEqual(res_full["full_house"]["unlocked_at"], run_full.completed_at)

        # 5 numeric + 1 NO_DATA (score None) -> locked
        five_only = dict(all_six)
        five_only["security"] = {"score": None, "availability": "no_data"}
        run_partial = self.make_run(80.0, five_only, tracked + timedelta(hours=1), repo_id=relation.repository_id)
        res_partial = {item["id"]: item for item in derive([(run_partial, relation)])}
        self.assertFalse(res_partial["full_house"]["unlocked"])

        # Numeric score of 0 (e.g. cicd = 0) is numeric -> unlocked
        six_with_zero = dict(all_six)
        six_with_zero["cicd"] = {"score": 0, "availability": "not_configured"}
        run_zero = self.make_run(65.0, six_with_zero, tracked + timedelta(hours=1), repo_id=relation.repository_id)
        res_zero = {item["id"]: item for item in derive([(run_zero, relation)])}
        self.assertTrue(res_zero["full_house"]["unlocked"])

    def test_perfect_health_strictly_hundred(self):
        tracked = datetime(2026, 1, 2, tzinfo=UTC)
        relation = SimpleNamespace(created_at=tracked, repository_id=uuid4())

        run_99 = self.make_run(99.99, completed=tracked + timedelta(hours=1), repo_id=relation.repository_id)
        res_99 = {item["id"]: item for item in derive([(run_99, relation)])}
        self.assertFalse(res_99["perfect_health"]["unlocked"])

        run_100 = self.make_run(100.0, completed=tracked + timedelta(hours=2), repo_id=relation.repository_id)
        res_100 = {item["id"]: item for item in derive([(run_100, relation)])}
        self.assertTrue(res_100["perfect_health"]["unlocked"])
        self.assertEqual(res_100["perfect_health"]["unlocked_at"], run_100.completed_at)

    def test_triple_tracker_derived_from_tracked_repositories(self):
        repo1, repo2, repo3 = uuid4(), uuid4(), uuid4()
        now = datetime(2026, 1, 1, tzinfo=UTC)
        links = [
            SimpleNamespace(repository_id=repo1, created_at=now),
            SimpleNamespace(repository_id=repo2, created_at=now + timedelta(hours=1)),
            SimpleNamespace(repository_id=repo3, created_at=now + timedelta(hours=2)),
        ]

        # 2 tracked -> locked with progress 2 / 3
        res_2 = {item["id"]: item for item in derive([], tracked_repositories=links[:2])}
        self.assertFalse(res_2["triple_tracker"]["unlocked"])
        self.assertEqual(res_2["triple_tracker"]["progress_current"], 2)
        self.assertEqual(res_2["triple_tracker"]["progress_target"], 3)
        self.assertEqual(res_2["triple_tracker"]["progress_percent"], 66.7)

        # 3 tracked -> unlocked
        res_3 = {item["id"]: item for item in derive([], tracked_repositories=links)}
        self.assertTrue(res_3["triple_tracker"]["unlocked"])
        self.assertEqual(res_3["triple_tracker"]["unlocked_at"], now + timedelta(hours=2))
        self.assertEqual(res_3["triple_tracker"]["progress_current"], 3)

    def test_portfolio_keeper_requires_five_analyzed_tracked_repos(self):
        tracked = datetime(2026, 1, 1, tzinfo=UTC)
        repo_ids = [uuid4() for _ in range(5)]
        links = [SimpleNamespace(repository_id=rid, created_at=tracked) for rid in repo_ids]

        runs = [
            self.make_run(70, completed=tracked + timedelta(days=i), repo_id=repo_ids[i])
            for i in range(4)
        ]
        pairs = list(zip(runs, links[:4]))

        # 4 analyzed repos -> locked with progress 4 / 5
        res_4 = {item["id"]: item for item in derive(pairs, tracked_repositories=links)}
        self.assertFalse(res_4["portfolio_keeper"]["unlocked"])
        self.assertEqual(res_4["portfolio_keeper"]["progress_current"], 4)
        self.assertEqual(res_4["portfolio_keeper"]["progress_target"], 5)
        self.assertEqual(res_4["portfolio_keeper"]["progress_percent"], 80.0)

        # 5 analyzed repos -> unlocked
        fifth_run = self.make_run(75, completed=tracked + timedelta(days=4), repo_id=repo_ids[4])
        pairs.append((fifth_run, links[4]))
        res_5 = {item["id"]: item for item in derive(pairs, tracked_repositories=links)}
        self.assertTrue(res_5["portfolio_keeper"]["unlocked"])
        self.assertEqual(res_5["portfolio_keeper"]["unlocked_at"], fifth_run.completed_at)
        self.assertEqual(res_5["portfolio_keeper"]["progress_current"], 5)

    def test_persistent_maintainer_requires_five_runs(self):
        tracked = datetime(2026, 1, 1, tzinfo=UTC)
        relation = SimpleNamespace(created_at=tracked, repository_id=uuid4())
        runs = [
            self.make_run(70, completed=tracked + timedelta(days=i), repo_id=relation.repository_id)
            for i in range(5)
        ]
        pairs = [(r, relation) for r in runs]

        # 4 runs -> locked with progress 4 / 5 (persistent_maintainer) and 4 / 10 (maintainer)
        res_4 = {item["id"]: item for item in derive(pairs[:4])}
        self.assertFalse(res_4["persistent_maintainer"]["unlocked"])
        self.assertEqual(res_4["persistent_maintainer"]["progress_current"], 4)
        self.assertEqual(res_4["persistent_maintainer"]["progress_target"], 5)
        self.assertEqual(res_4["persistent_maintainer"]["progress_percent"], 80.0)
        self.assertFalse(res_4["maintainer"]["unlocked"])
        self.assertEqual(res_4["maintainer"]["progress_current"], 4)
        self.assertEqual(res_4["maintainer"]["progress_target"], 10)
        self.assertEqual(res_4["maintainer"]["progress_percent"], 40.0)

        # 5 runs -> persistent_maintainer unlocked
        res_5 = {item["id"]: item for item in derive(pairs)}
        self.assertTrue(res_5["persistent_maintainer"]["unlocked"])
        self.assertEqual(res_5["persistent_maintainer"]["unlocked_at"], runs[4].completed_at)
        self.assertFalse(res_5["maintainer"]["unlocked"])
        self.assertEqual(res_5["maintainer"]["progress_current"], 5)

    def test_clean_and_green_requires_appsec_and_cicd_hundred(self):
        tracked = datetime(2026, 1, 2, tzinfo=UTC)
        relation = SimpleNamespace(created_at=tracked, repository_id=uuid4())

        # CI 100 and AppSec 100 with official provenance -> unlocked
        cats_ok = {
            "security": {"score": 100, "availability": "available"},
            "cicd": {"score": 100, "availability": "available"},
        }
        run_ok = self.make_run(95.0, cats_ok, tracked + timedelta(hours=1), repo_id=relation.repository_id)
        res_ok = {item["id"]: item for item in derive([(run_ok, relation)])}
        self.assertTrue(res_ok["clean_and_green"]["unlocked"])
        self.assertTrue(res_ok["ci_wizard"]["unlocked"])
        self.assertTrue(res_ok["clean_scan"]["unlocked"])

        # CI 100 but AppSec 90 -> locked
        cats_ci_only = {
            "security": {"score": 90, "availability": "available"},
            "cicd": {"score": 100, "availability": "available"},
        }
        run_ci = self.make_run(85.0, cats_ci_only, tracked + timedelta(hours=1), repo_id=relation.repository_id)
        res_ci = {item["id"]: item for item in derive([(run_ci, relation)])}
        self.assertFalse(res_ci["clean_and_green"]["unlocked"])

        # CI 100 and Security 100 but non-official AppSec check -> locked
        run_spoofed = self.make_run(95.0, cats_ok, tracked + timedelta(hours=1), repo_id=relation.repository_id)
        run_spoofed.results = {"checks": {}}
        res_spoofed = {item["id"]: item for item in derive([(run_spoofed, relation)])}
        self.assertFalse(res_spoofed["clean_and_green"]["unlocked"])

    def test_boolean_achievements_have_no_misleading_progress(self):
        tracked = datetime(2026, 1, 2, tzinfo=UTC)
        relation = SimpleNamespace(created_at=tracked, repository_id=uuid4())
        run = self.make_run(79.0, completed=tracked + timedelta(hours=1), repo_id=relation.repository_id)
        res = {item["id"]: item for item in derive([(run, relation)])}

        # Health 79 does NOT mean 79% progress to healthy_project
        self.assertIsNone(res["healthy_project"]["progress_current"])
        self.assertIsNone(res["healthy_project"]["progress_target"])
        self.assertIsNone(res["healthy_project"]["progress_percent"])
        self.assertIsNone(res["perfect_health"]["progress_current"])
        self.assertIsNone(res["full_house"]["progress_current"])

    def test_no_pre_tracking_run_unlock(self):
        tracked = datetime(2026, 1, 10, tzinfo=UTC)
        relation = SimpleNamespace(created_at=tracked, repository_id=uuid4())
        old_run = self.make_run(100.0, completed=datetime(2026, 1, 5, tzinfo=UTC), repo_id=relation.repository_id)
        res = {item["id"]: item for item in derive([(old_run, relation)])}
        self.assertFalse(res["first_checkup"]["unlocked"])
        self.assertFalse(res["perfect_health"]["unlocked"])
        self.assertEqual(res["maintainer"]["progress_current"], 0)


    def test_official_health_achievements_require_mvp_v1_profile(self):
        tracked = datetime(2026, 1, 1, tzinfo=UTC)
        repo_id = uuid4()
        relation = SimpleNamespace(created_at=tracked, repository_id=repo_id)

        all_six = {
            "security": {"score": 85, "availability": "available"},
            "cicd": {"score": 90, "availability": "available"},
            "activity": {"score": 75, "availability": "available"},
            "documentation": {"score": 80, "availability": "available"},
            "issues": {"score": 70, "availability": "available"},
            "code_health": {"score": 95, "availability": "available"},
        }

        # 1. code-v1 Health=100 -> perfect_health locked
        run_code_v1 = self.make_run(100.0, completed=tracked + timedelta(hours=1), repo_id=repo_id, profile="code-v1")
        res_code = {item["id"]: item for item in derive([(run_code_v1, relation)])}
        self.assertFalse(res_code["perfect_health"]["unlocked"])

        # 2. platform-v1 six numeric categories -> full_house locked
        run_platform_v1 = self.make_run(85.0, all_six, tracked + timedelta(hours=1), repo_id=repo_id, profile="platform-v1")
        res_plat = {item["id"]: item for item in derive([(run_platform_v1, relation)])}
        self.assertFalse(res_plat["full_house"]["unlocked"])

        # 3. 5 non-mvp analyzed tracked repos -> portfolio_keeper locked
        repo_ids = [uuid4() for _ in range(5)]
        links = [SimpleNamespace(repository_id=rid, created_at=tracked) for rid in repo_ids]
        non_mvp_runs = [
            self.make_run(80.0, completed=tracked + timedelta(days=i), repo_id=repo_ids[i], profile="legacy-v0")
            for i in range(5)
        ]
        pairs_non_mvp = list(zip(non_mvp_runs, links))
        res_non_mvp_pk = {item["id"]: item for item in derive(pairs_non_mvp, tracked_repositories=links)}
        self.assertFalse(res_non_mvp_pk["portfolio_keeper"]["unlocked"])
        self.assertEqual(res_non_mvp_pk["portfolio_keeper"]["progress_current"], 0)

        # 4. Equivalent mvp-v1 cases -> unlocked
        run_mvp_100 = self.make_run(100.0, completed=tracked + timedelta(hours=1), repo_id=repo_id, profile="mvp-v1")
        res_mvp_100 = {item["id"]: item for item in derive([(run_mvp_100, relation)])}
        self.assertTrue(res_mvp_100["perfect_health"]["unlocked"])

        run_mvp_full = self.make_run(85.0, all_six, tracked + timedelta(hours=1), repo_id=repo_id, profile="mvp-v1")
        res_mvp_full = {item["id"]: item for item in derive([(run_mvp_full, relation)])}
        self.assertTrue(res_mvp_full["full_house"]["unlocked"])

        mvp_runs = [
            self.make_run(80.0, completed=tracked + timedelta(days=i), repo_id=repo_ids[i], profile="mvp-v1")
            for i in range(5)
        ]
        pairs_mvp = list(zip(mvp_runs, links))
        res_mvp_pk = {item["id"]: item for item in derive(pairs_mvp, tracked_repositories=links)}
        self.assertTrue(res_mvp_pk["portfolio_keeper"]["unlocked"])
        self.assertEqual(res_mvp_pk["portfolio_keeper"]["progress_current"], 5)


if __name__ == "__main__":
    unittest.main()
