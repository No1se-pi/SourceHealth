"""Collect structured commit history from a local Git repository."""

from __future__ import annotations

import subprocess
from datetime import datetime
from pathlib import Path

from sourcehealth.git.models import Commit


class GitCollectionError(RuntimeError):
    """Raised when commit history cannot be collected from Git."""


class GitCollector:
    """Read and normalize Git history without calculating any metrics."""

    _FIELD_SEPARATOR = "\x00"
    _FIELDS_PER_COMMIT = 5
    _LOG_FORMAT = "%H%x00%an%x00%ae%x00%aI%x00%B"

    def __init__(self, git_executable: str = "git") -> None:
        self._git_executable = git_executable

    def collect(self, repo_path: str | Path) -> list[Commit]:
        """Return commits reachable from the repository's current ``HEAD``.

        Git produces NUL-delimited fields, so multiline messages and localized
        human-readable labels cannot break parsing. An initialized repository
        without commits returns an empty list.
        """

        path = Path(repo_path).expanduser()
        if not path.is_dir():
            raise GitCollectionError(f"Repository path is not a directory: {path}")

        self._ensure_repository(path)
        if not self._has_head(path):
            return []

        result = self._run_git(
            path,
            "-c",
            "i18n.logOutputEncoding=UTF-8",
            "log",
            "-z",
            "--no-show-signature",
            f"--format={self._LOG_FORMAT}",
        )
        if result.returncode != 0:
            detail = result.stderr.strip() or "unknown Git error"
            raise GitCollectionError(f"Unable to read Git history: {detail}")

        return self._parse_log(result.stdout)

    def _ensure_repository(self, path: Path) -> None:
        result = self._run_git(path, "rev-parse", "--git-dir")
        if result.returncode != 0:
            detail = result.stderr.strip() or "not a Git repository"
            raise GitCollectionError(f"Unable to use repository at {path}: {detail}")

    def _has_head(self, path: Path) -> bool:
        result = self._run_git(path, "rev-parse", "--verify", "HEAD")
        return result.returncode == 0

    def _run_git(self, path: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
        try:
            return subprocess.run(
                [self._git_executable, *arguments],
                cwd=path,
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
        except FileNotFoundError as error:
            raise GitCollectionError(
                f"Git executable was not found: {self._git_executable}"
            ) from error
        except OSError as error:
            raise GitCollectionError(f"Unable to start Git: {error}") from error

    @classmethod
    def _parse_log(cls, output: str) -> list[Commit]:
        if not output:
            return []

        fields = output.split(cls._FIELD_SEPARATOR)
        if fields[-1] == "":
            fields.pop()
        if len(fields) % cls._FIELDS_PER_COMMIT != 0:
            raise GitCollectionError("Git returned an unexpected log format")

        commits: list[Commit] = []
        for index in range(0, len(fields), cls._FIELDS_PER_COMMIT):
            commit_hash, author_name, author_email, raw_datetime, message = fields[
                index : index + cls._FIELDS_PER_COMMIT
            ]
            try:
                commit_datetime = datetime.fromisoformat(raw_datetime)
            except ValueError as error:
                raise GitCollectionError(
                    f"Git returned an invalid commit datetime: {raw_datetime!r}"
                ) from error

            commits.append(
                Commit(
                    hash=commit_hash,
                    author_name=author_name,
                    author_email=author_email,
                    datetime=commit_datetime,
                    message=message.rstrip("\n"),
                )
            )

        return commits
