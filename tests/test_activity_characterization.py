import unittest
from copy import deepcopy
from unittest.mock import Mock

from sourcehealth.application.pipeline import analyze_context
from sourcehealth.core.domain import DataAvailability
from sourcehealth.scoring.engine import ScoringEngine
from sourcehealth.scoring.mvp import MVPPolicy, activity_components
from tests.mvp_fixtures import mvp_context, runtime_payload


class ActivityCharacterizationTests(unittest.TestCase):
    def report(self):
        return analyze_context(mvp_context(), include_code=True, with_mvp=True,
                               runtime=Mock(analyze=Mock(return_value=runtime_payload())))

    def scenario(self, *, commits, days, age, contributors=0, pulls=0, release=None):
        report = self.report()
        git = report.checks["git_activity"]
        git.metrics.update(total_commits=max(commits, 1), commits_last_30_days=commits,
                           active_days_last_30_days=days, days_since_last_commit=age)
        platform = report.checks["platform_activity"]
        platform.metrics.update(recent_pr_activity=pulls, contributors_count=contributors,
                                release_count=1 if release else 0, last_release=release)
        components, values = activity_components(git, platform)
        ScoringEngine(MVPPolicy()).apply(report)
        return report.category_scores["activity"]["score"], values, components

    def test_v12_characterization_scenarios(self):
        reference = "2026-09-19T00:00:00+00:00"
        scenarios = {
            "A": self.scenario(commits=20, days=5, age=0, contributors=3, pulls=5, release=reference),
            "B": self.scenario(commits=20, days=1, age=0, contributors=3, pulls=5, release=reference),
            "C": self.scenario(commits=10, days=5, age=15, contributors=2, pulls=1),
            "D": self.scenario(commits=10, days=5, age=29, contributors=2, pulls=1),
            "E": self.scenario(commits=0, days=0, age=31, contributors=2, pulls=1),
            "F": self.scenario(commits=0, days=0, age=56, contributors=2),
            "G": self.scenario(commits=0, days=0, age=90, contributors=2),
            "H": self.scenario(commits=0, days=0, age=180, contributors=2),
        }
        self.assertEqual(scenarios["A"][0], 100)
        self.assertLessEqual(scenarios["B"][0], 80)
        self.assertGreater(scenarios["D"][0] - scenarios["E"][0], 20)
        self.assertEqual(scenarios["F"][0], 18.44)
        self.assertEqual(scenarios["G"][0], scenarios["H"][0])

    def test_empty_and_partial_git_are_zero_and_no_data(self):
        empty = self.report()
        git = empty.checks["git_activity"]
        git.metrics.update(total_commits=0, commits_last_30_days=0, active_days_last_30_days=0,
                           days_since_last_commit=None)
        ScoringEngine(MVPPolicy()).apply(empty)
        self.assertEqual(empty.category_scores["activity"]["score"], 0)

        partial = deepcopy(empty)
        partial.checks["git_activity"].status = "partial"
        partial.checks["git_activity"].availability = DataAvailability.PARTIAL
        ScoringEngine(MVPPolicy()).apply(partial)
        self.assertIsNone(partial.category_scores["activity"]["score"])
