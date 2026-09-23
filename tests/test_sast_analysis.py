"""Проверки точности правил и синтаксического анализа на безопасных строках.

Фикстуры содержат фрагменты кода как данные: тесты не исполняют их и не проверяют
работоспособность токенов. Каждое JSON-правило обязано иметь positive/negative pair.
"""

import contextlib
import io
import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from sourcehealth.sast import DEFAULT_RULES, SASTScanner, ScanConfig, load_rules
from sourcehealth.sast.__main__ import main
from sourcehealth.sast.rules import ruleset_digest


class AnalysisTests(unittest.TestCase):
    """Сравнить наблюдаемые находки с ожидаемыми, включая случаи без находок."""

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def scan(self, source, filename="app.py", config=None, rules=None):
        path = self.root / filename
        path.write_bytes(source if isinstance(source, bytes) else source.encode("utf-8"))
        return SASTScanner(config, rules).scan(self.root)

    def ids(self, source):
        return [finding.rule_id for finding in self.scan(source).findings]

    def test_every_shipped_rule_has_positive_and_negative_fixture(self):
        fixtures = json.loads((Path(__file__).parent / "fixtures/sast_rules.json").read_text(encoding="utf-8"))
        self.assertEqual(set(fixtures), {rule.id for rule in DEFAULT_RULES})
        for rule in DEFAULT_RULES:
            fixture = fixtures[rule.id]
            for name, expected in (("positive", 1), ("negative", 0)):
                with self.subTest(rule=rule.id, fixture=name):
                    with tempfile.TemporaryDirectory() as directory:
                        path = Path(directory) / fixture["filename"]
                        # Синтетические секреты хранятся фрагментами: целый токен
                        # появляется только во временном файле во время теста.
                        path.write_text("".join(fixture[name]), encoding="utf-8")
                        result = SASTScanner(rules=[rule]).scan(directory)
                    self.assertTrue(result.complete, result.skipped)
                    self.assertEqual(len(result.findings), expected)

    def test_aliases_multiline_calls_and_unicode_columns(self):
        result = self.scan('from subprocess import run as launch\nимя = "ok"; launch(\n cmd,\n shell=True,\n)\n')
        self.assertEqual(len(result.findings), 1)
        finding = result.findings[0]
        self.assertEqual((finding.line, finding.column), (2, 13))
        self.assertEqual(finding.engine, "python_call")
        self.assertEqual(finding.cwe, "CWE-78")

    def test_comments_docstrings_and_ordinary_strings_do_not_trigger_python_rules(self):
        self.assertEqual(self.ids('"""pickle.loads(data)"""\n# eval(data)\ntext="requests.get(url, verify=False)"\n'), [])

    def test_local_shadowing_and_reassignment_do_not_inherit_library_meaning(self):
        for source in (
            'def f(eval):\n    return eval(data)\n',
            'import pickle\ndef f(pickle):\n    pickle.loads(data)\n',
            'import pickle\npickle = custom\npickle.loads(data)\n',
            'def eval(value):\n    return value\neval(data)\n',
            'import pickle as p\ndef f():\n    p.loads(data)\n    p = custom\n',
            'import pickle as p\ndef f():\n    from my_library import loads as p\n    p(data)\n',
        ):
            with self.subTest(source=source):
                self.assertEqual(self.ids(source), [])

    def test_nested_scopes_and_comprehensions_keep_imports_where_visible(self):
        source = ('import pickle as p\n'
                  'def outer():\n'
                  '    def inner(p):\n'
                  '        return p.loads(data)\n'
                  '    return p.loads(data)\n'
                  'values = [p.loads(data) for p in objects]\n'
                  'p.loads(data)\n')
        result = self.scan(source)
        self.assertEqual([f.line for f in result.findings], [5, 7])

    def test_lambda_default_is_evaluated_in_outer_scope(self):
        result = self.scan('import pickle\nf = lambda pickle=pickle.loads(data): pickle.loads(data)\n')
        self.assertEqual(len(result.findings), 1)

    def test_sessions_resolve_known_factories_but_not_arbitrary_objects(self):
        result = self.scan('import requests\ns = requests.Session()\ns.get(url, verify=False)\nother.get(url, verify=False)\n')
        self.assertEqual([f.line for f in result.findings], [3])

    def test_safe_yaml_loader_aliases_are_not_reported(self):
        source = 'from yaml import load as read, SafeLoader as Safe\nread(data, Safe)\n'
        self.assertEqual(self.ids(source), [])
        source = 'from yaml import load as read, UnsafeLoader as Unsafe\nread(data, Unsafe)\n'
        self.assertEqual(self.ids(source), ["PY-UNSAFE-YAML"])

    def test_sql_formats_and_parameterized_safe_alternative(self):
        result = self.scan('cursor.execute("SELECT * FROM t WHERE id=%s" % user_id)\n'
                           'cursor.execute("SELECT * FROM t WHERE id={}".format(user_id))\n'
                           'cursor.execute("SELECT * FROM t WHERE id=" + user_id)\n'
                           'cursor.execute("SELECT * FROM t WHERE id=%s", [user_id])\n')
        self.assertEqual([f.line for f in result.findings], [1, 2, 3])

    def test_python_parse_error_preserves_secret_detection_and_does_not_leak(self):
        secret = 'ghp_' + 'Ab3D' * 9
        result = self.scan(f'TOKEN="{secret}"\neval(\n')
        self.assertFalse(result.complete)
        self.assertEqual(result.skipped["python_syntax_error"], 1)
        self.assertEqual(result.findings[0].rule_id, "SECRET-GITHUB-TOKEN")
        self.assertEqual(result.diagnostics[0]["path"], "app.py")
        self.assertNotIn(secret, json.dumps(result.to_dict()))

    def test_python_parser_warnings_do_not_print_source(self):
        output = io.StringIO()
        with contextlib.redirect_stderr(output):
            self.scan('x = 1 is 2\neval(data)\n')
        self.assertEqual(output.getvalue(), "")

    def test_ast_node_budget_reports_incomplete(self):
        result = self.scan('eval(data)\n' * 10, config=ScanConfig(max_ast_nodes=10))
        self.assertFalse(result.complete)
        self.assertEqual(result.skipped["python_ast_limit"], 1)

    def test_ast_findings_obey_shared_limit_with_secrets(self):
        result = self.scan('TOKEN="ghp_' + 'Ab3D' * 9 + '"\neval(data)\nexec(data)\n',
                           config=ScanConfig(max_findings=2))
        self.assertFalse(result.complete)
        self.assertEqual(len(result.findings), 2)
        self.assertEqual(result.skipped["finding_limit"], 1)

    def test_specific_tokens_win_over_entropy_regardless_of_rule_order(self):
        result = self.scan('TOKEN="glpat-' + 'Ab3D' * 5 + '"', "config.env", rules=tuple(reversed(DEFAULT_RULES)))
        self.assertEqual([f.rule_id for f in result.findings], ["SECRET-GITLAB-TOKEN"])

    def test_unicode_bom_encodings_and_cr_newlines(self):
        for encoding in ("utf-16", "utf-32", "utf-8-sig"):
            with self.subTest(encoding=encoding):
                content = ('first=1\rTOKEN="ghp_' + 'Ab3D' * 9 + '"\r').encode(encoding)
                result = self.scan(content, "config.env")
                self.assertTrue(result.complete)
                self.assertEqual(result.findings[0].line, 2)

    def test_python_pep263_encoding_is_respected(self):
        result = self.scan('# coding: cp1251\nимя = 1; eval(data)\n'.encode("cp1251"))
        self.assertTrue(result.complete)
        self.assertEqual(result.findings[0].column, 10)

    def test_ruleset_digest_changes_only_with_rule_content(self):
        self.assertEqual(ruleset_digest(DEFAULT_RULES), ruleset_digest(tuple(DEFAULT_RULES)))
        changed = (replace(DEFAULT_RULES[0], severity="low"), *DEFAULT_RULES[1:])
        self.assertNotEqual(ruleset_digest(DEFAULT_RULES), ruleset_digest(changed))

    def test_duplicate_json_fields_fail_instead_of_silently_overriding(self):
        (self.root / "rule.json").write_text('{"id":"ONE", "id":"TWO"}', encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "rule.json"):
            load_rules(self.root)

    def test_no_ast_parse_for_file_without_supported_symbols(self):
        with patch("sourcehealth.sast.python_analysis.ast.parse", side_effect=AssertionError("unnecessary parse")):
            result = self.scan('def add(a, b):\n    return a + b\n')
        self.assertTrue(result.complete)
        self.assertEqual(result.python_files_parsed, 0)
        self.assertEqual(result.code_files_analyzed, 1)

    def test_code_files_analyzed_counts_supported_files_once(self):
        (self.root / "safe.py").write_text("value = 1\n", encoding="utf-8")
        (self.root / "unsafe.py").write_text("eval(data)\n", encoding="utf-8")
        (self.root / "neutral.txt").write_text("neutral\n", encoding="utf-8")
        result = SASTScanner().scan(self.root)
        self.assertEqual(result.code_files_analyzed, 2)
        self.assertEqual(result.python_files_parsed, 1)

    def test_match_capture_shadows_import(self):
        result = self.scan('import pickle\nmatch data:\n    case {"value": pickle}:\n        pickle.loads(data)\n')
        self.assertEqual(result.findings, [])

    def test_cli_lists_rules_and_can_disable_a_known_rule(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(main(["--list-rules"]), 0)
        catalogue = json.loads(output.getvalue())
        self.assertEqual(len(catalogue["rules"]), len(DEFAULT_RULES))
        self.scan('eval(data)')
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(main([str(self.root), "--disable-rule", "PY-DYNAMIC-EXEC"]), 0)
        report = json.loads(output.getvalue())
        self.assertEqual(report["checks"]["sast"]["findings"], [])
        self.assertNotIn("PY-DYNAMIC-EXEC", report["checks"]["sast"]["rule_ids"])

    def test_sarif_preserves_severity_coordinates_and_redaction(self):
        token = 'ghp_' + 'Ab3D' * 9
        self.scan(f'TOKEN="{token}"\n', "имя #.env")
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = main([str(self.root), "--format", "sarif", "--fail-on", "high"])
        self.assertEqual(code, 1)
        sarif = json.loads(output.getvalue())
        self.assertEqual(sarif["version"], "2.1.0")
        run = sarif["runs"][0]
        self.assertTrue(run["invocations"][0]["executionSuccessful"])
        self.assertEqual(run["columnKind"], "unicodeCodePoints")
        finding = run["results"][0]
        self.assertEqual(finding["level"], "error")
        self.assertEqual(finding["locations"][0]["physicalLocation"]["region"]["startLine"], 1)
        uri = finding["locations"][0]["physicalLocation"]["artifactLocation"]["uri"]
        self.assertIn("%23", uri)
        self.assertNotIn(token, output.getvalue())

    def test_sarif_partial_scan_remains_unsuccessful(self):
        self.scan('eval(\n')
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = main([str(self.root), "--format", "sarif"])
        self.assertEqual(code, 2)
        self.assertFalse(json.loads(output.getvalue())["runs"][0]["invocations"][0]["executionSuccessful"])

    def test_cli_custom_json_rule_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            rule = {"id":"CUSTOM-ECHO", "pattern":"UNSAFE", "message":"Review", "recommendation":"Fix"}
            (Path(directory) / "echo.json").write_text(json.dumps(rule), encoding="utf-8")
            self.scan('UNSAFE', "example.txt")
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(main([str(self.root), "--rules-dir", directory]), 0)
            self.assertEqual(json.loads(output.getvalue())["checks"]["sast"]["rule_ids"], ["CUSTOM-ECHO"])

    def test_invalid_cli_rule_id_does_not_silently_disable_checks(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
            main([str(self.root), "--disable-rule", "TYPO"])
        self.assertEqual(error.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
