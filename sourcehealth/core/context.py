"""Подготовленные факты одного запуска; сбор данных выполняется вне анализаторов."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sourcehealth.git.models import Commit

from .domain import DataAvailability, RepositoryRef, require_utc_aware


@dataclass(frozen=True)
class AnalysisContext:
    """None означает недоступную историю, пустой tuple — репозиторий без коммитов.

    metadata предназначена для уже собранных внешних данных (например SourceCraft).
    Анализаторы рассматривают контекст и вложенные данные как read-only.
    """

    repo_path: Path | None = None
    commits: tuple[Commit, ...] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    collection_errors: dict[str, str] = field(default_factory=dict)
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    repository: RepositoryRef | None = None
    sourcecraft_facts: dict[str, Any] = field(default_factory=dict)
    collection_statuses: dict[str, DataAvailability] = field(default_factory=dict)

    @property
    def workspace(self) -> Path | None:
        """repo_path сохранён для совместимости конструкторов локального CLI."""
        return self.repo_path

    def __post_init__(self) -> None:
        require_utc_aware(self.started_at)
        if self.repo_path is None and self.repository is None:
            raise ValueError("repository identity or local workspace is required")
