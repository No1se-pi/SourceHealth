"""Общие модели данных подсистемы анализа Git."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class Commit:
    """Нормализованное представление одного Git-коммита.

    Объект отделяет сырой вывод ``git log`` от анализаторов. Благодаря этому
    любой будущий анализатор SourceHealth может работать с одинаковой
    структурой данных и не запускать Git самостоятельно.

    Attributes:
        hash: Полный SHA-хеш коммита.
        author_name: Имя автора, сохранённое в Git.
        author_email: Email автора, сохранённый в Git.
        datetime: Дата и время автора с обязательной информацией о часовом поясе.
        message: Полное сообщение коммита, включая многострочное тело.
    """

    hash: str
    author_name: str
    author_email: str
    datetime: datetime
    message: str

    def __post_init__(self) -> None:
        """Проверить, что время коммита однозначно определено.

        Наивный ``datetime`` без часового пояса нельзя безопасно сравнивать
        с коммитами из других часовых поясов. Поэтому такие значения
        отклоняются сразу при создании модели.
        """

        if self.datetime.tzinfo is None or self.datetime.utcoffset() is None:
            raise ValueError("Commit datetime must be timezone-aware")

    def to_dict(self) -> dict[str, Any]:
        """Вернуть JSON-совместимое представление коммита.

        ``datetime`` преобразуется в строку ISO 8601, поскольку стандартный
        JSON-сериализатор Python не умеет сериализовать ``datetime`` напрямую.
        """

        return {
            "hash": self.hash,
            "author_name": self.author_name,
            "author_email": self.author_email,
            "datetime": self.datetime.isoformat(),
            "message": self.message,
        }
