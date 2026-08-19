from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from sourcehealth.git import GitCollectionError, GitCollector


class GitCollectorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.collector = GitCollector()

    def test_empty_repository_returns_empty_list(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            self._git(Path(directory), "init")

            self.assertEqual(self.collector.collect(directory), [])

    def test_collects_structured_commit_with_multiline_message(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            self._git(repository, "init")
            self._git(repository, "config", "user.name", "Collector Test")
            self._git(repository, "config", "user.email", "collector@example.com")
            (repository / "sample.txt").write_text("content", encoding="utf-8")
            self._git(repository, "add", "sample.txt")
            environment = os.environ.copy()
            environment["GIT_AUTHOR_DATE"] = "2026-08-18T10:30:00+03:00"
            environment["GIT_COMMITTER_DATE"] = "2026-08-18T10:30:00+03:00"
            self._git(
                repository,
                "commit",
                "-m",
                "Subject",
                "-m",
                "Message body",
                environment=environment,
            )

            commits = self.collector.collect(repository)

            self.assertEqual(len(commits), 1)
            commit = commits[0]
            self.assertEqual(len(commit.hash), 40)
            self.assertEqual(commit.author_name, "Collector Test")
            self.assertEqual(commit.author_email, "collector@example.com")
            self.assertEqual(commit.datetime.isoformat(), "2026-08-18T10:30:00+03:00")
            self.assertEqual(commit.message, "Subject\n\nMessage body")
            self.assertEqual(commit.to_dict()["datetime"], "2026-08-18T10:30:00+03:00")

    def test_invalid_path_and_non_repository_are_reported(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            missing = Path(directory) / "missing"
            with self.assertRaises(GitCollectionError):
                self.collector.collect(missing)

            with self.assertRaises(GitCollectionError):
                self.collector.collect(directory)

    @staticmethod
    def _git(
        repository: Path,
        *arguments: str,
        environment: dict[str, str] | None = None,
    ) -> None:
        subprocess.run(
            ["git", *arguments],
            cwd=repository,
            env=environment,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )


if __name__ == "__main__":
    unittest.main()
