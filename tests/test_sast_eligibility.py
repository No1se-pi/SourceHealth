"""Регрессионные тесты на воспроизведение SAST eligibility gap и актуализацию explanation Security.

Воспроизводит:
- Case A: Находка Python AST при code_files_lexed == 0
- Case B: Находка Secret/Text при code_files_lexed == 0
- Актуализированное объяснение недоступности Security (без 'interface is not confirmed')
"""

import tempfile
import unittest
from pathlib import Path

from sourcehealth.analyzers.sast import SASTAnalyzerAdapter
from sourcehealth.core import AnalysisContext
from sourcehealth.core.domain import Category, DataAvailability
from sourcehealth.sast import SASTScanner
from sourcehealth.scoring.mvp import MVPPolicy
from tests.mvp_fixtures import mvp_context


class SASTEligibilityAndSecurityTests(unittest.TestCase):
    def test_reproduce_case_a_python_ast_finding_eligibility_gap(self):
        """Case A: Python AST находит уязвимость, но code_files_lexed == 0, из-за чего SAST игнорируется scoring policy."""
        with tempfile.TemporaryDirectory() as directory:
            app_py = Path(directory) / "app.py"
            app_py.write_text("import sys\neval(sys.argv[1])\n", encoding="utf-8")

            scanner = SASTScanner()
            scan_result = scanner.scan(directory)

            # 1. Проверяем метрики сканирования
            self.assertEqual(scan_result.python_files_parsed, 1)
            self.assertEqual(scan_result.code_files_lexed, 0)
            self.assertGreaterEqual(len(scan_result.findings), 1)
            self.assertTrue(any(f.engine == "python_call" for f in scan_result.findings))

            # 2. Адаптер формирует AnalyzerResult для пайплайна
            context = AnalysisContext(repo_path=Path(directory))
            sast_check = SASTAnalyzerAdapter(scanner).analyze(context)
            self.assertEqual(sast_check.metrics["code_files_lexed"], 0)
            self.assertEqual(sast_check.metrics["python_files_parsed"], 1)
            self.assertGreater(sum(sast_check.metrics["summary"].values()), 0)

            # 3. При оценке через MVPPolicy SAST не попадает в checks code_health
            policy = MVPPolicy()
            score_res = policy.evaluate({"sast": sast_check})
            code_health = score_res.categories["code_health"]

            # Из-за code_files_lexed == 0 компонент SAST не участвует в оценке
            self.assertNotIn("sast", [ref for ref in code_health.evidence_refs])
            self.assertIsNone(code_health.score)

    def test_reproduce_case_b_secret_text_only_finding_eligibility_gap(self):
        """Case B: Secret-сканер находит секрет в текстовом файле, но code_files_lexed == 0."""
        with tempfile.TemporaryDirectory() as directory:
            cfg = Path(directory) / "server.conf"
            cfg.write_text(
                "-----BEGIN RSA PRIVATE KEY-----\n"
                "MIIEowIBAAKCAQEA0\n"
                "-----END RSA PRIVATE KEY-----\n",
                encoding="utf-8",
            )

            scanner = SASTScanner()
            scan_result = scanner.scan(directory)

            # 1. Проверяем метрики сканирования
            self.assertEqual(scan_result.python_files_parsed, 0)
            self.assertEqual(scan_result.code_files_lexed, 0)
            self.assertGreaterEqual(len(scan_result.findings), 1)
            self.assertEqual(scan_result.findings[0].category, "secret")

            # 2. Адаптер
            context = AnalysisContext(repo_path=Path(directory))
            sast_check = SASTAnalyzerAdapter(scanner).analyze(context)
            self.assertEqual(sast_check.metrics["code_files_lexed"], 0)
            self.assertGreater(sast_check.metrics["summary"]["high"], 0)

            # 3. При оценке через MVPPolicy SAST игнорируется
            policy = MVPPolicy()
            score_res = policy.evaluate({"sast": sast_check})
            code_health = score_res.categories["code_health"]
            self.assertNotIn("sast", [ref for ref in code_health.evidence_refs])
            self.assertIsNone(code_health.score)

    def test_stale_security_explanation_removed_and_official_appsec_wording_present(self):
        """Проверка, что устаревшая формулировка 'interface is not confirmed' полностью удалена."""
        policy = MVPPolicy()
        score_res = policy.evaluate({})
        sec = score_res.categories["security"]

        self.assertIsNone(sec.score)
        self.assertEqual(sec.category, Category.SECURITY)
        self.assertEqual(sec.availability, DataAvailability.NO_DATA)

        # Не должно содержать устаревшей фразы
        self.assertNotIn("SourceCraft AppSec interface is not confirmed", sec.explanation)
        self.assertNotIn("interface is not confirmed", sec.explanation)

        # Должно содержать корректную формулировку
        self.assertIn("Official SourceCraft AppSec", sec.explanation)
        self.assertIn("local SAST не заменяет Security", sec.explanation)

    def test_ci_configured_without_runs_yields_score_40(self):
        """Проверка, что сконфигурированный CI без запусков дает ровно 40.0 баллов (не 50.0)."""
        from sourcehealth.analyzers.analytics import CIAnalyzer

        context = mvp_context()
        context.sourcecraft_facts["cicd"]["items"] = []
        context.metadata["ci_configured"] = True

        check = CIAnalyzer().analyze(context)
        self.assertTrue(check.metrics["configured"])
        self.assertEqual(check.metrics["runs_observed"], 0)
        self.assertEqual(check.availability, DataAvailability.AVAILABLE)

        policy = MVPPolicy()
        score_res = policy.evaluate({"cicd": check})
        ci_cat = score_res.categories["cicd"]

        self.assertEqual(ci_cat.score, 40.0)
        self.assertEqual(ci_cat.availability, DataAvailability.AVAILABLE)
        self.assertIn("конфигурация без запусков: 40", ci_cat.explanation)
