"""Compatibility entry point for the original activity prototype."""

from datetime import datetime
from typing import Iterable

from sourcehealth.git import Commit, GitActivityAnalyzer, GitActivityMetrics


def commit_periodicity(
    commits: Iterable[Commit], *, now: datetime | None = None
) -> GitActivityMetrics:
    """Calculate temporal metrics from collector output."""

    return GitActivityAnalyzer().analyze(commits, now=now)
