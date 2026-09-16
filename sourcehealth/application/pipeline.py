"""Объединить platform и sandbox перед scoring, изолируя ошибки runtime."""

from datetime import UTC, datetime

from sourcehealth.analyzers.platform import RepositoryMetadataAnalyzer, SourceCraftSecurityAnalyzer
from sourcehealth.core import AnalysisContext, AnalysisReport
from sourcehealth.runner import AnalysisRunner
from sourcehealth.runtime import AnalysisRuntime
from sourcehealth.runtime_results import CLASSIFICATION, normalize_runtime_report, unavailable


def analyze_context(context: AnalysisContext, *, include_code: bool = False,
                    runtime: AnalysisRuntime | None = None) -> AnalysisReport:
    """Один вызов runtime для Git и SAST, без повторного clone ради анализатора."""
    report = AnalysisRunner([RepositoryMetadataAnalyzer(), SourceCraftSecurityAnalyzer()]).analyze_context(context)
    if include_code:
        if runtime is None:
            checks = {name: unavailable(name, "runtime_not_configured") for name in CLASSIFICATION}
        else:
            try:
                checks = normalize_runtime_report(runtime.analyze(context.repository))
            except Exception:
                # Exceptions may include Git stderr/credentials. Persist only a fixed code.
                checks = {name: unavailable(name, "runtime_failed") for name in CLASSIFICATION}
        report.checks.update(checks)
    report.completed_at = datetime.now(UTC)
    return report
