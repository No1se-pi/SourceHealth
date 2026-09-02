"""Публичный интерфейс пакета SourceHealth.

На текущем этапе пакет предоставляет компоненты для сбора истории Git
и расчёта временных метрик активности репозитория.
"""

# Переэкспортируем основные сущности верхнего уровня, чтобы пользователю
# не приходилось знать внутреннюю структуру пакета sourcehealth.git.
from sourcehealth.git import Commit, GitActivityAnalyzer, GitActivityMetrics, GitCollector

__all__ = [
    "Commit",
    "GitActivityAnalyzer",
    "GitActivityMetrics",
    "GitCollector",
]
