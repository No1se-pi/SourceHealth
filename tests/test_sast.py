"""Поведенческие проверки SAST на искусственных, недействительных секретах.

Тесты не используют сеть и никогда не выполняют содержимое фикстур.
На ОС без прав создания symlink пропускается только соответствующая проверка.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sourcehealth.SAST import DEFAULT_RULES, Rule, SASTScanner, ScanConfig, load_rules, shannon_entropy
from sourcehealth.SAST.__main__ import main, write_report
from sourcehealth.SAST.container import ContainerError, run_repository, sourcecraft_clone_url


class SASTTests(unittest.TestCase):
    """Проверить находки, отсутствие утечек в отчёте и границы файлового обхода."""

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def write(self, name: str, content: str | bytes) -> Path:
        """Создать контролируемую фикстуру внутри временного дерева."""
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content.encode("utf-8") if isinstance(content, str) else content)
        return path

    def test_entropy_known_distributions(self) -> None:
        self.assertEqual(shannon_entropy(""), 0)
        self.assertEqual(shannon_entropy("aaaa"), 0)
        self.assertEqual(shannon_entropy("abab"), 1)
        self.assertEqual(shannon_entropy("abcd"), 2)

    def test_all_rules_and_redaction(self) -> None:
        github = "ghp_" + "Ab3D" * 9
        aws = "AKIA" + "A1B2" * 4
        generic = "aB3dE5fG7hJ9kL2mN4pQ6rS8"
        self.write("config.env", f'GITHUB_TOKEN="{github}"\nAWS_KEY={aws}\nAPI_KEY={generic}\n')
        self.write("private.pem", "-----BEGIN PRIVATE KEY-----\nsynthetic-data\n")
        self.write("app.py", "eval(user_input)\nsubprocess.run(command, shell=True)\npickle.loads(data)\nrequests.get(url, verify=False)\n")
        result = SASTScanner().scan(self.root)
        self.assertTrue(result.complete)
        self.assertEqual({f.rule_id for f in result.findings}, {
            "SECRET-PRIVATE-KEY", "SECRET-AWS-ACCESS-KEY", "SECRET-GITHUB-TOKEN", "SECRET-HIGH-ENTROPY",
            "PY-DYNAMIC-EXEC", "PY-SHELL-TRUE", "PY-PICKLE-LOAD", "PY-TLS-VERIFY-DISABLED",
        })
        self.assertEqual(len(result.findings), 8)  # generic не дублирует GitHub/AWS.
        serialized = json.dumps(result.to_dict())
        for secret in (github, aws, generic, "user_input", "synthetic-data"):
            self.assertNotIn(secret, serialized)
        location = next(f for f in result.findings if f.rule_id == "SECRET-HIGH-ENTROPY")
        self.assertEqual((location.path, location.line, location.column), ("config.env", 3, 9))

    def test_low_entropy_placeholders_and_unlabelled_hash_are_ignored(self) -> None:
        self.write(".env", 'password="aaaaaaaaaaaaaaaaaaaaaaaa"\nAPI_KEY="your_example_value_123456789"\nTOKEN=${SOME_LONG_ENVIRONMENT_NAME}\nhash="aB3dE5fG7hJ9kL2mN4pQ6rS8"\n')
        self.assertEqual(SASTScanner().scan(self.root).findings, [])

    def test_dotfiles_and_utf8_bom_are_scanned(self) -> None:
        self.write(".env", b"\xef\xbb\xbfAPI_KEY=aB3dE5fG7hJ9kL2mN4pQ6rS8\r\n")
        result = SASTScanner().scan(self.root)
        self.assertEqual(len(result.findings), 1)
        self.assertEqual(result.findings[0].column, 9)

    def test_custom_rule_is_easy_to_add_and_suffix_is_respected(self) -> None:
        custom = Rule("CUSTOM-TODO", r"\bTODO\b", "Review TODO", "Resolve it", suffixes=(".py",))
        self.write("nested/app.py", "# TODO\n")
        self.write("notes.txt", "TODO\n")
        result = SASTScanner(rules=[custom]).scan(self.root)
        self.assertEqual([f.path for f in result.findings], ["nested/app.py"])
        self.assertEqual(SASTScanner(rules=[]).scan(self.root).findings, [])

    def test_exclusions_and_binary_do_not_mark_supported_scope_incomplete(self) -> None:
        for name in (".git/config", "nested/node_modules/lib.py", "ignored.py"):
            self.write(name, "eval(data)")
        self.write("binary.bin", b"\x00eval(data)")
        result = SASTScanner(ScanConfig(exclude_globs=("ignored.py",))).scan(self.root)
        self.assertTrue(result.complete)
        self.assertFalse(result.findings)
        self.assertEqual(result.skipped["excluded"], 3)
        self.assertEqual(result.skipped["binary"], 1)

    def test_encoding_large_file_and_long_line_are_explicit(self) -> None:
        self.write("bad.txt", b"\xff\xfea")
        self.write("large.txt", "x" * 101)
        self.write("long.py", "# API_KEY=" + "x" * 31)
        result = SASTScanner(ScanConfig(max_file_bytes=100, max_line_chars=30)).scan(self.root)
        self.assertFalse(result.complete)
        self.assertEqual(result.skipped, {"encoding": 1, "file_size_limit": 1, "long_line": 1})

    def test_limits_bound_results_and_work(self) -> None:
        for number in range(4):
            self.write(f"{number}.py", "eval(data)\n" * 4)
        for config, reason in (
            (ScanConfig(max_findings=2), "finding_limit"),
            (ScanConfig(max_files=1), "file_limit"),
            (ScanConfig(max_entries=1), "entry_limit"),
            (ScanConfig(max_total_bytes=10), "total_bytes_limit"),
        ):
            with self.subTest(reason=reason):
                result = SASTScanner(config).scan(self.root)
                self.assertFalse(result.complete)
                self.assertIn(reason, result.skipped)
                self.assertLessEqual(len(result.findings), config.max_findings)

    def test_timeout_and_depth_are_reported(self) -> None:
        self.write("nested/deeper/app.py", "eval(data)")
        result = SASTScanner(ScanConfig(max_depth=1)).scan(self.root)
        self.assertIn("depth_limit", result.skipped)
        with patch("sourcehealth.SAST.scanner.time.monotonic", side_effect=[0, 31, 32]):
            result = SASTScanner().scan(self.root)
        self.assertEqual(result.skipped, {"timeout": 1})
        self.assertFalse(result.complete)

    def test_symlink_file_and_directory_are_not_followed(self) -> None:
        with tempfile.TemporaryDirectory() as outside:
            secret = Path(outside) / "secret.py"
            secret.write_text("eval(data)", encoding="utf-8")
            try:
                (self.root / "linked.py").symlink_to(secret)
                (self.root / "linked-dir").symlink_to(outside, target_is_directory=True)
            except OSError:
                self.skipTest("OS does not permit symlinks")
            result = SASTScanner().scan(self.root)
            self.assertFalse(result.findings)
            self.assertEqual(result.skipped["link"], 2)

    def test_hardlinks_are_not_read(self) -> None:
        original = self.write("source.py", "eval(data)")
        try:
            os.link(original, self.root / "copy.py")
        except OSError:
            self.skipTest("OS does not permit hardlinks")
        result = SASTScanner().scan(self.root)
        self.assertFalse(result.findings)
        self.assertEqual(result.skipped["hardlink"], 2)

    @unittest.skipUnless(hasattr(os, "mkfifo"), "FIFO requires Unix")
    def test_fifo_is_skipped_without_blocking(self) -> None:
        os.mkfifo(self.root / "pipe")
        result = SASTScanner().scan(self.root)
        self.assertEqual(result.skipped["special_file"], 1)

    def test_read_error_is_not_a_clean_scan(self) -> None:
        self.write("app.py", "eval(data)")
        with patch("sourcehealth.SAST.scanner.os.open", side_effect=PermissionError):
            result = SASTScanner().scan(self.root)
        self.assertFalse(result.complete)
        self.assertEqual(result.skipped["read_error"], 1)

    def test_scanning_does_not_import_or_execute_files(self) -> None:
        marker = self.root / "EXECUTED"
        self.write("setup.py", f"from pathlib import Path\nPath({str(marker)!r}).touch()\n")
        self.write(".sourcehealth.py", "raise RuntimeError('must never run')")
        result = SASTScanner().scan(self.root)
        self.assertTrue(result.complete)
        self.assertFalse(marker.exists())

    def test_repeat_scans_have_independent_results(self) -> None:
        file = self.write("app.py", "eval(data)")
        scanner = SASTScanner()
        first = scanner.scan(self.root)
        file.write_text("pass", encoding="utf-8")
        second = scanner.scan(self.root)
        self.assertEqual(len(first.findings), 1)
        self.assertFalse(second.findings)

    def test_cli_json_and_exit_codes(self) -> None:
        self.write("app.py", "eval(data)")
        output = self.root / "report.json"
        self.assertEqual(main([str(self.root), "--output", str(output)]), 0)
        self.assertEqual(main([str(self.root), "--output", str(output), "--fail-on", "medium"]), 1)
        report = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(report["checks"]["sast"]["files_scanned"], 1)
        self.assertEqual(main([str(self.root), "--output", str(output), "--max-findings", "1"]), 2)
        self.assertFalse(json.loads(output.read_text())["complete"])
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main([str(self.root / "missing")]), 2)

    def test_cli_git_integration_real_empty_repository(self) -> None:
        subprocess.run(["git", "init", "--quiet", str(self.root)], check=True)
        output = self.root / "report.json"
        self.assertEqual(main([str(self.root), "--with-git", "--output", str(output)]), 0)
        report = json.loads(output.read_text())
        self.assertEqual(report["checks"]["git_activity"]["metrics"]["total_commits"], 0)
        self.assertTrue(report["complete"])

    def test_failed_git_preserves_sast_and_reports_incomplete(self) -> None:
        output = self.root / "report.json"
        self.assertEqual(main([str(self.root), "--with-git", "--output", str(output)]), 2)
        report = json.loads(output.read_text())
        self.assertEqual(report["checks"]["git_activity"]["status"], "error")
        self.assertTrue(report["checks"]["sast"]["complete"])
        self.assertFalse(report["complete"])

    def test_atomic_write_preserves_old_report_on_failure(self) -> None:
        output = self.write("report.json", '{"old": true}')
        with patch("sourcehealth.SAST.__main__.os.replace", side_effect=OSError):
            with self.assertRaises(OSError):
                write_report({"new": True}, output)
        self.assertEqual(json.loads(output.read_text()), {"old": True})
        self.assertEqual(list(self.root.iterdir()), [output])

    def test_invalid_configuration_and_duplicate_rules_are_rejected(self) -> None:
        for options in ({"max_files": 0}, {"max_entries": -1}, {"timeout_seconds": float("nan")}, {"max_depth": 1.5}):
            with self.assertRaises(ValueError):
                ScanConfig(**options)
        with self.assertRaises(ValueError):
            SASTScanner(rules=[DEFAULT_RULES[0], DEFAULT_RULES[0]])

    def test_json_rule_files_are_loaded_and_validated(self) -> None:
        rule = {"id": "CUSTOM-TODO", "pattern": "TODO", "message": "Review", "recommendation": "Fix"}
        path = self.write("rules/custom.json", json.dumps(rule))
        self.assertEqual(load_rules(path.parent)[0].id, "CUSTOM-TODO")
        for data in ([], {**rule, "unexpected": True}, {**rule, "pattern": "["},
                     {**rule, "keywords": "TODO"}, {**rule, "entropy_threshold": "high"}):
            path.write_text(json.dumps(data), encoding="utf-8")
            with self.subTest(data=data), self.assertRaisesRegex(ValueError, "custom.json"):
                load_rules(path.parent)
        path.write_text(json.dumps(rule), encoding="utf-8")
        self.write("rules/duplicate.json", json.dumps(rule))
        with self.assertRaisesRegex(ValueError, "unique"):
            load_rules(path.parent)

    def test_repository_rules_are_not_auto_loaded(self) -> None:
        self.write("rules/evil.json", "invalid json")
        self.write("app.py", "eval(data)")
        self.assertEqual(len(SASTScanner().scan(self.root).findings), 1)


class ContainerWorkflowTests(unittest.TestCase):
    """Контракт оркестратора без зависимости тестов от Docker и внешней сети."""

    def test_sourcecraft_urls_and_ssrf_rejection(self) -> None:
        for url in ("https://sourcecraft.dev/team/repo", "https://git@git.sourcecraft.dev/team/repo.git"):
            self.assertEqual(sourcecraft_clone_url(url), "https://git.sourcecraft.dev/team/repo.git")
        for url in (
            "http://sourcecraft.dev/a/b", "https://127.0.0.1/a/b", "file:///tmp/repo",
            "https://sourcecraft.dev.evil.test/a/b", "https://sourcecraft.dev:443/a/b",
            "https://git:secret@git.sourcecraft.dev/a/b", "https://sourcecraft.dev/a/b?url=evil",
            "https://sourcecraft.dev/a/../b", "https://sourcecraft.dev/a/%2e%2e",
            "https://sourcecraft.dev/a/b#fragment", "--upload-pack=bad",
        ):
            with self.subTest(url=url), self.assertRaises(ValueError):
                sourcecraft_clone_url(url)

    def test_clone_timeout_cleans_containers_and_volume(self) -> None:
        calls = []

        def fake_docker(arguments, **kwargs):
            calls.append(arguments)
            if arguments[0] == "start":
                raise ContainerError("container_timeout")
            return ""

        with patch("sourcehealth.SAST.container._docker", side_effect=fake_docker):
            report = run_repository("https://sourcecraft.dev/team/repo")
        self.assertFalse(report["complete"])
        self.assertEqual(report["error"], {"stage": "clone", "code": "container_timeout"})
        self.assertEqual(calls[-2][:2], ["rm", "--force"])
        self.assertEqual(calls[-1][:2], ["volume", "rm"])

    def test_scan_runs_offline_and_partial_json_survives(self) -> None:
        candidate = {"schema_version": "1.0", "checks": {"sast": {"complete": False, "findings": []}}, "complete": False}
        completed = subprocess.CompletedProcess([], 2, json.dumps(candidate), "")
        with patch("sourcehealth.SAST.container._docker", return_value="") as docker:
            with patch("sourcehealth.SAST.container.subprocess.run", return_value=completed):
                report = run_repository("https://sourcecraft.dev/team/repo")
        creates = [call.args[0] for call in docker.call_args_list if call.args[0][0] == "create"]
        self.assertIn("--network=none", creates[1])
        self.assertTrue(any("target=/workspace,readonly" in arg for arg in creates[1]))
        self.assertIn("--cap-drop=ALL", creates[0])
        self.assertIn("sast", report["checks"])
        self.assertFalse(report["complete"])

    def test_cleanup_failure_is_visible(self) -> None:
        def fake_docker(arguments, **kwargs):
            if arguments[0] in {"start", "rm"}:
                raise ContainerError("docker_command_failed")
            return ""

        with patch("sourcehealth.SAST.container._docker", side_effect=fake_docker):
            report = run_repository("https://sourcecraft.dev/team/repo")
        self.assertEqual(len(report["cleanup_pending"]), 1)
        self.assertFalse(report["complete"])

    def test_scan_timeout_cleans_both_containers_and_volume(self) -> None:
        with patch("sourcehealth.SAST.container._docker", return_value="") as docker:
            with patch("sourcehealth.SAST.container.subprocess.run", side_effect=subprocess.TimeoutExpired("docker", 1)):
                report = run_repository("https://sourcecraft.dev/team/repo")
        self.assertEqual(report["error"], {"stage": "analyze", "code": "container_timeout"})
        arguments = [call.args[0] for call in docker.call_args_list]
        self.assertEqual(sum(args[0] == "rm" for args in arguments), 2)
        self.assertEqual(arguments[-1][:2], ["volume", "rm"])

    def test_inconsistent_container_report_cannot_claim_success(self) -> None:
        candidate = {"schema_version": "1.0", "checks": {"sast": {"complete": False, "findings": []}}, "complete": True}
        completed = subprocess.CompletedProcess([], 2, json.dumps(candidate), "")
        with patch("sourcehealth.SAST.container._docker", return_value=""):
            with patch("sourcehealth.SAST.container.subprocess.run", return_value=completed):
                report = run_repository("https://sourcecraft.dev/team/repo")
        self.assertFalse(report["complete"])
        self.assertEqual(report["error"]["code"], "inconsistent_report")


if __name__ == "__main__":
    unittest.main()
