"""Объединить platform и sandbox перед scoring, изолируя ошибки runtime."""

from dataclasses import replace
from datetime import UTC, datetime

from sourcehealth.analyzers.analytics import CIAnalyzer, IssuesAnalyzer, PlatformActivityAnalyzer
from sourcehealth.analyzers.platform import RepositoryMetadataAnalyzer, SourceCraftSecurityAnalyzer
from sourcehealth.core import AnalysisContext, AnalysisReport
from sourcehealth.core.domain import Evidence
from sourcehealth.runner import AnalysisRunner
from sourcehealth.runtime import AnalysisRuntime
from sourcehealth.runtime_results import CLASSIFICATION, MVP_CLASSIFICATION, normalize_runtime_report, unavailable


def analyze_context(context: AnalysisContext, *, include_code: bool = False,
                    runtime: AnalysisRuntime | None = None, with_mvp: bool = False) -> AnalysisReport:
    """Один вызов runtime для Git и SAST, без повторного clone ради анализатора."""
    report = AnalysisRunner([RepositoryMetadataAnalyzer(), SourceCraftSecurityAnalyzer()]).analyze_context(context)
    if include_code:
        names = MVP_CLASSIFICATION if with_mvp else CLASSIFICATION
        if runtime is None:
            checks = {name: unavailable(name, "runtime_not_configured") for name in names}
        else:
            try:
                checks = normalize_runtime_report(runtime.analyze(context.repository), with_mvp=with_mvp)
            except Exception:
                # Exceptions may include Git stderr/credentials. Persist only a fixed code.
                checks = {name: unavailable(name, "runtime_failed") for name in names}
        report.checks.update(checks)
    if with_mvp:
        doc = report.checks.get("documentation")
        sha = doc.metadata.get("head_sha") if doc else None
        context = replace(context, metadata={**context.metadata, "ci_configured": doc.metadata.get("ci_configured") if doc else None})
        report.checks.update(AnalysisRunner([IssuesAnalyzer(), CIAnalyzer(), PlatformActivityAnalyzer()]).analyze_context(context).checks)
        for name in ("git_activity", "sast"):
            check = report.checks.get(name)
            if check and check.status in {"ok", "partial"}:
                check.evidence = [Evidence(id=f"{name}:snapshot", source=check.source, type="static_analysis",
                                          reference=sha or context.repository.id, summary=f"Сохранённые метрики {name}; без source snippets.",
                                          timestamp=context.started_at.isoformat())]
        if sha:
            report.repository["head_sha"] = sha
            ci = report.checks["cicd"]
            if ci.metrics.get("configured") is not None:
                ci.evidence.append(Evidence(id="cicd:snapshot", source="git_snapshot", type="ci_configuration",
                                            reference=sha, summary="Проверено наличие .sourcecraft/ci.yaml в snapshot.",
                                            location=".sourcecraft/ci.yaml"))
    report.completed_at = datetime.now(UTC)
    return report
