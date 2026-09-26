"""Ограниченный сбор snapshot-фактов: Git/read-only файлы, без выполнения target code."""

import os
import re
import stat
import subprocess
import time
from datetime import datetime
from pathlib import Path

CODE_SUFFIXES = frozenset({".py", ".js", ".jsx", ".ts", ".tsx", ".java", ".go", ".rs", ".c", ".h",
                            ".cpp", ".hpp", ".cs", ".php", ".rb", ".swift", ".kt", ".scala", ".sh", ".sql"})
EXCLUDED = frozenset({".git", "node_modules", "vendor", ".venv", "venv", "dist", "build", "__pycache__"})
MARKER = re.compile(r"\b(TODO|FIXME)\b")


def git(root, *args, timeout=10):
    """Только доверенные Git subcommands; stderr и сообщения исходников не возвращаются."""
    output = subprocess.run(["git", "-c", "core.fsmonitor=false", "-c", "core.hooksPath=/dev/null",
                             "-c", "core.pager=", "-C", str(root), *args],
                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=timeout, check=True,
                            env={**os.environ, "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull,
                                 "GIT_TERMINAL_PROMPT": "0"}).stdout
    if len(output) > 8 * 1024 * 1024:
        raise ValueError("git_output_limit")
    return output


class SnapshotCollector:
    """Один обход для documentation/debt; bounded blame только для файлов с маркерами."""

    def __init__(self, *, max_files=10000, max_bytes=64 * 1024 * 1024, max_file_bytes=1024 * 1024,
                 timeout=30, age_files=10):
        self.max_files, self.max_bytes, self.max_file_bytes = max_files, max_bytes, max_file_bytes
        self.timeout, self.age_files = timeout, age_files

    def collect(self, root: Path, now: datetime):
        started = time.monotonic()
        root = root.resolve()
        sha = git(root, "rev-parse", "HEAD").decode("ascii").strip()
        if not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", sha):
            raise ValueError("invalid_snapshot")
        paths = git(root, "ls-tree", "-r", "--name-only", "-z", sha).decode("utf-8").split("\0")
        paths = [p for p in paths if p and not EXCLUDED.intersection(Path(p).parts)]
        complete = len(paths) <= self.max_files
        documentation_complete = debt_complete = ci_complete = complete
        docs = {"readme": False, "license": False, "contributing": False, "codeowners": False,
                "docs_directory": False, "run_instructions": False, "build_instructions": False,
                "test_instructions": False, "readme_bytes": 0, "readme_headings": 0}
        locations = {}
        debt = {"todo_count": 0, "fixme_count": 0, "files_with_debt": 0, "code_files": 0,
                "large_files": 0, "oldest_marker_age_days": None, "age_complete": True}
        ci_configured = False
        age_targets = []
        # Each analysis owns its byte budget; code cannot consume documentation's allowance.
        documentation_bytes = debt_bytes = 0
        for relative in paths[:self.max_files]:
            if time.monotonic() - started > self.timeout:
                documentation_complete = debt_complete = ci_complete = False
                break
            path = Path(relative)
            if path.is_absolute() or ".." in path.parts or "\\" in relative or ":" in relative or any(ord(c) < 32 for c in relative):
                documentation_complete = debt_complete = ci_complete = False
                continue
            target = root / path
            lower, name = relative.lower(), path.name.lower()
            is_code = path.suffix.lower() in CODE_SUFFIXES
            doc_relevant = (path.parts[0].lower() == "docs" or
                            name == "codeowners" or
                            len(path.parts) == 1 and bool(re.fullmatch(
                                r"(?:readme|license|licence|copying|contributing)(?:\.[a-z]+)?", name)))
            try:
                # Check every component: a parent symlink must not escape a local workspace.
                if any(p.is_symlink() or p.is_junction() if hasattr(p, "is_junction") else p.is_symlink()
                       for p in [target, *list(target.parents)[:len(path.parts) - 1]]):
                    raise ValueError("unsafe_path")
                info = target.lstat()
                if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                    raise ValueError("unsafe_file")
                lower = relative.lower()
                name = path.name.lower()
                kind = None
                if len(path.parts) == 1:
                    if re.fullmatch(r"readme(?:\.(?:md|rst|txt))?", name):
                        kind = "readme"
                    elif re.fullmatch(r"(?:license|licence|copying)(?:\.[a-z]+)?", name):
                        kind = "license"
                    elif re.fullmatch(r"contributing(?:\.(?:md|rst|txt))?", name):
                        kind = "contributing"
                if lower in {"codeowners", ".github/codeowners", ".sourcecraft/codeowners", "docs/codeowners"}:
                    kind = "codeowners"
                if path.parts[0].lower() == "docs":
                    docs["docs_directory"] = True
                    locations.setdefault("docs_directory", relative)
                if lower == ".sourcecraft/ci.yaml":
                    ci_configured = True
                if kind:
                    docs[kind] = True
                    locations[kind] = relative
                is_code = path.suffix.lower() in CODE_SUFFIXES
                is_doc = kind == "readme" or (path.suffix.lower() in {".md", ".rst", ".txt"} and path.parts[0].lower() == "docs")
                if not is_code and not is_doc:
                    continue
                used_bytes = documentation_bytes if is_doc else debt_bytes
                if info.st_size > self.max_file_bytes or used_bytes + info.st_size > self.max_bytes:
                    if is_doc:
                        documentation_complete = False
                    if is_code:
                        debt_complete = False
                    continue
                flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0)
                with os.fdopen(os.open(target, flags), "rb") as stream:
                    opened = os.fstat(stream.fileno())
                    if (opened.st_ino, opened.st_dev, opened.st_size) != (info.st_ino, info.st_dev, info.st_size):
                        raise ValueError("file_changed")
                    content = stream.read(self.max_file_bytes + 1)
                if len(content) > self.max_file_bytes:
                    raise ValueError("file_limit")
                if is_doc:
                    documentation_bytes += len(content)
                else:
                    debt_bytes += len(content)
                text = content.decode("utf-8")
                if is_doc:
                    if kind == "readme":
                        docs["readme_bytes"] = len(content)
                        docs["readme_headings"] = len(re.findall(r"(?m)^#{1,6}\s+\S", text))
                    for key, pattern in {
                        "run_instructions": r"(?im)(?:^#{1,6}\s+.*(?:quick\s*start|getting started|быстрый\s*старт|запуск)|\b(?:npm run dev|npm start|docker compose up|uvicorn|python -m)\b)",
                        "build_instructions": r"(?im)(?:^#{1,6}\s+.*(?:build|сборк)|\b(?:npm run build|docker build|cargo build|go build)\b)",
                        "test_instructions": r"(?im)(?:^#{1,6}\s+.*(?:test|тест)|\b(?:pytest|unittest|npm test|go test|cargo test)\b)",
                    }.items():
                        if re.search(pattern, text):
                            docs[key] = True
                            locations.setdefault(key, relative)
                if is_code:
                    debt["code_files"] += 1
                    lines = text.splitlines()
                    debt["large_files"] += len(lines) > 1000
                    markers = [(n, MARKER.findall(line)) for n, line in enumerate(lines, 1) if MARKER.search(line)]
                    if markers:
                        debt["files_with_debt"] += 1
                        debt["todo_count"] += sum(values.count("TODO") for _, values in markers)
                        debt["fixme_count"] += sum(values.count("FIXME") for _, values in markers)
                        age_targets.append((relative, {n for n, _ in markers}))
            except (OSError, ValueError, UnicodeError):
                if doc_relevant:
                    documentation_complete = False
                if is_code:
                    debt_complete = False
                if lower == ".sourcecraft/ci.yaml":
                    ci_complete = False
        ages = []
        debt["age_complete"] = debt_complete and len(age_targets) <= self.age_files
        for relative, numbers in age_targets[:self.age_files]:
            try:
                remaining = self.timeout - (time.monotonic() - started)
                if remaining <= 0:
                    raise ValueError("age_budget")
                output = git(root, "blame", "--line-porcelain", "--no-textconv", sha, "--", relative,
                             timeout=min(5, remaining)).decode("utf-8")
                current, author_time, covered = None, None, set()
                for line in output.splitlines():
                    header = re.fullmatch(r"[0-9a-f]{40,64} \d+ (\d+)(?: \d+)?", line)
                    if header:
                        current = int(header[1])
                    elif line.startswith("author-time "):
                        author_time = int(line.split()[1])
                    elif line.startswith("\t") and current in numbers and author_time is not None:
                        ages.append(max(0, (now.timestamp() - author_time) / 86400))
                        covered.add(current)
                if covered != numbers:
                    debt["age_complete"] = False
            except (OSError, ValueError, subprocess.SubprocessError, UnicodeError):
                debt["age_complete"] = False
        if ages and debt["age_complete"]:
            debt["oldest_marker_age_days"] = max(ages)
        debt["marker_density"] = ((debt["todo_count"] + debt["fixme_count"]) / debt["code_files"]
                                   if debt_complete and debt["code_files"] else (0 if debt_complete else None))
        if not documentation_complete:
            for key in docs:
                if docs[key] is False:
                    docs[key] = None
        return {"head_sha": sha, "complete": documentation_complete and debt_complete and ci_complete,
                "documentation_complete": documentation_complete, "debt_complete": debt_complete,
                "documentation": docs, "locations": locations,
                "technical_debt": debt, "ci_configured": ci_configured if ci_complete or ci_configured else None,
                "scope": "tracked_default_branch_excluding_generated",
                "documentation_bytes": documentation_bytes, "debt_bytes": debt_bytes,
                "bytes_read": documentation_bytes + debt_bytes}
