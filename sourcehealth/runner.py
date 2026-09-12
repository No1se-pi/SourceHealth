"""Последовательное выполнение независимых анализаторов с общим контекстом."""

from collections.abc import Callable, Iterable
from datetime import UTC, datetime
from pathlib import Path

from sourcehealth.core import AnalysisContext, AnalysisReport, Analyzer, AnalyzerResult
from sourcehealth.git import GitCollectionError, GitCollector


def prepare_context(repo_path: Path) -> AnalysisContext:
    """Собрать историю один раз. Ошибка Git не мешает анализаторам файлов."""
    started_at = datetime.now(UTC)
    try:
        commits = tuple(GitCollector().collect(repo_path))
    except (GitCollectionError, ValueError):
        # Git stderr может содержать секреты и недоверенные сообщения репозитория.
        return AnalysisContext(repo_path, collection_errors={"git": "git_collection_failed"},
                               started_at=started_at)
    return AnalysisContext(repo_path, commits=commits, started_at=started_at)


class AnalysisRunner:
    """Регистрация — обычный список; context_factory заменяет этап сбора фактов.

    Для SAST-only можно передать AnalysisContext как factory без запуска Git.
    Внешний коллектор SourceCraft добавляется через собственную factory.
    """

    def __init__(self, analyzers: Iterable[Analyzer], *,
                 context_factory: Callable[[Path], AnalysisContext] = prepare_context) -> None:
        self.analyzers = tuple(analyzers)
        names = [analyzer.name for analyzer in self.analyzers]
        if any(not isinstance(name, str) or not name for name in names):
            raise ValueError("analyzer names must be nonempty strings")
        if len(set(names)) != len(names):
            raise ValueError("analyzer names must be unique")
        self.context_factory = context_factory

    def analyze(self, repo_path: str | Path) -> AnalysisReport:
        path = Path(repo_path).expanduser().resolve()
        if not path.is_dir():
            raise ValueError("repository must be an existing directory")
        context = self.context_factory(path)
        checks: dict[str, AnalyzerResult] = {}
        for analyzer in self.analyzers:
            try:
                result = analyzer.analyze(context)
                if not isinstance(result, AnalyzerResult) or result.analyzer != analyzer.name:
                    raise ValueError("analyzer returned an invalid result")
                # Проверяем и копируем результат до следующего анализатора:
                # ошибка сериализации тоже не должна разрушать весь отчёт.
                result = AnalyzerResult(**result.to_dict())
            except Exception:
                # Не перехватываем KeyboardInterrupt/SystemExit и не выводим
                # произвольный текст исключения в публичный JSON.
                result = AnalyzerResult(analyzer.name, status="error", error="analyzer_failed")
            checks[analyzer.name] = result
        return AnalysisReport(repository={"path": str(path)}, started_at=context.started_at,
                              completed_at=datetime.now(UTC), checks=checks)
