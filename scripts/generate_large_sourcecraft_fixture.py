"""Детерминированный Git fixture вне SourceHealth; публикация — отдельный ручной шаг.

python scripts/generate_large_sourcecraft_fixture.py /tmp/sourcehealth-large-fixture
Ничего не запускает из fixture и не обращается к сети.
"""

import argparse
import hashlib
import json
import os
import subprocess
from pathlib import Path

SEED = "sourcehealth-large-v1"
SOURCE_ROOT = Path(__file__).resolve().parents[1]
FIXED_DATE = "2026-09-01T00:00:00+00:00"


def fixture_files():
    """Небольшой неизменный code/docs набор; масштаб добавляет только neutral text."""
    files = {
        "README.md": "# SourceHealth large acceptance fixture\n\n"
        "Synthetic fixture; not a production application. Do not execute planted controls.\n"
        "## Quick Start\nRead docs/run.md; static inspection only.\n"
        "## Build\nNo build required; see docs/build.md.\n"
        "## Test\nSee docs/test.md for static acceptance checks.\n",
        "LICENSE": "MIT License\n\nCopyright (c) 2026 SourceHealth fixture contributors\n\n"
        "Permission is hereby granted, free of charge, to any person obtaining a copy\n"
        "of this software and associated documentation files (the Software), to deal\n"
        "in the Software without restriction, including without limitation the rights\n"
        "to use, copy, modify, merge, publish, distribute, sublicense, and/or sell\n"
        "copies of the Software, and to permit persons to whom the Software is\n"
        "furnished to do so, subject to the following conditions:\n\n"
        "The above copyright notice and this permission notice shall be included in all\n"
        "copies or substantial portions of the Software.\n\n"
        "THE SOFTWARE IS PROVIDED AS IS, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR\n"
        "IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,\n"
        "FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE\n"
        "AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER\n"
        "LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,\n"
        "OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.\n",
        "CONTRIBUTING.md": "# Contributing\nRegenerate with the trusted SourceHealth generator.\n",
        "CODEOWNERS": "# Fixture: no real account is assigned.\n",
        "docs/run.md": "# Run\nStatic analysis only. Never execute the planted controls.\n",
        "docs/build.md": "# Build\nNo dependencies or build commands are required.\n",
        "docs/test.md": "# Test\nCount tracked files and inspect safe analyzer aggregates.\n",
        "docs/controls.md": "# Controls\nTwo eval calls, two TODO/FIXME markers. No credentials.\n",
        "tests/README.md": "# Acceptance\nSourceHealth owns the tests; target code is not executed.\n",
    }
    for index in range(100):
        lines = [f'"""Static fixture module {index:03d}."""', ""]
        for number in range(8):
            lines += [f"def scale_{number}(value):", f"    return value * {number + 1}", ""]
        if index < 2:
            lines += ["# TODO: replace static acceptance control" if index == 0 else
                      "# FIXME: replace static acceptance control",
                      "def planted_control(expression):", "    return eval(expression)", ""]
        files[f"src/module_{index:03d}.py"] = "\n".join(lines)
    return files


def generate(destination, file_count):
    destination = Path(destination).resolve()
    if destination == SOURCE_ROOT or SOURCE_ROOT in destination.parents:
        raise ValueError("destination_must_be_outside_sourcehealth")
    if destination.exists():
        raise ValueError("destination_must_not_exist")
    files = fixture_files()
    if file_count < len(files):
        raise ValueError("file_count_too_small")
    destination.mkdir(parents=True)
    for index in range(file_count - len(files)):
        digest = hashlib.sha256(f"{SEED}:{index}".encode()).hexdigest()
        files[f"data/generated/batch_{index // 500:03d}/record_{index:05d}.txt"] = f"record {index:05d}\n{digest}\n"
    for name, content in files.items():
        path = destination / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="\n")
    # Ignore caller Git configuration, hooks, signing and environment overrides.
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull,
               GIT_AUTHOR_DATE=FIXED_DATE, GIT_COMMITTER_DATE=FIXED_DATE)

    def git(*args):
        return subprocess.run(["git", "-c", "core.hooksPath=" + os.devnull,
                               "-c", "commit.gpgsign=false", "-c", "core.autocrlf=false",
                               "-c", "user.name=SourceHealth Fixture", "-c", "user.email=fixture@example.invalid",
                               "-C", str(destination), *args], env=env, check=True, capture_output=True).stdout

    git("init", "--quiet", "--initial-branch=main", "--object-format=sha1", "--template=")
    git("add", "--all")
    git("commit", "--quiet", "-m", "Deterministic large acceptance fixture v1")
    tracked = git("ls-files", "-z").split(b"\0")[:-1]
    if len(tracked) != file_count:
        raise ValueError("tracked_count_mismatch")
    return {"fixture_version": SEED, "tracked_files": len(tracked),
            "commits": int(git("rev-list", "--count", "HEAD")),
            "working_copy_bytes": sum((destination / p.decode()).stat().st_size for p in tracked),
            "size_definition": "tracked file bytes, excluding .git",
            "head_sha": git("rev-parse", "HEAD").decode().strip(),
            "large_threshold_met": len(tracked) >= 10_000,
            "sourcecraft_acceptance": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--files", type=int, default=10_000)
    args = parser.parse_args()
    if not 10_000 <= args.files <= 100_000:
        parser.error("files must be between 10000 and 100000")
    try:
        print(json.dumps(generate(args.destination, args.files), sort_keys=True))
    except (ValueError, OSError, subprocess.SubprocessError):
        # Exception strings can contain private paths/configuration; never print them.
        parser.exit(2, "Fixture generation failed; use a new destination outside SourceHealth.\n")


if __name__ == "__main__":
    main()
