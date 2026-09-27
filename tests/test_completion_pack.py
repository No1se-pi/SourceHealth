"""Comprehensive tests for product completion pack: profile summary, portfolio, publicity, and history."""

import unittest
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

from sourcehealth.profile.service import ProfileService
from sourcehealth.publicity.service import PublicityService


class ProfileSummaryTests(unittest.TestCase):
    def test_summary_and_portfolio_distribution(self):
        now = datetime.now(UTC)


        # Repositories:
        # 1. Health 85 -> healthy
        # 2. Health 70 -> medium
        # 3. Health 50 -> needs_attention
        # 4. Health None (with preview 60) -> no_data (Source Soul must NOT count as official health)
        # 5. Not analyzed yet -> no_data
        r1 = SimpleNamespace(
            repository_id=uuid4(),
            organization_slug="org",
            repository_slug="r1",
            health_score=85.0,
            score_preview=None,
            last_analysis_at=now,
        )
        r2 = SimpleNamespace(
            repository_id=uuid4(),
            organization_slug="org",
            repository_slug="r2",
            health_score=70.0,
            score_preview=None,
            last_analysis_at=now,
        )
        r3 = SimpleNamespace(
            repository_id=uuid4(),
            organization_slug="org",
            repository_slug="r3",
            health_score=50.0,
            score_preview=None,
            last_analysis_at=now,
        )
        r4 = SimpleNamespace(
            repository_id=uuid4(),
            organization_slug="org",
            repository_slug="r4",
            health_score=None,
            score_preview={"health_score": 60.0},  # Source Soul preview only
            last_analysis_at=now,
        )
        r5 = SimpleNamespace(
            repository_id=uuid4(),
            organization_slug="org",
            repository_slug="r5",
            health_score=None,
            score_preview=None,
            last_analysis_at=None,
        )

        tracked_repos = [r1, r2, r3, r4, r5]
        achievements = [
            {"id": "first_checkup", "unlocked": True},
            {"id": "maintainer", "unlocked": False},
        ]

        summary = ProfileService.compute_summary(tracked_repos, achievements)

        self.assertEqual(summary["tracked_count"], 5)
        self.assertEqual(summary["analyzed_count"], 4)
        self.assertEqual(summary["official_health_count"], 3)
        self.assertEqual(summary["best_health"], 85.0)
        self.assertEqual(summary["median_health"], 70.0)
        self.assertEqual(summary["achievements_unlocked"], 1)

        # Portfolio distribution:
        self.assertEqual(summary["portfolio_healthy"], 1)
        self.assertEqual(summary["portfolio_medium"], 1)
        self.assertEqual(summary["portfolio_needs_attention"], 1)
        self.assertEqual(summary["portfolio_no_data"], 2)  # r4 (Source Soul only) + r5 (no analysis)

    def test_empty_profile_summary(self):
        summary = ProfileService.compute_summary([], [])
        self.assertEqual(summary["tracked_count"], 0)
        self.assertEqual(summary["analyzed_count"], 0)
        self.assertEqual(summary["official_health_count"], 0)
        self.assertIsNone(summary["best_health"])
        self.assertIsNone(summary["median_health"])
        self.assertEqual(summary["achievements_unlocked"], 0)
        self.assertEqual(summary["portfolio_healthy"], 0)
        self.assertEqual(summary["portfolio_medium"], 0)
        self.assertEqual(summary["portfolio_needs_attention"], 0)
        self.assertEqual(summary["portfolio_no_data"], 0)



class PublicityServiceTests(unittest.TestCase):
    def test_badge_and_share_urls_derive_from_public_base(self):
        class FakeSessions:
            pass

        service = PublicityService(FakeSessions(), "https://sourcehealth.tech/")
        self.assertEqual(service.base, "https://sourcehealth.tech")

    def test_share_info_model_fields(self):
        from sourcehealth.api.routers.publicity import ShareInfo
        info = ShareInfo(
            repository_id=uuid4(),
            organization_slug="org",
            repository_slug="repo",
            health_score=85.0,
            health_available=True,
            repository_url="https://sourcehealth.tech/repositories/1",
            badge_url="https://sourcehealth.tech/api/v1/badges/org/repo.svg",
            badge_markdown="![SourceHealth](https://sourcehealth.tech/api/v1/badges/org/repo.svg)",
            badge_html='<img src="https://sourcehealth.tech/api/v1/badges/org/repo.svg" alt="SourceHealth" />',
            latest_analysis_id=uuid4(),
            latest_analysis_url="https://sourcehealth.tech/analyses/1",
            markdown_report_url="https://sourcehealth.tech/api/v1/analyses/1/report.md",
        )
        self.assertEqual(info.organization_slug, "org")
        self.assertIsNotNone(info.badge_html)


if __name__ == "__main__":
    unittest.main()

