"""Deep repository analytics are bounded, deterministic, and privacy-safe."""

import json
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import Mock, patch

from sourcehealth.application.pipeline import analyze_context
from sourcehealth.core import AnalyzerResult
from sourcehealth.core.domain import DataAvailability as A
from sourcehealth.insights import (
    MAX_HISTORY_COMMITS,
    MAX_PATH_TOUCHES,
    DeepGitCollector,
    summarize_contributors,
    summarize_ownership,
)
from sourcehealth.markdown import render_markdown
from sourcehealth.recommendations.mvp import recommend
from sourcehealth.scoring.engine import ScoringEngine
from sourcehealth.scoring.mvp import MVPPolicy
from tests.mvp_fixtures import mvp_context, runtime_payload


def insights_metrics(**updates):
    values = {
        "sampled_commits": 10, "history_complete": True, "contributors_count": 2,
        "top_contributor_share": 0.9, "top_2_contributors_share": 1.0,
        "top_3_contributors_share": 1.0, "contributor_distribution": [],
        "bus_factor_proxy": 1, "bus_factor_threshold": 0.5,
        "bus_factor_basis": "commit_concentration", "bus_factor_sample_commits": 10,
        "bus_factor_complete": True, "bus_factor_reason": None,
        "ownership_groups": [], "ownership_complete": True, "ownership_sample_commits": 10,
        "path_touches_observed": 10, "deep_analytics_ms": 1,
        "dependency_manifest_count": 0, "dependency_lockfile_count": 0,
        "ecosystems_detected": [], "lockfile_coverage": None,
        "dependency_update_automation": False, "security_policy_present": False,
        "branch_policy_present": False, "review_policy_present": False,
        "license_policy_present": False, "codeowners_present": False,
        "contributing_present": False, "snapshot_complete": True,
    }
    values.update(updates)
    return values


