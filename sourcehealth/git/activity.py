"""Time and commit-activity metrics for structured Git history."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from statistics import mean, median
from typing import Any, Iterable

from sourcehealth.git.models import Commit


_SECONDS_PER_DAY = 86_400


@dataclass(frozen=True)
class GitActivityMetrics:
    """JSON-friendly temporal metrics.

    Duration and gap fields are expressed in days. Date fields are ISO 8601
    strings normalized to UTC. Gap fields are ``None`` when fewer than two
    commits are available.
    """

    total_commits: int
    first_commit_date: str | None
    last_commit_date: str | None
    repository_age: float | None
    days_since_last_commit: float | None
    min_commit_gap: float | None
    max_commit_gap: float | None
    mean_commit_gap: float | None
    median_commit_gap: float | None
    commits_last_7_days: int
    commits_last_30_days: int
    commits_last_90_days: int
    commits_last_180_days: int
    commits_last_365_days: int
    unique_active_days: int
    active_days_last_30_days: int
    active_days_last_90_days: int
    active_days_last_365_days: int
    active_months_last_12_months: int
    average_commits_per_active_day: float
    average_commits_per_month: float
    longest_inactivity_period: float | None

    def to_dict(self) -> dict[str, Any]:
        """Return a dictionary ready for ``json.dumps``."""

        return asdict(self)


class GitActivityAnalyzer:
    """Calculate only time-related metrics from already collected commits."""

    _WINDOWS = (7, 30, 90, 180, 365)

    def analyze(
        self,
        commits: Iterable[Commit],
        *,
        now: datetime | None = None,
    ) -> GitActivityMetrics:
        """Calculate activity metrics without accessing Git or the filesystem."""

        current_time = now or datetime.now(UTC)
        self._require_aware(current_time, "now")
        current_time = current_time.astimezone(UTC)

        commit_times = []
        for commit in commits:
            self._require_aware(commit.datetime, "commit datetime")
            commit_times.append(commit.datetime.astimezone(UTC))
        commit_times.sort()

        if not commit_times:
            return self._empty_metrics()

        first = commit_times[0]
        last = commit_times[-1]
        gaps = [
            self._days(later - earlier)
            for earlier, later in zip(commit_times, commit_times[1:])
        ]
        commit_counts = {
            days: self._commits_in_window(commit_times, current_time, days)
            for days in self._WINDOWS
        }
        active_days = {
            days: self._active_days_in_window(commit_times, current_time, days)
            for days in (30, 90, 365)
        }
        unique_days = {commit_time.date() for commit_time in commit_times}
        lifetime_months = self._months_inclusive(first, last)

        return GitActivityMetrics(
            total_commits=len(commit_times),
            first_commit_date=first.isoformat(),
            last_commit_date=last.isoformat(),
            repository_age=self._days(last - first),
            days_since_last_commit=self._days(current_time - last),
            min_commit_gap=min(gaps) if gaps else None,
            max_commit_gap=max(gaps) if gaps else None,
            mean_commit_gap=mean(gaps) if gaps else None,
            median_commit_gap=median(gaps) if gaps else None,
            commits_last_7_days=commit_counts[7],
            commits_last_30_days=commit_counts[30],
            commits_last_90_days=commit_counts[90],
            commits_last_180_days=commit_counts[180],
            commits_last_365_days=commit_counts[365],
            unique_active_days=len(unique_days),
            active_days_last_30_days=active_days[30],
            active_days_last_90_days=active_days[90],
            active_days_last_365_days=active_days[365],
            active_months_last_12_months=self._active_months_last_12_months(
                commit_times, current_time
            ),
            average_commits_per_active_day=len(commit_times) / len(unique_days),
            average_commits_per_month=len(commit_times) / lifetime_months,
            longest_inactivity_period=max(gaps) if gaps else None,
        )

    @staticmethod
    def _empty_metrics() -> GitActivityMetrics:
        return GitActivityMetrics(
            total_commits=0,
            first_commit_date=None,
            last_commit_date=None,
            repository_age=None,
            days_since_last_commit=None,
            min_commit_gap=None,
            max_commit_gap=None,
            mean_commit_gap=None,
            median_commit_gap=None,
            commits_last_7_days=0,
            commits_last_30_days=0,
            commits_last_90_days=0,
            commits_last_180_days=0,
            commits_last_365_days=0,
            unique_active_days=0,
            active_days_last_30_days=0,
            active_days_last_90_days=0,
            active_days_last_365_days=0,
            active_months_last_12_months=0,
            average_commits_per_active_day=0.0,
            average_commits_per_month=0.0,
            longest_inactivity_period=None,
        )

    @staticmethod
    def _require_aware(value: datetime, name: str) -> None:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError(f"{name} must be timezone-aware")

    @staticmethod
    def _days(value: timedelta) -> float:
        return value.total_seconds() / _SECONDS_PER_DAY

    @classmethod
    def _commits_in_window(
        cls, commit_times: list[datetime], now: datetime, days: int
    ) -> int:
        start = now - timedelta(days=days)
        return sum(start <= commit_time <= now for commit_time in commit_times)

    @classmethod
    def _active_days_in_window(
        cls, commit_times: list[datetime], now: datetime, days: int
    ) -> int:
        start = now - timedelta(days=days)
        return len(
            {
                commit_time.date()
                for commit_time in commit_times
                if start <= commit_time <= now
            }
        )

    @staticmethod
    def _active_months_last_12_months(
        commit_times: list[datetime], now: datetime
    ) -> int:
        current_month = now.year * 12 + now.month - 1
        first_included_month = current_month - 11
        return len(
            {
                commit_time.year * 12 + commit_time.month - 1
                for commit_time in commit_times
                if first_included_month
                <= commit_time.year * 12 + commit_time.month - 1
                <= current_month
                and commit_time <= now
            }
        )

    @staticmethod
    def _months_inclusive(first: datetime, last: datetime) -> int:
        return (last.year - first.year) * 12 + last.month - first.month + 1
