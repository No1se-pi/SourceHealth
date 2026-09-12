"""Регрессии лексического анализа Go/Rust/Java/C++ и пакетного поиска.

Фрагменты служат исключительно входными данными сканера. Ни один подозрительный
вызов не исполняется. Проверяем наблюдаемые находки, координаты и полноту отчёта.
"""

import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from sourcehealth.sast import DEFAULT_RULES, Rule, SASTScanner, ScanConfig


class PolyglotTests(unittest.TestCase):
    """Одинаковый контракт поиска для всех четырёх языков и старых regex-правил."""

    @staticmethod
    def scan(source, suffix, rule_id=None, config=None, rules=None):
        """Изолировать каждый пример, чтобы соседние файлы не влияли на результат."""
        selected = rules if rules is not None else (
            [r for r in DEFAULT_RULES if r.id == rule_id] if rule_id else None)
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / ("sample" + suffix)).write_bytes(source.encode("utf-8"))
            return SASTScanner(config, selected).scan(directory)

    def test_all_code_rules_ignore_comments_and_raw_string_examples(self):
        fixtures = json.loads((Path(__file__).parent / "fixtures/sast_rules.json").read_text(encoding="utf-8"))
        wrappers = {
            "go": lambda value: '`' + value + '`',
            "rust": lambda value: 'r###"' + value + '"###',
            "java": lambda value: '"""\n' + value + '\n"""',
            "cpp": lambda value: 'R"example(' + value + ')example"',
        }
        for rule in DEFAULT_RULES:
            if rule.engine != "code_regex":
                continue
            example = "".join(fixtures[rule.id]["positive"])
            for source in ('// ' + example + '\n', '/* ' + example + ' */', wrappers[rule.language](example)):
                with self.subTest(rule=rule.id, source=source):
                    result = self.scan(source, rule.suffixes[0], rule.id)
                    self.assertTrue(result.complete, result.skipped)
                    self.assertEqual(result.findings, [])

    def test_multiline_and_comments_between_call_tokens(self):
        cases = [
            ('.go', 'GO-TLS-NO-VERIFY', 'InsecureSkipVerify /* explanation */ :\n true'),
            ('.rs', 'RUST-TLS-NO-VERIFY', 'client.danger_accept_invalid_certs(\n /* reason */ true\n);'),
            ('.java', 'JAVA-WEAK-HASH', 'MessageDigest // explanation\n . getInstance(\n "MD5"\n);'),
            ('.cpp', 'CPP-STRCPY', 'strcpy /* explanation */ (dest, input);'),
        ]
        for suffix, rule_id, source in cases:
            with self.subTest(language=suffix):
                result = self.scan(source, suffix, rule_id)
                self.assertTrue(result.complete)
                self.assertEqual([f.rule_id for f in result.findings], [rule_id])

    def test_nested_rust_comments_and_lifetimes(self):
        result = self.scan("/* outer /* inner */ data.get_unchecked(i); */\n"
                           "fn f<'a, 'b>(v: &'a [u8]) { v.get_unchecked(i); }", '.rs', 'RUST-UNCHECKED-INDEX')
        self.assertTrue(result.complete)
        self.assertEqual(len(result.findings), 1)
        self.assertEqual(result.findings[0].line, 2)

    def test_cpp_continued_line_comment(self):
        result = self.scan('// example \\\nstrcpy(dest, input);\nstrcpy(dest, input);', '.cpp', 'CPP-STRCPY')
        self.assertEqual([f.line for f in result.findings], [3])

    def test_cpp_digit_separators_do_not_hide_following_calls(self):
        result = self.scan("auto n = 1'000'000; auto h = 0xFF'AB; strcpy(d,s);", '.cpp', 'CPP-STRCPY')
        self.assertTrue(result.complete)
        self.assertEqual(len(result.findings), 1)

    def test_raw_strings_keep_comment_markers_and_inner_quotes_as_data(self):
        cases = [
            ('.rs', 'RUST-UNCHECKED-INDEX', 'r##" " /* data.get_unchecked(i); // "##;\ndata.get_unchecked(i);'),
            ('.cpp', 'CPP-STRCPY', 'u8R"xx( " /* strcpy(d,s); // )xx";\nstrcpy(d,s);'),
            ('.go', 'GO-TLS-NO-VERIFY', '` " /* InsecureSkipVerify: true // `\nInsecureSkipVerify: true'),
            ('.java', 'JAVA-WEAK-HASH', '"""\n \\""" MessageDigest.getInstance("MD5");\n""";\nMessageDigest.getInstance("MD5");'),
        ]
        for suffix, rule_id, source in cases:
            with self.subTest(language=suffix):
                result = self.scan(source, suffix, rule_id)
                self.assertTrue(result.complete, result.skipped)
                self.assertEqual(len(result.findings), 1)
                self.assertEqual(result.findings[0].line, source.count('\n') + 1)

    def test_unclosed_raw_literals_and_comments_report_incomplete(self):
        for suffix, rule_id, prefix, example in (
            ('.rs', 'RUST-UNCHECKED-INDEX', 'r###"', 'data.get_unchecked(i);'),
            ('.cpp', 'CPP-STRCPY', 'R"tag(', 'strcpy(d,s);'),
            ('.go', 'GO-TLS-NO-VERIFY', '`', 'InsecureSkipVerify: true'),
            ('.java', 'JAVA-WEAK-HASH', '"""\n', 'MessageDigest.getInstance("MD5");'),
            ('.cpp', 'CPP-STRCPY', '/*', 'strcpy(d,s);'),
        ):
            with self.subTest(language=suffix, prefix=prefix):
                result = self.scan(prefix + example, suffix, rule_id)
                self.assertFalse(result.complete)
                self.assertIn('lexical_error', result.skipped)
                self.assertEqual(result.findings, [])

    def test_unicode_columns_and_crlf_coordinates(self):
        result = self.scan('// Пример\r\n"имя"; strcpy(d,s);', '.cpp', 'CPP-STRCPY')
        self.assertEqual([(f.line, f.column) for f in result.findings], [(2, 8)])

    def test_long_lines_preserve_following_coordinates(self):
        result = self.scan('strcpy(d,s);' + ' ' * 80 + '\nstrcpy(d,s);', '.cpp', 'CPP-STRCPY',
                           ScanConfig(max_line_chars=64))
        self.assertFalse(result.complete)
        self.assertEqual(result.skipped.get('long_line'), 1)
        self.assertEqual([f.line for f in result.findings], [2])

    def test_secrets_in_comments_are_still_found_without_leaking_values(self):
        token = 'ghp_' + 'Ab3D' * 9
        source = '// TOKEN="' + token + '"; strcpy(d,s);\n'
        result = self.scan(source, '.cpp')
        self.assertEqual([f.rule_id for f in result.findings], ['SECRET-GITHUB-TOKEN'])
        self.assertNotIn(token, json.dumps(result.to_dict()))

    def test_shared_finding_limit_covers_text_and_code_engines(self):
        source = '// ghp_' + 'Ab3D' * 9 + '\nstrcpy(d,s);\nstrcat(d,s);'
        result = self.scan(source, '.cpp', config=ScanConfig(max_findings=2))
        self.assertEqual(len(result.findings), 2)
        self.assertFalse(result.complete)
        self.assertIn('finding_limit', result.skipped)

    def test_parameterized_queries_and_bounded_output_are_not_flagged(self):
        for suffix, source in (
            ('.go', 'db.Query("SELECT * FROM users WHERE id=?", id)'),
            ('.java', 'conn.prepareStatement("SELECT * FROM users WHERE id=?");'),
            ('.cpp', 'snprintf(buffer, sizeof(buffer), "%s", input);\nscanf("%31s", buffer);'),
        ):
            with self.subTest(language=suffix):
                self.assertEqual(self.scan(source, suffix).findings, [])

    def test_entropy_prefilter_preserves_the_complete_supported_alphabet(self):
        rule = next(r for r in DEFAULT_RULES if r.id == 'SECRET-HIGH-ENTROPY')
        for char in ':{}?%&*/+=.!@#$-_':
            value = 'aB3dE5fG7hJ9kL2m' + char
            with self.subTest(char=char):
                result = self.scan('API_KEY="' + value + '"', '.env', rules=[rule])
                self.assertEqual(len(result.findings), 1)

    def test_legacy_regex_retains_line_semantics(self):
        rule = Rule('CUSTOM-LINE', r'^abc$', 'Example', 'Review')
        self.assertEqual(len(self.scan('abc\nabc', '.txt', rules=[rule]).findings), 2)
        multiline = replace(rule, engine='text_regex', pattern=r'abc\s+abc')
        self.assertEqual(len(self.scan('abc\nabc', '.txt', rules=[multiline]).findings), 1)

    def test_language_selector_rejects_mismatched_suffixes(self):
        with self.assertRaises(ValueError):
            Rule('CUSTOM-GO', 'danger', 'Example', 'Review', engine='code_regex', language='go', suffixes=('.rs',))

    def test_tls_field_assignment_is_checked(self):
        result = self.scan('cfg.InsecureSkipVerify = true\ncfg.MinVersion = tls.VersionTLS10', '.go')
        self.assertEqual({f.rule_id for f in result.findings}, {'GO-TLS-NO-VERIFY', 'GO-TLS-LEGACY-VERSION'})

    def test_fast_format_filter_keeps_comment_separated_dynamic_arguments(self):
        for gap in (' ', '\n', '/* note */', '/* ** note ** */', '// note\n', '/* a */\n// b\n'):
            with self.subTest(gap=gap):
                source = 'printf' + gap + '(' + gap + 'userInput);'
                result = self.scan(source, '.cpp', 'CPP-FORMAT-STRING')
                self.assertTrue(result.complete)
                self.assertEqual(len(result.findings), 1)
        result = self.scan('fprintf(/* comma, semicolon; */ stream, input);', '.cpp', 'CPP-FORMAT-STRING')
        self.assertEqual(len(result.findings), 1)

    def test_scanf_checks_later_conversions_but_ignores_escaped_percent(self):
        for source, count in [('scanf("%d %s", &n, buffer);', 1),
                              ('scanf("%%s %31s", buffer);', 0),
                              ('scanf("%31s %[abc]", first, second);', 1)]:
            with self.subTest(source=source):
                result = self.scan(source, '.cpp', 'CPP-SCANF-UNBOUNDED')
                self.assertEqual(len(result.findings), count)

    def test_benchmark_validates_volume_and_planted_controls(self):
        from sourcehealth.sast.benchmark import benchmark_polyglot
        for hot in (False, True):
            with self.subTest(hot=hot):
                report = benchmark_polyglot(mib=4, repeat=1, hot=hot)
                self.assertTrue(report['runs'][0]['verified'])
                self.assertEqual(report['runs'][0]['bytes'], 4 * 1_048_576)
                self.assertEqual(report['runs'][0]['controls_found'], 5)


if __name__ == '__main__':
    unittest.main()
