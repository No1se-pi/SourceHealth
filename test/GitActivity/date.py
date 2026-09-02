"""Совместимая точка входа для раннего прототипа анализа активности.

Файл оставлен для старого кода, который импортирует ``commit_periodicity``.
Новая реализация делегирует вычисления основному ``GitActivityAnalyzer``.
"""

from datetime import datetime
from typing import Iterable

from sourcehealth.git import Commit, GitActivityAnalyzer, GitActivityMetrics


def commit_periodicity(
    commits: Iterable[Commit], *, now: datetime | None = None
) -> GitActivityMetrics:
    """Рассчитать временные метрики по результату ``GitCollector``."""

    # Не дублируем алгоритм в compatibility-слое: единственным источником
    # логики остаётся основной анализатор пакета.
    return GitActivityAnalyzer().analyze(commits, now=now)
