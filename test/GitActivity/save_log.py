"""Compatibility entry point for the original Git collection prototype."""

from pathlib import Path

from sourcehealth.git import Commit, GitCollector


def collect_commits(path: str | Path) -> list[Commit]:
    """Collect structured commits directly in memory."""

    return GitCollector().collect(path)
