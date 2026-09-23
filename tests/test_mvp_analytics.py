"""Контрольные сценарии метрик, policy, рекомендаций и unavailable coverage."""

import unittest
from copy import deepcopy
from dataclasses import replace
from unittest.mock import Mock

from sourcehealth.analyzers.analytics import CIAnalyzer, IssuesAnalyzer, PlatformActivityAnalyzer
from sourcehealth.application.pipeline import analyze_context
from sourcehealth.core.domain import DataAvailability as A
from sourcehealth.recommendations.mvp import recommend
from sourcehealth.scoring.engine import ScoringEngine
from sourcehealth.scoring.mvp import WEIGHTS, MVPPolicy
from tests.mvp_fixtures import appsec_fixture, mvp_context, runtime_payload


class MVPAnalyticsTests(unittest.TestCase):
    def setUp(self):
        self.context = mvp_context()

    def report(self):
        return analyze_context(self.context, include_code=True, with_mvp=True,
                               runtime=Mock(analyze=Mock(return_value=runtime_payload())))

    def score(self, report):
        ScoringEngine(MVPPolicy()).apply(report)
        return report

    def test_issues_healthy_empty_stale_and_partial(self):
        healthy = IssuesAnalyzer().analyze(self.context)
        self.assertEqual(healthy.metrics["median_first_external_response_hours"], 1)
        self.assertEqual(healthy.metrics["median_close_hours"], 24)
        self.assertEqual(healthy.metrics["closed_count"], 1)
        for mode in ("empty", "stale", "partial"):
            context = deepcopy(self.context)
            if mode == "empty":
                context.sourcecraft_facts["issues"]["items"] = []
            elif mode == "stale":
                context.sourcecraft_facts["issues"]["items"][0].update(status="initial", updated_at="2026-08-20T00:00:00+00:00")
            else:
                context.collection_statuses["issues"] = A.PARTIAL
            result = IssuesAnalyzer().analyze(context)
            if mode == "empty":
                self.assertEqual(result.metrics["open_count"], 0)
                self.assertIsNone(result.metrics["median_first_external_response_hours"])
            elif mode == "stale":
                self.assertEqual(result.metrics["stale_ratio"], 1)
            else:
                self.assertIsNone(result.metrics["open_count"])
                self.assertIsNone(result.metrics["stale_ratio"])
                self.assertEqual(result.metrics["observed_count"], 1)

    def test_ci_stable_failing_absent_unknown_and_partial(self):
        self.assertEqual(CIAnalyzer().analyze(self.context).metrics["success_rate"], 1)
        for mode in ("failed", "empty", "absent", "partial", "outage"):
            context = deepcopy(self.context)
            if mode == "failed":
                context.sourcecraft_facts["cicd"]["items"][0]["status"] = "failed"
            elif mode in {"empty", "absent"}:
                context.sourcecraft_facts["cicd"]["items"] = []
                if mode == "absent":
                    context.metadata["ci_configured"] = False
            else:
                context.collection_statuses["cicd"] = A.PARTIAL if mode == "partial" else A.SOURCE_UNAVAILABLE
            result = CIAnalyzer().analyze(context)
            if mode == "failed":
                self.assertEqual(result.metrics["success_rate"], 0)
            elif mode == "absent":
                self.assertEqual(result.availability, A.NOT_CONFIGURED)
                self.assertFalse(result.metrics["configured"])
            elif mode == "empty":
                self.assertIsNone(result.metrics["configured"])
            else:
                self.assertIsNone(result.metrics["success_rate"])
                self.assertNotEqual(result.availability, A.NOT_CONFIGURED)

    def test_unanswered_issues_lower_response_component_and_partial_is_unknown(self):
        healthy = self.score(self.report()).category_scores["issues"]["score"]
        issue = self.context.sourcecraft_facts["issues"]["items"][0]
        self.context.sourcecraft_facts["issues"]["items"].append({**issue, "id": "unanswered", "first_external_response_at": None})
        metrics = IssuesAnalyzer().analyze(self.context).metrics
        self.assertEqual(metrics["unanswered_count"], 1)
        self.assertEqual(metrics["external_response_rate"], 0.5)
        self.assertEqual(metrics["median_first_external_response_hours"], 1)  # Explicitly among answered.
        self.assertLess(self.score(self.report()).category_scores["issues"]["score"], healthy)
        issue["first_external_response_at"] = None
        metrics = IssuesAnalyzer().analyze(self.context).metrics
        self.assertEqual(metrics["unanswered_count"], 2)
        self.assertEqual(metrics["external_response_rate"], 0)
        self.assertIsNone(metrics["median_first_external_response_hours"])
        self.assertLess(self.score(self.report()).category_scores["issues"]["score"], healthy)
        issue["response_complete"] = False
        metrics = IssuesAnalyzer().analyze(self.context).metrics
        self.assertIsNone(metrics["unanswered_count"])
        self.assertIsNone(metrics["external_response_rate"])
        self.assertIsNone(metrics["median_first_external_response_hours"])

    def test_coverage_weight_is_not_category_count_or_full_scan_claim(self):
        from sourcehealth.scoring.coverage import score_coverage

        report = self.score(self.report())
        coverage = score_coverage(report.scoring_policy_version, report.category_scores)
        self.assertEqual(coverage["nominal_weight_percent"], 80)
        self.assertEqual(coverage["scored_categories"], 5)
        self.assertEqual(coverage["unscored_categories"], ["security"])
        report.category_scores["activity"]["availability"] = "partial"
        self.assertEqual(score_coverage(report.scoring_policy_version, report.category_scores)["partial_categories"], ["activity"])
        self.assertIsNone(score_coverage("future-unknown", report.category_scores))

    def test_empty_issues_are_observed_but_not_scored(self):
        self.context.sourcecraft_facts["issues"]["items"] = []
        report = self.score(self.report())
        self.assertEqual(report.checks["issues"].metrics["observed_count"], 0)
        self.assertEqual(report.category_scores["issues"]["availability"], "available")
        self.assertIsNone(report.category_scores["issues"]["score"])
        from sourcehealth.scoring.coverage import score_coverage
        self.assertEqual(score_coverage(report.scoring_policy_version, report.category_scores)[
            "nominal_weight_percent"], 65)

    def test_same_day_commit_burst_cannot_max_recent_activity(self):
        report = self.report()
        git = report.checks["git_activity"]
        git.metrics.update(commits_last_30_days=20, active_days_last_30_days=1, days_since_last_commit=0)
        burst = self.score(deepcopy(report)).category_scores["activity"]["score"]
        git.metrics["active_days_last_30_days"] = 5
        sustained = self.score(report).category_scores["activity"]["score"]
        self.assertLessEqual(burst, 80)
        self.assertGreater(sustained - burst, 15)

    def test_repository_scale_alone_does_not_change_score(self):
        report = self.report()
        baseline = self.score(deepcopy(report)).health_score
        report.checks["sast"].metrics["files_scanned"] = 10000
        report.checks["technical_debt"].metrics["code_files"] = 10000
        self.assertEqual(self.score(report).health_score, baseline)

    def test_sast_uses_code_density_and_includes_python_ast_findings(self):
        report = self.report()
        sast = report.checks["sast"]
        sast.metrics.update(code_files_analyzed=100, code_files_lexed=0,
                            python_files_parsed=2, summary={"high": 0, "medium": 2, "low": 0})
        small = self.score(deepcopy(report)).category_scores["code_health"]["score"]
        sast.metrics.update(code_files_analyzed=10000,
                            summary={"high": 0, "medium": 200, "low": 0})
        large = self.score(report).category_scores["code_health"]["score"]
        self.assertEqual(small, large)
        self.assertLess(small, 100)

    def test_platform_activity_complete_no_release_and_partial(self):
        result = PlatformActivityAnalyzer().analyze(self.context)
        self.assertEqual(result.metrics["pr_count"], 1)
        self.assertEqual(result.metrics["merged_count"], 1)

        self.context.sourcecraft_facts["releases"]["items"] = []
        result = PlatformActivityAnalyzer().analyze(self.context)
        self.assertEqual(result.metrics["release_count"], 0)
        self.assertIsNone(result.metrics["last_release"])
        self.context.collection_statuses["contributors"] = A.PARTIAL
        result = PlatformActivityAnalyzer().analyze(self.context)
        self.assertIsNone(result.metrics["contributors_count"])
        self.assertEqual(result.metrics["merged_count"], 1)

    def test_platform_provenance_distinguishes_entire_set_from_recent_window(self):
        self.context.sourcecraft_facts["pull_requests"]["items"][0]["updated_at"] = "2026-01-01T00:00:00+00:00"
        platform = PlatformActivityAnalyzer().analyze(self.context)
        self.assertEqual(platform.metrics["pr_count"], 1)
        self.assertEqual(platform.metrics["recent_pr_activity"], 0)
        for check in (platform, IssuesAnalyzer().analyze(self.context), CIAnalyzer().analyze(self.context)):
            self.assertNotIn("window_days", check.metadata)
            self.assertEqual(check.metadata["observation_scope"], "entire_collected_set")
            self.assertEqual(check.metadata["recent_window_days"], 30)
            self.assertIn("recent/stale", check.evidence[0].summary)
        self.assertEqual(IssuesAnalyzer().analyze(self.context).metadata["stale_threshold_days"], 30)

    def test_six_slots_security_unavailable_and_weighted_coverage(self):
        report = self.score(self.report())
        self.assertEqual(set(report.category_scores), set(WEIGHTS))
        self.assertIsNone(report.category_scores["security"]["score"])
        self.assertEqual(report.category_scores["security"]["availability"], "no_data")
        self.assertIsNotNone(report.health_score)
        expected = round(sum(WEIGHTS[k] * c["score"] for k, c in report.category_scores.items() if c["score"] is not None) / 80, 2)
        self.assertEqual(report.health_score, expected)
        report.checks.pop("sourcecraft_appsec")
        report.checks["official_test"] = appsec_fixture()
        self.score(report)
        self.assertEqual(report.category_scores["security"]["score"], 100)
        self.assertTrue(all(c["availability"] == "available" for c in report.category_scores.values()))

    def test_exact_minimum_nominal_coverage(self):
        report = self.report()
        report.checks = {key: value for key, value in report.checks.items()
                         if key in {"documentation", "cicd", "issues"}}
        self.score(report)
        self.assertEqual(sum(c["score"] is not None for c in report.category_scores.values()), 3)
        self.assertIsNone(report.health_score)  # 3 categories but only 45 nominal weight.
        full = self.report()
        report.checks.pop("issues")
        report.checks["technical_debt"] = full.checks["technical_debt"]
        report.checks["sast"] = full.checks["sast"]
        self.score(report)
        self.assertIsNotNone(report.health_score)  # Exactly 3 categories and 50 weight.

    def test_outage_insufficient_coverage_and_no_data(self):
        report = self.report()
        report.checks["issues"].status = "partial"
        report.checks["issues"].availability = A.SOURCE_UNAVAILABLE
        self.score(report)
        self.assertIsNone(report.category_scores["issues"]["score"])
        self.assertIsNotNone(report.health_score)
        report.checks = {k: v for k, v in report.checks.items() if k in {"documentation", "cicd", "issues"}}
        self.score(report)
        self.assertIsNone(report.health_score)
        report.checks = {}
        self.score(report)
        self.assertTrue(all(c["score"] is None for c in report.category_scores.values()))

    def test_monotonic_category_deterioration_and_repair(self):
        mutations = [
            ("documentation", "documentation", lambda c: c.metrics.update(run_instructions=False)),
            ("cicd", "cicd", lambda c: c.metrics.update(success_rate=0.1)),
            ("issues", "issues", lambda c: c.metrics.update(stale_ratio=1)),
            ("git_activity", "activity", lambda c: c.metrics.update(commits_last_30_days=0, days_since_last_commit=180)),
            ("technical_debt", "code_health", lambda c: c.metrics.update(marker_density=10, large_files=10, oldest_marker_age_days=400)),
            ("sast", "code_health", lambda c: c.metrics.update(summary={"high": 10, "medium": 0, "low": 0})),
            ("official_test", "security", lambda c: c.metrics.update(open_by_severity={"critical": 2, "high": 2, "medium": 5, "low": 10})),
        ]
        for key, category, mutate in mutations:
            with self.subTest(category=category, key=key):
                report = self.report()
                report.checks["official_test"] = appsec_fixture()
                good = self.score(deepcopy(report)).category_scores[category]["score"]
                original = deepcopy(report.checks[key])
                mutate(report.checks[key])
                bad = self.score(report).category_scores[category]["score"]
                self.assertLess(bad, good)
                report.checks[key] = original
                self.assertEqual(self.score(report).category_scores[category]["score"], good)

    def test_recommendations_have_real_refs_and_no_fake_security_or_impact(self):
        report = self.report()
        report.checks["documentation"].metrics["run_instructions"] = False
        report.checks["cicd"].metrics["success_rate"] = 0.1
        report.checks["issues"].metrics["stale_open_count"] = 3
        report.checks["technical_debt"].metrics["todo_count"] = 10
        items = recommend(report.checks)
        self.assertEqual({r.id for r in items}, {"docs:run_instructions", "ci:failures", "issues:stale", "debt:markers"})
        evidence = {e.id for c in report.checks.values() for e in c.evidence}
        self.assertTrue(all(set(r.evidence_refs) <= evidence for r in items))
        self.assertTrue(all(r.expected_impact in {"High", "Medium", "Low"} for r in items))
        self.assertFalse(any(r.category == "security" for r in items))

    def test_partial_snapshot_preserves_platform_without_scoring_incomplete_docs(self):
        payload = runtime_payload()
        payload["complete"] = False
        payload["checks"]["documentation"].update(status="partial", availability="partial")
        payload["checks"]["documentation"]["metadata"]["complete"] = False
        report = analyze_context(self.context, include_code=True, with_mvp=True, runtime=Mock(analyze=Mock(return_value=payload)))
        self.score(report)
        self.assertIsNone(report.category_scores["documentation"]["score"])
        self.assertEqual(report.checks["issues"].status, "ok")

    def test_replay_does_not_depend_on_wall_clock_or_popularity(self):
        context = replace(self.context, sourcecraft_facts={**self.context.sourcecraft_facts, "likes": 1000000})
        first = self.score(self.report())
        second = analyze_context(context, include_code=True, with_mvp=True, runtime=Mock(analyze=Mock(return_value=runtime_payload())))
        self.score(second)
        self.assertEqual(first.category_scores, second.category_scores)
        self.assertEqual(first.health_score, second.health_score)
