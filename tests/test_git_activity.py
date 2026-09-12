"""Тесты временных метрик ``GitActivityAnalyzer``."""

from __future__ import annotations

import json
import unittest
from datetime import UTC, datetime, timedelta, timezone

from sourcehealth.git import Commit, GitActivityAnalyzer


def make_commit(commit_hash: str, commit_datetime: datetime) -> Commit:
    """Создать минимальный тестовый коммит с заданным временем."""

    return Commit(
        hash=commit_hash,
        author_name="Test Author",
        author_email="author@example.com",
        datetime=commit_datetime,
        message=f"Commit {commit_hash}",
    )


class GitActivityAnalyzerTests(unittest.TestCase):
    """Проверка расчётов активности без обращения к реальному Git."""

    def setUp(self) -> None:
        # Фиксированное `now` делает все временные тесты воспроизводимыми.
        self.analyzer = GitActivityAnalyzer()
        self.now = datetime(2026, 8, 20, 12, tzinfo=UTC)

    def test_empty_commit_list(self) -> None:
        """Пустая история должна давать нулевые счётчики и допустимые None."""

        metrics = self.analyzer.analyze([], now=self.now)

        self.assertEqual(metrics.total_commits, 0)
        self.assertIsNone(metrics.first_commit_date)
        self.assertIsNone(metrics.last_commit_date)
        self.assertIsNone(metrics.repository_age)
        self.assertIsNone(metrics.min_commit_gap)
        self.assertEqual(metrics.commits_last_365_days, 0)
        self.assertEqual(metrics.unique_active_days, 0)
        self.assertEqual(metrics.average_commits_per_active_day, 0.0)

        # Проверяем, что публичный результат сериализуется стандартным JSON.
        json.dumps(metrics.to_dict())

    def test_one_commit(self) -> None:
        """Один коммит не образует интервалов, но участвует в окнах активности."""

        commit = make_commit("one", self.now - timedelta(days=2))
        metrics = self.analyzer.analyze([commit], now=self.now)

        self.assertEqual(metrics.total_commits, 1)
        self.assertEqual(metrics.repository_age, 0.0)
        self.assertEqual(metrics.days_since_last_commit, 2.0)
        self.assertIsNone(metrics.min_commit_gap)
        self.assertIsNone(metrics.longest_inactivity_period)
        self.assertEqual(metrics.commits_last_7_days, 1)
        self.assertEqual(metrics.unique_active_days, 1)
        self.assertEqual(metrics.average_commits_per_month, 1.0)

    def test_two_commits_are_sorted_before_gap_calculation(self) -> None:
        """Порядок входных данных не должен влиять на интервалы между коммитами."""

        older = make_commit("older", self.now - timedelta(days=10))
        newer = make_commit("newer", self.now - timedelta(days=3))

        # Специально передаём коммиты в обратном порядке.
        metrics = self.analyzer.analyze([newer, older], now=self.now)

        self.assertEqual(metrics.first_commit_date, older.datetime.isoformat())
        self.assertEqual(metrics.last_commit_date, newer.datetime.isoformat())
        self.assertEqual(metrics.min_commit_gap, 7.0)
        self.assertEqual(metrics.max_commit_gap, 7.0)
        self.assertEqual(metrics.mean_commit_gap, 7.0)
        self.assertEqual(metrics.median_commit_gap, 7.0)

    def test_multiple_commits_on_one_day(self) -> None:
        """Несколько коммитов за сутки образуют один активный календарный день."""

        day = datetime(2026, 8, 19, tzinfo=UTC)
        commits = [
            make_commit("morning", day + timedelta(hours=8)),
            make_commit("noon", day + timedelta(hours=12)),
            make_commit("evening", day + timedelta(hours=20)),
        ]

        metrics = self.analyzer.analyze(commits, now=self.now)

        self.assertEqual(metrics.total_commits, 3)
        self.assertEqual(metrics.unique_active_days, 1)
        self.assertEqual(metrics.active_days_last_30_days, 1)
        self.assertEqual(metrics.average_commits_per_active_day, 3.0)
        self.assertAlmostEqual(metrics.min_commit_gap, 4 / 24)
        self.assertAlmostEqual(metrics.max_commit_gap, 8 / 24)

    def test_large_commit_gaps(self) -> None:
        """Большие периоды простоя должны корректно попадать в gap-метрики."""

        commits = [
            make_commit("first", self.now - timedelta(days=400)),
            make_commit("second", self.now - timedelta(days=200)),
            make_commit("third", self.now - timedelta(days=10)),
        ]

        metrics = self.analyzer.analyze(commits, now=self.now)

        self.assertEqual(metrics.repository_age, 390.0)
        self.assertEqual(metrics.min_commit_gap, 190.0)
        self.assertEqual(metrics.max_commit_gap, 200.0)
        self.assertEqual(metrics.mean_commit_gap, 195.0)
        self.assertEqual(metrics.median_commit_gap, 195.0)
        self.assertEqual(metrics.longest_inactivity_period, 200.0)
        self.assertEqual(metrics.commits_last_365_days, 2)

    def test_timezone_aware_datetimes_are_compared_as_instants(self) -> None:
        """Разные UTC offset должны сравниваться как абсолютные моменты времени."""

        plus_three = timezone(timedelta(hours=3))
        minus_five = timezone(timedelta(hours=-5))

        # 15:00 UTC+3 == 12:00 UTC.
        same_instant = datetime(2026, 8, 19, 15, tzinfo=plus_three)
        # 08:00 UTC-5 == 13:00 UTC, то есть ровно на час позже.
        one_hour_later = datetime(2026, 8, 19, 8, tzinfo=minus_five)

        metrics = self.analyzer.analyze(
            [
                make_commit("later", one_hour_later),
                make_commit("earlier", same_instant),
            ],
            now=self.now,
        )

        self.assertEqual(metrics.first_commit_date, "2026-08-19T12:00:00+00:00")
        self.assertEqual(metrics.last_commit_date, "2026-08-19T13:00:00+00:00")
        self.assertAlmostEqual(metrics.min_commit_gap, 1 / 24)
        self.assertEqual(metrics.unique_active_days, 1)

    def test_naive_datetime_is_rejected(self) -> None:
        """Коммит без часового пояса должен отклоняться ещё на уровне модели."""

        with self.assertRaisesRegex(ValueError, "timezone-aware"):
            make_commit("naive", datetime(2026, 8, 20, 10))


if __name__ == "__main__":
    unittest.main()
