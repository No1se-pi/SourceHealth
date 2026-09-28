"""Дискриминирующие регрессионные тесты на воспроизведение SAST eligibility gap.

Демонстрирует для Case A (Python AST) и Case B (Secret/Text):
1. technical debt в одиночку формирует детерминированный базовый балл Code Health (100.0);
2. добавление SAST-результата с находками, но code_files_lexed == 0 НЕ меняет итоговый балл Code Health (100.0 == 100.0);
3. парный контроль с теми же метриками и находками, но code_files_lexed > 0 МЕНЯЕТ (понижает) балл Code Health (98.0 / 94.0 < 100.0).

Это доказывает, что именно предикат code_files_lexed > 0 исключает компонент SAST из скоринга.
"""

import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from sourcehealth.analyzers.sast import SASTAnalyzerAdapter
from sourcehealth.core import AnalysisContext, AnalyzerResult
from sourcehealth.core.domain import Category, DataAvailability, Evidence
from sourcehealth.sast import SASTScanner
from sourcehealth.scoring.mvp import MVPPolicy
from tests.mvp_fixtures import mvp_context


def _clean_technical_debt_check() -> AnalyzerResult:
    """Формирует воспроизводимый результат анализа технического долга с весом 60 (≥50)."""
    return AnalyzerResult(
        "technical_debt",
        status="ok",
        metrics={
            "code_files": 10,
            "marker_density": 0.0,
            "large_files": 0,
            "age_complete": True,
            "oldest_marker_age_days": 0,
        },
        findings=[],
        evidence=(
            Evidence(
                id="technical_debt:snapshot",
                source="technical_debt",
                type="snapshot",
                reference="local",
                summary="Clean technical debt metrics",
            ),
        ),
        category="code_health",
        source="sourcehealth_local",
        availability=DataAvailability.AVAILABLE,
    )


class SASTEligibilityAndSecurityTests(unittest.TestCase):
    def test_reproduce_case_a_python_ast_finding_eligibility_gap(self):
        """Case A: Python AST находит уязвимость, но code_files_lexed == 0, из-за чего SAST игнорируется scoring policy."""
        debt_check = _clean_technical_debt_check()
        policy = MVPPolicy()

        # 1. Technical debt в одиночку формирует детерминированный базовый балл Code Health
        base_res = policy.evaluate({"technical_debt": debt_check})
        base_score = base_res.categories["code_health"].score
        self.assertEqual(base_score, 100.0)

        with tempfile.TemporaryDirectory() as directory:
            app_py = Path(directory) / "app.py"
            app_py.write_text("import sys\neval(sys.argv[1])\n", encoding="utf-8")

            scanner = SASTScanner()
            scan_result = scanner.scan(directory)

            # Проверяем метрики сканирования
            self.assertEqual(scan_result.python_files_parsed, 1)
            self.assertEqual(scan_result.code_files_lexed, 0)
            self.assertGreaterEqual(len(scan_result.findings), 1)
            self.assertTrue(any(f.engine == "python_call" for f in scan_result.findings))

            # Адаптер формирует AnalyzerResult для пайплайна
            context = AnalysisContext(repo_path=Path(directory))
            sast_check = SASTAnalyzerAdapter(scanner).analyze(context)
            self.assertEqual(sast_check.metrics["code_files_lexed"], 0)
            self.assertEqual(sast_check.metrics["python_files_parsed"], 1)
            self.assertGreater(sast_check.metrics["summary"]["medium"], 0)

            # Findings remain negative evidence even when this scanner path has no clean-scan baseline.
            res_actual = policy.evaluate({"technical_debt": debt_check, "sast": sast_check})
            actual_score = res_actual.categories["code_health"].score
            self.assertEqual(actual_score, 95.0)

            # 3. Парный контроль с теми же метриками/находками, но code_files_lexed == 1 МЕНЯЕТ (понижает) балл
            sast_control = deepcopy(sast_check)
            sast_control.metrics["code_files_lexed"] = 1
            res_control = policy.evaluate({"technical_debt": debt_check, "sast": sast_control})
            control_score = res_control.categories["code_health"].score

            self.assertGreater(control_score, actual_score)
            self.assertLess(control_score, base_score)
            # Взвешенный расчет: (60 * 100.0 + 40 * 95.0) / 100 = 98.0
            self.assertEqual(control_score, 98.0)

    def test_reproduce_case_b_secret_text_only_finding_eligibility_gap(self):
        """Case B: Secret-сканер находит секрет в текстовом файле, но code_files_lexed == 0."""
        debt_check = _clean_technical_debt_check()
        policy = MVPPolicy()

        # 1. Базовый балл без SAST
        base_res = policy.evaluate({"technical_debt": debt_check})
        base_score = base_res.categories["code_health"].score
        self.assertEqual(base_score, 100.0)

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

            self.assertEqual(scan_result.python_files_parsed, 0)
            self.assertEqual(scan_result.code_files_lexed, 0)
            self.assertGreaterEqual(len(scan_result.findings), 1)
            self.assertEqual(scan_result.findings[0].category, "secret")

            context = AnalysisContext(repo_path=Path(directory))
            sast_check = SASTAnalyzerAdapter(scanner).analyze(context)
            self.assertEqual(sast_check.metrics["code_files_lexed"], 0)
            self.assertGreater(sast_check.metrics["summary"]["high"], 0)

            # A detected secret must not disappear merely because no lexer-based files were counted.
            res_actual = policy.evaluate({"technical_debt": debt_check, "sast": sast_check})
            actual_score = res_actual.categories["code_health"].score
            self.assertEqual(actual_score, 85.0)

            # 3. Парный контроль с code_files_lexed == 1 понижает балл Code Health
            sast_control = deepcopy(sast_check)
            sast_control.metrics["code_files_lexed"] = 1
            res_control = policy.evaluate({"technical_debt": debt_check, "sast": sast_control})
            control_score = res_control.categories["code_health"].score

            self.assertGreater(control_score, actual_score)
            self.assertLess(control_score, base_score)
            # Взвешенный расчет: (60 * 100.0 + 40 * 85.0) / 100 = 94.0
            self.assertEqual(control_score, 94.0)

    def test_partial_sast_findings_reduce_code_health_without_clean_scan_credit(self):
        debt_check = _clean_technical_debt_check()
        sast_check = AnalyzerResult(
            "sast", status="partial", category="code_health", source="sourcehealth_local",
            availability=DataAvailability.PARTIAL,
            metrics={"code_files_lexed": 100, "summary": {"high": 2, "medium": 3, "low": 4}},
            evidence=(Evidence(id="sast:snapshot", source="sourcehealth_local", type="static_analysis",
                               reference="local", summary="Observed partial SAST findings"),),
        )

        score = MVPPolicy().evaluate({"technical_debt": debt_check, "sast": sast_check}).categories["code_health"]

        self.assertEqual(score.score, 51.0)
        self.assertEqual(score.availability, DataAvailability.PARTIAL)
        self.assertIn("PARTIAL SAST", score.explanation)
        self.assertIn("sast:snapshot", score.evidence_refs)

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
