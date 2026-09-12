"""Адаптер существующего чистого анализатора Git; не собирает историю."""

from sourcehealth.core import AnalysisContext, AnalyzerResult
from sourcehealth.git import GitActivityAnalyzer


class GitActivityAnalyzerAdapter:
    name = "git_activity"

    def analyze(self, context: AnalysisContext) -> AnalyzerResult:
        if context.commits is None:
            return AnalyzerResult(
                analyzer=self.name, status="error",
                error=context.collection_errors.get("git", "git_history_unavailable"),
            )
        metrics = GitActivityAnalyzer().analyze(context.commits, now=context.started_at)
        return AnalyzerResult(analyzer=self.name, metrics=metrics.to_dict())
