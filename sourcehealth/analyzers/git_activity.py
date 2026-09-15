"""Адаптер существующего чистого анализатора Git; не собирает историю."""

from sourcehealth.core import AnalysisContext, AnalyzerResult
from sourcehealth.core.domain import DataAvailability
from sourcehealth.git import GitActivityAnalyzer


class GitActivityAnalyzerAdapter:
    name = "git_activity"

    def analyze(self, context: AnalysisContext) -> AnalyzerResult:
        if context.commits is None:
            return AnalyzerResult(
                analyzer=self.name, status="error",
                error=context.collection_errors.get("git", "git_history_unavailable"),
                availability=DataAvailability.NO_DATA, category="activity", source="git",
            )
        metrics = GitActivityAnalyzer().analyze(context.commits, now=context.started_at)
        return AnalyzerResult(analyzer=self.name, metrics=metrics.to_dict(), category="activity", source="git")
