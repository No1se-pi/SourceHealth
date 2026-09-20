"""Настоящий локальный Git snapshot; target scripts никогда не запускаются."""

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from sourcehealth.analyzers.snapshot import DocumentationAnalyzer, TechnicalDebtAnalyzer
from sourcehealth.core import AnalysisContext
from sourcehealth.reporting import analyze_repository, to_legacy_report
from sourcehealth.runtime_results import normalize_runtime_report
from sourcehealth.sast import SASTScanner
from sourcehealth.snapshot import SnapshotCollector
from tests.mvp_fixtures import NOW


class SnapshotTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.git("init", "-q")

    def git(self, *args):
        return subprocess.run(["git", "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                               "-c", "commit.gpgsign=false", "-c", "core.hooksPath=/dev/null", "-C", str(self.root), *args],
                              check=True, capture_output=True,
                              env={**os.environ, "GIT_AUTHOR_DATE": "2026-08-01T00:00:00Z", "GIT_COMMITTER_DATE": "2026-08-01T00:00:00Z"})

    def files(self, values):
        for name, text in values.items():
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        self.git("add", ".")
        self.git("commit", "-qm", "fixture")

    def analyze(self, **kwargs):
        facts = SnapshotCollector(**kwargs).collect(self.root, NOW)
        context = AnalysisContext(self.root, started_at=NOW, metadata={"snapshot": facts})
        return DocumentationAnalyzer().analyze(context), TechnicalDebtAnalyzer().analyze(context)

    def test_healthy_docs_clean_debt_and_exact_snapshot(self):
        self.files({"README.md": "# Example\n## Quick Start\nnpm run dev\n## Build\nnpm run build\n## Tests\nnpm test\n",
                    "LICENSE": "license", "CONTRIBUTING.md": "contribute", ".github/CODEOWNERS": "owner",
                    "docs/guide.md": "guide", ".sourcecraft/ci.yaml": "untrusted script: never execute", "main.py": "x = 1\n"})
        docs, debt = self.analyze()
        for key in ("readme", "license", "contributing", "codeowners", "docs_directory", "run_instructions", "build_instructions", "test_instructions"):
            self.assertTrue(docs.metrics[key], key)
        self.assertEqual(docs.metadata["head_sha"], self.git("rev-parse", "HEAD").stdout.decode().strip())
        self.assertTrue(docs.metadata["ci_configured"])
        self.assertEqual(debt.metrics["todo_count"], 0)
        self.assertEqual(debt.metrics["marker_density"], 0)

    def test_minimal_and_missing_documentation(self):
        self.files({"main.py": "x = 1\n"})
        docs, _ = self.analyze()
        self.assertFalse(docs.metrics["readme"])
        self.assertFalse(docs.metrics["run_instructions"])
        self.files({"README.md": "# Project\nDescription only"})
        docs, _ = self.analyze()
        self.assertTrue(docs.metrics["readme"])
        self.assertFalse(docs.metrics["run_instructions"])

    def test_debt_counts_age_and_size_without_executing_repository(self):
        self.files({"main.py": "# TODO refactor\n# FIXME bug\n" + "x = 1\n" * 1001,
                    "setup.py": "raise RuntimeError('must never execute')\n"})
        _, debt = self.analyze()
        self.assertEqual(debt.metrics["todo_count"], 1)
        self.assertEqual(debt.metrics["fixme_count"], 1)
        self.assertEqual(debt.metrics["files_with_debt"], 1)
        self.assertEqual(debt.metrics["large_files"], 1)
        self.assertEqual(debt.metrics["oldest_marker_age_days"], 49)
        self.assertEqual(debt.metrics["marker_density"], 1)
        _, limited = self.analyze(age_files=0)
        self.assertIsNone(limited.metrics["oldest_marker_age_days"])
        self.assertFalse(limited.metrics["age_complete"])

    def test_partial_snapshot_does_not_claim_missing_docs_or_zero_density(self):
        self.files({"a.py": "x=1", "README.md": "# Quick Start"})
        docs, debt = self.analyze(max_files=0)
        self.assertEqual(docs.availability, "partial")
        self.assertIsNone(docs.metrics["readme"])
        self.assertIsNone(debt.metrics["marker_density"])

    def test_real_scanner_legacy_extension_roundtrip(self):
        self.files({"README.md": "# Quick Start\npython -m example\n", "main.py": "# TODO refactor\nx=1\n"})
        baseline = to_legacy_report(analyze_repository(self.root, SASTScanner()))
        self.assertEqual(set(baseline["checks"]), {"git_activity", "sast"})
        payload = to_legacy_report(analyze_repository(self.root, SASTScanner(), with_mvp=True))
        results = normalize_runtime_report(payload, with_mvp=True)
        self.assertEqual(set(results), {"git_activity", "sast", "documentation", "technical_debt"})
        self.assertTrue(all(r.status == "ok" for r in results.values()))
        self.assertEqual(results["technical_debt"].metrics["todo_count"], 1)
        self.assertNotIn(str(self.root), str({k: v.to_dict() for k, v in results.items()}))

    def test_code_read_failure_does_not_invalidate_documentation(self):
        self.files({"README.md": "# Quick Start\npython -m app\n", "main.py": "x=1\n"})
        for content, limits in ((b"\xff", {}), (b"x" * 200, {"max_file_bytes": 100})):
            with self.subTest(limits=limits):
                (self.root / "main.py").write_bytes(content)
                self.git("add", ".")
                self.git("commit", "-qm", "code fixture")
                docs, debt = self.analyze(**limits)
                self.assertEqual(docs.status, "ok")
                self.assertTrue(docs.metrics["run_instructions"])
                self.assertEqual(debt.status, "partial")
                self.assertIsNone(debt.metrics["marker_density"])
        (self.root / "main.py").write_bytes(b"\xff")
        self.git("add", ".")
        self.git("commit", "-qm", "invalid encoding")
        payload = to_legacy_report(analyze_repository(self.root, SASTScanner(), with_mvp=True))
        normalized = normalize_runtime_report(payload, with_mvp=True)
        self.assertEqual(normalized["documentation"].status, "ok")
        self.assertEqual(normalized["technical_debt"].status, "partial")

    def test_documentation_read_failure_does_not_invalidate_debt(self):
        self.files({"README.md": "# Project", "main.py": "x=1\n"})
        (self.root / "README.md").write_bytes(b"\xff")
        self.git("add", ".")
        self.git("commit", "-qm", "invalid documentation")
        docs, debt = self.analyze()
        self.assertEqual(docs.status, "partial")
        self.assertEqual(debt.status, "ok")
        self.assertEqual(debt.metrics["marker_density"], 0)

    def test_code_byte_budget_exhaustion_preserves_later_documentation(self):
        # Git lists A/B before README: the first code file consumes most of its budget.
        self.files({"A.py": "x=1\n" * 8, "B.py": "x=2\n" * 8,
                    "README.md": "# Quick Start\npython -m app\n"})
        docs, debt = self.analyze(max_bytes=40)
        self.assertEqual(docs.status, "ok")
        self.assertTrue(docs.metrics["run_instructions"])
        self.assertEqual(debt.status, "partial")
        self.assertIsNone(debt.metrics["marker_density"])
        facts = SnapshotCollector(max_bytes=40).collect(self.root, NOW)
        self.assertEqual(facts["debt_bytes"], (self.root / "A.py").stat().st_size)
        self.assertEqual(facts["documentation_bytes"], (self.root / "README.md").stat().st_size)
        self.assertEqual(facts["bytes_read"], facts["documentation_bytes"] + facts["debt_bytes"])

    def test_documentation_byte_budget_exhaustion_preserves_later_code(self):
        self.files({"README.md": "# Project\n" * 3, "docs/guide.md": "# Guide\n" * 3,
                    "main.py": "x=1\n" * 8})
        docs, debt = self.analyze(max_bytes=40)
        self.assertEqual(docs.status, "partial")
        self.assertEqual(debt.status, "ok")
        self.assertEqual(debt.metrics["code_files"], 1)
        self.assertEqual(debt.metrics["marker_density"], 0)

    def test_symlink_does_not_read_outside_snapshot(self):
        self.files({"main.py": "x=1\n", "README.md": "safe"})
        (self.root / "README.md").unlink()
        with tempfile.TemporaryDirectory() as other:
            outside = Path(other) / "outside.txt"
            outside.write_text("npm run dev", encoding="utf-8")
            try:
                (self.root / "README.md").symlink_to(outside)
            except OSError:
                self.skipTest("symlink privilege unavailable")
            docs, _ = self.analyze()
            self.assertEqual(docs.availability, "partial")
            self.assertIsNone(docs.metrics["run_instructions"])