class RepositoryInsightsTests(unittest.TestCase):
    def test_contributor_concentration_examples_and_small_sample(self):
        for counts, expected_factor, expected_share in (
            ([91, 9], 1, 0.91), ([45, 35, 20], 2, 0.45), ([25, 25, 25, 25], 2, 0.25),
        ):
            identities = [f"id-{index}" for index, count in enumerate(counts) for _ in range(count)]
            metrics, _ = summarize_contributors(identities, history_complete=True)
            self.assertEqual(metrics["bus_factor_proxy"], expected_factor)
            self.assertEqual(metrics["top_contributor_share"], expected_share)
        metrics, _ = summarize_contributors(["a"] * 4, history_complete=True)
        self.assertIsNone(metrics["bus_factor_proxy"])
        self.assertEqual(metrics["bus_factor_reason"], "insufficient_commit_sample")

    def test_large_history_and_ownership_are_bounded(self):
        metrics, aliases = summarize_contributors(["a"] * MAX_HISTORY_COMMITS, history_complete=False)
        self.assertEqual(metrics["sampled_commits"], MAX_HISTORY_COMMITS)
        self.assertFalse(metrics["history_complete"])
        touches = [("a", f"frontend/file-{index}.ts") for index in range(MAX_PATH_TOUCHES + 1)]
        ownership = summarize_ownership(touches, aliases, complete=False, sampled_commits=1000)
        self.assertEqual(ownership["path_touches_observed"], MAX_PATH_TOUCHES)
        self.assertFalse(ownership["ownership_complete"])

    def test_collector_requests_only_bounded_history(self):
        identity_record = b"Private Name\x1fprivate-email@example.invalid\x00"
        history = identity_record * (MAX_HISTORY_COMMITS + 1)
        ownership = b"\x1ePrivate Name\x1fprivate-email@example.invalid\x00\nfrontend/app.py\x00"
        calls = []
        def fake_git(root, *args, timeout=10):
            calls.append(args)
            return ownership if "--name-only" in args else history
        with patch("sourcehealth.insights.git", side_effect=fake_git):
            metrics = DeepGitCollector().collect(Path("."))
        self.assertEqual(metrics["sampled_commits"], MAX_HISTORY_COMMITS)
        self.assertFalse(metrics["history_complete"])
        self.assertTrue(any(f"--max-count={MAX_HISTORY_COMMITS + 1}" in call for call in calls))
        serialized = json.dumps(metrics)
        self.assertNotIn("Private Name", serialized)
        self.assertNotIn("private-email@example.invalid", serialized)

    def test_ownership_aggregates_top_level_groups(self):
        _, aliases = summarize_contributors(["a"] * 8 + ["b"] * 2, history_complete=True)
        touches = [("a", f"frontend/{index}.ts") for index in range(8)] + [
            ("b", f"frontend/{index}.ts") for index in range(2)] + [
            ("a", "backend/a.py"), ("b", "backend/b.py")]
        groups = summarize_ownership(touches, aliases, complete=True)["ownership_groups"]
        frontend = next(item for item in groups if item["path_group"] == "frontend/")
        backend = next(item for item in groups if item["path_group"] == "backend/")
        self.assertEqual(frontend["dominant_share"], 0.8)
        self.assertEqual(backend["dominant_share"], 0.5)

    def test_recommendations_require_complete_absence_and_manifests(self):
        check = AnalyzerResult("repository_insights", metrics=insights_metrics(
            dependency_manifest_count=3, ecosystems_detected=["python"], lockfile_coverage=0.0),
            source="git_snapshot", category=None)
        from sourcehealth.core.domain import Evidence
        check.evidence = [Evidence("insights:repository", "git_snapshot", "repository_insights", "a" * 40, "safe")]
        ids = {item.id for item in recommend({"repository_insights": check})}
        self.assertTrue({"insights:bus-factor", "insights:security-policy", "insights:codeowners",
                         "insights:contributing", "insights:branch-policy", "insights:review-policy",
                         "insights:dependency-locks", "insights:dependency-updates",
                         "insights:license-policy"} <= ids)
        check.metrics["snapshot_complete"] = False
        ids = {item.id for item in recommend({"repository_insights": check})}
        self.assertNotIn("insights:security-policy", ids)
        self.assertNotIn("insights:dependency-locks", ids)
        check.metrics.update(snapshot_complete=True, dependency_manifest_count=0, lockfile_coverage=None)
        ids = {item.id for item in recommend({"repository_insights": check})}
        self.assertNotIn("insights:dependency-locks", ids)

    def test_supplemental_check_does_not_change_health(self):
        report = analyze_context(mvp_context(), include_code=True, with_mvp=True,
                                 runtime=Mock(analyze=Mock(return_value=runtime_payload())))
        before = deepcopy(report)
        ScoringEngine(MVPPolicy()).apply(before)
        report.checks["repository_insights"] = AnalyzerResult(
            "repository_insights", status="partial", availability=A.PARTIAL,
            source="git_snapshot", metrics=insights_metrics(history_complete=False))
        ScoringEngine(MVPPolicy()).apply(report)
        self.assertEqual(report.health_score, before.health_score)
        self.assertEqual(report.category_scores, before.category_scores)

    def test_public_outputs_never_contain_private_identity(self):
        marker_name, marker_email = "VERY_PRIVATE_AUTHOR_NAME", "private-email@example.invalid"
        metrics, _ = summarize_contributors([marker_name + marker_email] * 5, history_complete=True)
        serialized = json.dumps(metrics)
        self.assertNotIn(marker_name, serialized)
        self.assertNotIn(marker_email, serialized)
        report = {
            "schema_version": "3.0", "repository": {"organization_slug": "safe", "repository_slug": "repo",
            "canonical_url": "https://sourcecraft.dev/safe/repo"}, "completed_at": "2026-01-01T00:00:00+00:00",
            "scoring_policy_version": "mvp-score-v1.2", "health_score": None, "category_scores": {},
            "recommendations": [], "checks": {"repository_insights": {"availability": "available",
            "metrics": insights_metrics(**metrics), "findings": [], "evidence": []}}}
        markdown = render_markdown(report)
        self.assertNotIn(marker_name, markdown)
        self.assertNotIn(marker_email, markdown)


if __name__ == "__main__":
    unittest.main()
