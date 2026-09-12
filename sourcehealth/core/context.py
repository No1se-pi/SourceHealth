"""Подготовленные факты одного запуска; сбор данных выполняется вне анализаторов."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sourcehealth.git.models import Commit


@dataclass(frozen=True)
class AnalysisContext:
    """None означает недоступную историю, пустой tuple — репозиторий без коммитов.

    metadata предназначена для уже собранных внешних данных (например SourceCraft).
    Анализаторы рассматривают контекст и вложенные данные как read-only.
    """

    repo_path: Path
    commits: tuple[Commit, ...] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    collection_errors: dict[str, str] = field(default_factory=dict)
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
