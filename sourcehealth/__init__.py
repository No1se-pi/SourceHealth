"""Публичный интерфейс пакета SourceHealth.

Git API сохранён на верхнем уровне. Общий pipeline находится в core/runner,
адаптеры — в analyzers, самостоятельный сканер — в sast.
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
