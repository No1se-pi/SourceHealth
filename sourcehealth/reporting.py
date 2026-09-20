"""Совместимость старого JSON 1.0 и SARIF с единым AnalysisReport 2.0."""

from dataclasses import replace
from pathlib import Path
from typing import Any

from sourcehealth.analyzers import GitActivityAnalyzerAdapter, SASTAnalyzerAdapter
from sourcehealth.core import AnalysisContext, AnalysisReport
from sourcehealth.runner import AnalysisRunner, prepare_context
from sourcehealth.sast import SASTScanner, ScanResult


def analyze_repository(path: str | Path, scanner: SASTScanner, *, with_git: bool = True, with_mvp: bool = False) -> AnalysisReport:
    analyzers = [SASTAnalyzerAdapter(scanner)]
    if with_git:
        analyzers.append(GitActivityAnalyzerAdapter())
    factory = prepare_context if with_git else AnalysisContext
    if with_mvp:
        from sourcehealth.analyzers.snapshot import DocumentationAnalyzer, TechnicalDebtAnalyzer
        from sourcehealth.snapshot import SnapshotCollector

        analyzers.extend([DocumentationAnalyzer(), TechnicalDebtAnalyzer()])

        def factory(path):
            context = prepare_context(path) if with_git else AnalysisContext(path)
            try:
                snapshot = SnapshotCollector().collect(path, context.started_at)
            except Exception:
                snapshot = None  # No Git stderr or host paths in public failure output.
            return replace(context, metadata={"snapshot": snapshot})
    runner = AnalysisRunner(analyzers, context_factory=factory)
    return runner.analyze(path)


def to_legacy_report(report: AnalysisReport) -> dict[str, Any]:
    """Сохранить плоские поля SAST для прежних CLI, Docker и SARIF consumers."""
    checks = {}
    for name, result in report.checks.items():
        if name == "sast":
            # Даже ошибка сканера должна давать корректный неполный SARIF.
            scan = ScanResult(complete=False).to_dict()
            scan.update(result.metadata)
            scan.update(result.metrics)
            scan.update(findings=result.findings, complete=result.status == "ok")
            if result.error:
                scan["error"] = result.error
            checks[name] = scan
        elif name == "git_activity":
            checks[name] = {"status": result.status}
            if result.error:
                checks[name]["error"] = result.error
            else:
                checks[name]["metrics"] = result.metrics
        else:
            checks[name] = result.to_dict()
    return {"schema_version": "1.0", "complete": report.complete, "checks": checks}


def build_report(path: str | Path, scanner: SASTScanner, *, with_git: bool = False) -> dict[str, Any]:
    """Старый публичный helper; orchestration теперь находится в AnalysisRunner."""
    return to_legacy_report(analyze_repository(path, scanner, with_git=with_git))
