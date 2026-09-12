"""Инструменты SourceHealth для сбора и анализа истории Git.

Модуль объединяет публичные классы подсистемы Git:
- ``GitCollector`` получает структурированную историю коммитов;
- ``Commit`` описывает один нормализованный коммит;
- ``GitActivityAnalyzer`` рассчитывает временные метрики;
- ``GitActivityMetrics`` хранит результат анализа;
- ``GitCollectionError`` используется для ошибок взаимодействия с Git.
"""

from sourcehealth.git.activity import GitActivityAnalyzer, GitActivityMetrics
from sourcehealth.git.collector import GitCollectionError, GitCollector
from sourcehealth.git.models import Commit

# Явно фиксируем публичный API модуля. Это упрощает импорт и показывает,
# какие классы считаются стабильной частью подсистемы Git.
__all__ = [
    "Commit",
    "GitActivityAnalyzer",
    "GitActivityMetrics",
    "GitCollectionError",
    "GitCollector",
]
