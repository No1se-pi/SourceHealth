"""Совместимая точка входа для раннего прототипа сбора Git-истории.

Раньше прототип мог работать через промежуточный лог-файл. Текущая версия
получает структурированные коммиты напрямую в память через ``GitCollector``.
"""

from pathlib import Path

from sourcehealth.git import Commit, GitCollector


def collect_commits(path: str | Path) -> list[Commit]:
    """Собрать структурированные коммиты из локального репозитория."""

    # Вся проверка пути, запуск Git и парсинг находятся в основном коллекторе.
    return GitCollector().collect(path)
