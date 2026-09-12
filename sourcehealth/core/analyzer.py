"""Минимальный структурный контракт: наследование и plugin framework не нужны."""

from typing import Protocol

from .context import AnalysisContext
from .result import AnalyzerResult


class Analyzer(Protocol):
    name: str

    def analyze(self, context: AnalysisContext) -> AnalyzerResult:
        """Проанализировать факты и вернуть результат без итогового Health Score."""
        ...
