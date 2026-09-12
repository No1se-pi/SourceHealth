"""Контракт и реальные интеграции pipeline без доступа к сети."""

import contextlib
import io
import json
import subprocess
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import Mock, patch

from sourcehealth.analyzers import GitActivityAnalyzerAdapter, SASTAnalyzerAdapter
from sourcehealth.cli import main
from sourcehealth.core import AnalysisContext, AnalyzerResult
from sourcehealth.git import Commit, GitActivityAnalyzer, GitCollectionError
from sourcehealth.reporting import build_report, to_legacy_report
from sourcehealth.runner import AnalysisRunner
from sourcehealth.sast import SASTScanner, ScanConfig
from sourcehealth.sast.sarif import to_sarif


class StubAnalyzer:
    def __init__(self, name, **kwargs):
        self.name = name
        self.kwargs = kwargs
        self.contexts = []

    def analyze(self, context):
        self.contexts.append(context)
        return AnalyzerResult(self.name, **self.kwargs)


class BrokenAnalyzer:
    name = "broken"

    def analyze(self, context):
        raise RuntimeError("private repository data must not leak")


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)

    def runner(self, analyzers):
        return AnalysisRunner(analyzers, context_factory=AnalysisContext)

    def test_multiple_analyzers_metrics_findings_and_shared_context(self):
        metrics = StubAnalyzer("metrics", metrics={"count": 3})
        findings = StubAnalyzer("findings", findings=[{"message": "review"}])
        with patch("sourcehealth.runner.GitCollector") as collector:
            collector.return_value.collect.return_value = []
            report = AnalysisRunner([metrics, findings]).analyze(self.root)
            collector.return_value.collect.assert_called_once_with(self.root.resolve())
        self.assertIs(metrics.contexts[0], findings.contexts[0])
        self.assertEqual(metrics.contexts[0].commits, ())
        payload = json.loads(json.dumps(report.to_dict(), allow_nan=False))
        self.assertEqual(list(payload["checks"]), ["metrics", "findings"])
        self.assertEqual(payload["checks"]["metrics"]["metrics"], {"count": 3})
        self.assertEqual(payload["checks"]["findings"]["findings"], [{"message": "review"}])
        self.assertEqual(payload["schema_version"], "2.0")
        self.assertTrue(payload["complete"])
        self.assertEqual(payload["status"], "ok")
        self.assertLessEqual(report.started_at, report.completed_at)

    def test_failure_preserves_results_and_runs_next_analyzer(self):
        after = StubAnalyzer("after", metrics={"count": 1})
        report = self.runner([BrokenAnalyzer(), after]).analyze(self.root)
        self.assertFalse(report.complete)
        self.assertEqual(report.status, "partial")
        self.assertEqual(report.checks["broken"].error, "analyzer_failed")
        self.assertEqual(report.checks["after"].metrics, {"count": 1})
        self.assertNotIn("private repository", json.dumps(report.to_dict()))

    def test_partial_and_all_error_status(self):
        for status in ("partial", "error"):
            with self.subTest(status=status):
                report = self.runner([StubAnalyzer("one", status=status)]).analyze(self.root)
                self.assertFalse(report.complete)
                self.assertEqual(report.status, status)

    def test_invalid_result_is_isolated(self):
        invalid = [
            {"metrics": {"value": float("nan")}},
            {"metrics": {"value": Path("not-json")}},
            {"status": "unknown"},
            {"findings": ["not-an-object"]},
        ]
        for kwargs in invalid:
            with self.subTest(kwargs=kwargs):
                report = self.runner([StubAnalyzer("bad", **kwargs), StubAnalyzer("ok")]).analyze(self.root)
                self.assertEqual(report.checks["bad"].status, "error")
                self.assertEqual(report.checks["ok"].status, "ok")
                json.dumps(report.to_dict(), allow_nan=False)

    def test_mismatched_name_and_wrong_type_are_isolated(self):
        for result in (AnalyzerResult("other"), {"metrics": {}}):
            analyzer = Mock(name="analyzer")
            analyzer.name = "expected"
            analyzer.analyze.return_value = result
            report = self.runner([analyzer]).analyze(self.root)
            self.assertEqual(report.checks["expected"].status, "error")

    def test_duplicate_names_are_rejected(self):
        with self.assertRaises(ValueError):
            self.runner([StubAnalyzer("same"), StubAnalyzer("same")])

    def test_interrupt_is_not_swallowed(self):
        analyzer = Mock()
        analyzer.name = "interrupt"
        analyzer.analyze.side_effect = KeyboardInterrupt
        with self.assertRaises(KeyboardInterrupt):
            self.runner([analyzer]).analyze(self.root)

    def test_git_adapter_uses_existing_metrics_and_common_clock(self):
        now = datetime(2026, 1, 10, tzinfo=UTC)
        commit = Commit(hash="abc", author_name="Test", author_email="test@example.invalid",
                        datetime=datetime(2026, 1, 9, tzinfo=UTC), message="test")
        context = AnalysisContext(self.root, commits=(commit,), started_at=now)
        result = GitActivityAnalyzerAdapter().analyze(context)
        self.assertEqual(result.metrics, GitActivityAnalyzer().analyze([commit], now=now).to_dict())

    def test_real_empty_git_repository(self):
        subprocess.run(["git", "init", "--quiet", str(self.root)], check=True)
        report = AnalysisRunner([GitActivityAnalyzerAdapter(), SASTAnalyzerAdapter()]).analyze(self.root)
        self.assertTrue(report.complete)
        self.assertEqual(report.checks["git_activity"].metrics["total_commits"], 0)

    def test_git_collection_failure_preserves_sast(self):
        with patch("sourcehealth.runner.GitCollector.collect", side_effect=GitCollectionError("private")):
            report = AnalysisRunner([GitActivityAnalyzerAdapter(), SASTAnalyzerAdapter()]).analyze(self.root)
        self.assertEqual(report.checks["git_activity"].error, "git_collection_failed")
        self.assertEqual(report.checks["sast"].status, "ok")
        self.assertFalse(report.complete)

    def test_sast_adapter_real_findings_and_partial_coverage(self):
        (self.root / "app.py").write_text("eval(data)\n", encoding="utf-8")
        for limit, expected in ((1000, "ok"), (1, "partial")):
            scanner = SASTScanner(ScanConfig(max_findings=limit))
            result = SASTAnalyzerAdapter(scanner).analyze(AnalysisContext(self.root))
            self.assertEqual(result.status, expected)
            self.assertEqual(result.metrics["files_scanned"], 1)
            self.assertEqual(result.findings[0]["rule_id"], "PY-DYNAMIC-EXEC")
            self.assertIn("ruleset_digest", result.metadata)
            self.assertEqual(result.metadata["complete"], expected == "ok")

    def test_legacy_build_report_does_not_collect_git_for_sast_only(self):
        with patch("sourcehealth.runner.GitCollector.collect", side_effect=AssertionError):
            report = build_report(self.root, SASTScanner())
        self.assertTrue(report["complete"])
        self.assertEqual(report["schema_version"], "1.0")
        self.assertEqual(report["checks"]["sast"]["files_scanned"], 0)

    def test_failed_sast_can_be_exported_as_incomplete_sarif(self):
        scanner = Mock()
        scanner.scan.side_effect = OSError("private")
        report = self.runner([SASTAnalyzerAdapter(scanner)]).analyze(self.root)
        sarif = to_sarif(to_legacy_report(report), ())
        self.assertFalse(sarif["runs"][0]["invocations"][0]["executionSuccessful"])

    def test_general_cli_defaults_to_full_report_and_can_disable_git(self):
        subprocess.run(["git", "init", "--quiet", str(self.root)], check=True)
        output = self.root / "report.json"
        self.assertEqual(main([str(self.root), "--output", str(output)]), 0)
        report = json.loads(output.read_text())
        self.assertEqual(report["schema_version"], "2.0")
        self.assertEqual(set(report["checks"]), {"sast", "git_activity"})
        with patch("sourcehealth.runner.GitCollector.collect", side_effect=AssertionError):
            self.assertEqual(main([str(self.root), "--no-git", "--output", str(output)]), 0)
        self.assertEqual(set(json.loads(output.read_text())["checks"]), {"sast"})

    def test_general_cli_fail_on_and_incomplete_precedence(self):
        (self.root / "app.py").write_text("eval(data)\n", encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main([str(self.root), "--no-git", "--fail-on", "low"]), 1)
            self.assertEqual(main([str(self.root), "--no-git", "--fail-on", "low",
                                   "--max-findings", "1"]), 2)


if __name__ == "__main__":
    unittest.main()
