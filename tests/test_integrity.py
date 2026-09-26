"""Integrity signals expose low-confidence patterns without changing scores."""

import unittest
from types import SimpleNamespace
from uuid import uuid4

from sourcehealth.integrity import derive_signals


def run(*, health=70, commits=0, days=0, ci_score=40, ci_runs=10, coverage_names=(),
        policy="mvp-score-v1.2"):
    categories = {name: {"score": 80, "availability": "available"} for name in coverage_names}
    categories["cicd"] = {"score": ci_score, "availability": "available"}
    return SimpleNamespace(id=uuid4(), health_score=health, scoring_policy_version=policy,
                           category_scores=categories, results={"checks": {
                               "git_activity": {"metrics": {"commits_last_30_days": commits,
                                                              "active_days_last_30_days": days}},
                               "cicd": {"metrics": {"runs_observed": ci_runs, "success_rate": 1.0}},
                           }})


class IntegrityTests(unittest.TestCase):
    def ids(self, *args): return {item["id"] for item in derive_signals(*args)}

    def test_commit_burst_and_healthy_spread(self):
        self.assertIn("commit_burst", self.ids(run(commits=20, days=1)))
        self.assertNotIn("commit_burst", self.ids(run(commits=20, days=8)))

    def test_low_sample_and_well_sampled_ci(self):
        self.assertIn("low_sample_ci", self.ids(run(ci_score=100, ci_runs=1)))
        self.assertNotIn("low_sample_ci", self.ids(run(ci_score=100, ci_runs=20)))

    def test_score_and_coverage_jumps(self):
        previous = run(health=50, coverage_names=("documentation",))
        current = run(health=80, coverage_names=("documentation", "cicd", "security", "activity", "issues"))
        signals = derive_signals(current, previous)
        by_id = {item["id"]: item for item in signals}
        self.assertIn("score_jump", by_id)
        self.assertTrue(by_id["score_jump"]["facts"]["coverage_changed"])
        self.assertIn("coverage_jump", by_id)
        self.assertNotIn("score_jump", self.ids(run(health=60), run(health=50)))

    def test_missing_or_no_data_metrics_do_not_fabricate_flags(self):
        self.assertEqual(derive_signals(None), [])
        empty = run()
        empty.results = {"checks": {}}
        empty.category_scores = {"cicd": {"score": None, "availability": "no_data"}}
        self.assertEqual(derive_signals(empty), [])

    def test_policy_change_suppresses_jumps(self):
        previous = run(health=50, policy="mvp-score-v1.1", coverage_names=("documentation",))
        current = run(health=90, policy="mvp-score-v1.2",
                      coverage_names=("documentation", "security", "activity", "issues"))
        self.assertTrue({"score_jump", "coverage_jump"}.isdisjoint(self.ids(current, previous)))

        previous = run(health=50, policy="mvp-score-v1.2")
        self.assertIn("score_jump", self.ids(current, previous))
