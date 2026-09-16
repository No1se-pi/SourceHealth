"""Runtime boundary fixtures: no external services and no execution of target code."""

import json
import unittest
from copy import deepcopy
from unittest.mock import Mock, patch

from sourcehealth.application.pipeline import analyze_context
from sourcehealth.core import AnalysisContext
from sourcehealth.core.domain import DataAvailability, RepositoryRef
from sourcehealth.git.activity import GitActivityAnalyzer
from sourcehealth.runtime import DockerAnalysisRuntime
from sourcehealth.runtime_results import normalize_runtime_report
from sourcehealth.sast.models import ScanResult
from sourcehealth.scoring.engine import ScoringEngine


def runtime_fixture(*, partial=False):
    return {"schema_version": "1.0", "complete": not partial, "checks": {
        "git_activity": {"status": "ok", "metrics": GitActivityAnalyzer().analyze([]).to_dict()},
        "sast": ScanResult(complete=not partial, files_scanned=3,
                           skipped={"file_limit": 1} if partial else {}).to_dict(),
    }}


class RuntimePipelineTests(unittest.TestCase):
    def setUp(self):
        self.repository = RepositoryRef.from_url("https://sourcecraft.dev/example/project", visibility="public")
        self.context = AnalysisContext(repository=self.repository,
            sourcecraft_facts={"repository_metadata": {"visibility": "public"}},
            collection_statuses={"repository_metadata": DataAvailability.AVAILABLE})

    def report(self, runtime):
        report = analyze_context(self.context, include_code=True, runtime=runtime)
        ScoringEngine().apply(report)
        return report

    def test_success_combines_git_sast_platform_with_one_runtime_call(self):
        fixture = runtime_fixture()
        before = deepcopy(fixture)
        runtime = Mock(analyze=Mock(return_value=fixture))
        report = self.report(runtime)
        runtime.analyze.assert_called_once_with(self.repository)
        self.assertEqual(fixture, before)
        self.assertEqual(set(report.checks), {"git_activity", "sast", "repository_metadata", "sourcecraft_appsec"})
        self.assertEqual(report.checks["git_activity"].status, "ok")
        self.assertEqual(report.checks["git_activity"].category, "activity")
        self.assertEqual(report.checks["sast"].metrics["files_scanned"], 3)
        self.assertEqual((report.checks["sast"].category, report.checks["sast"].source),
                         ("code_health", "sourcehealth_local"))
        self.assertEqual(report.category_scores["security"]["availability"], "no_data")
        self.assertIsNone(report.health_score)
        self.assertEqual(report.to_public_dict()["schema_version"], "3.0")

    def test_partial_sast_preserves_git_and_coverage(self):
        report = self.report(Mock(analyze=Mock(return_value=runtime_fixture(partial=True))))
        self.assertFalse(report.complete)
        self.assertEqual(report.checks["git_activity"].status, "ok")
        self.assertEqual(report.checks["sast"].availability, DataAvailability.PARTIAL)
        self.assertEqual(report.checks["sast"].metadata["skipped"], {"file_limit": 1})

    def test_exception_keeps_platform_and_does_not_leak(self):
        report = self.report(Mock(analyze=Mock(side_effect=RuntimeError("private stderr marker"))))
        self.assertEqual(report.checks["repository_metadata"].status, "ok")
        self.assertEqual(report.checks["git_activity"].availability, DataAvailability.NO_DATA)
        self.assertNotIn("private stderr marker", json.dumps(report.to_public_dict()))
        self.assertEqual(report.status, "partial")

    def test_unconfigured_runtime_is_explicit_and_platform_profile_skips_runtime(self):
        self.assertEqual(self.report(None).checks["sast"].error, "runtime_not_configured")
        runtime = Mock()
        report = analyze_context(self.context, runtime=runtime)
        runtime.analyze.assert_not_called()
        self.assertNotIn("sast", report.checks)

    def test_malformed_check_does_not_discard_other_checks(self):
        for invalid in (None, [], {"complete": "yes"}, {"complete": True, "findings": [], "files_scanned": float("nan")}):
            with self.subTest(invalid=invalid):
                fixture = runtime_fixture()
                fixture["checks"]["sast"] = invalid
                checks = normalize_runtime_report(fixture)
                self.assertEqual(checks["git_activity"].status, "ok")
                self.assertEqual(checks["sast"].availability, DataAvailability.NO_DATA)

    def test_envelope_failures_are_safe_and_cleanup_is_not_success(self):
        for code in ("container_timeout", "docker_unavailable", "docker_command_failed", "private stderr marker"):
            checks = normalize_runtime_report({"schema_version": "1.0", "complete": False, "checks": {},
                                               "error": {"stage": "clone", "code": code}})
            self.assertEqual(checks["sast"].error, code if code != "private stderr marker" else "runtime_failed")
        fixture = runtime_fixture()
        fixture.update(complete=False, cleanup_pending=["private resource marker"])
        checks = normalize_runtime_report(fixture)
        self.assertTrue(all(c.status == "partial" and c.error == "runtime_cleanup_pending" for c in checks.values()))
        self.assertNotIn("private resource marker", json.dumps({k: v.to_dict() for k, v in checks.items()}))

    def test_finding_text_comes_from_trusted_rules_and_paths_are_relative(self):
        from sourcehealth.sast.rules import DEFAULT_RULES

        fixture = runtime_fixture()
        fixture["checks"]["sast"]["findings"] = [{"rule_id": DEFAULT_RULES[0].id, "path": "src/test.py",
                                                 "line": 1, "column": 1, "message": "private text marker",
                                                 "snippet": "private text marker", "value": "private text marker"}]
        fixture["checks"]["git_activity"]["metrics"]["raw_log"] = "private text marker"
        checks = normalize_runtime_report(fixture)
        self.assertEqual(checks["sast"].findings[0]["message"], DEFAULT_RULES[0].message)
        self.assertNotIn("private text marker", json.dumps({k: v.to_dict() for k, v in checks.items()}))
        for path in ("/workspace/repo/test.py", "../test.py", "C:\\private\\test.py"):
            fixture["checks"]["sast"]["findings"][0]["path"] = path
            self.assertEqual(normalize_runtime_report(fixture)["sast"].error, "runtime_invalid_check")

    def test_docker_adapter_delegates_once_to_existing_workflow(self):
        with patch("sourcehealth.sast.container.run_repository", return_value=runtime_fixture()) as run:
            report = self.report(DockerAnalysisRuntime(image="trusted-image", timeout=20))
        run.assert_called_once_with(self.repository.canonical_url, image="trusted-image", timeout=20)
        self.assertEqual(report.checks["git_activity"].status, "ok")

    def test_interrupt_is_not_swallowed(self):
        with self.assertRaises(KeyboardInterrupt):
            self.report(Mock(analyze=Mock(side_effect=KeyboardInterrupt)))
