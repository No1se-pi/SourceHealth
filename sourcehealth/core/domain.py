"""Стабильные понятия предметной области без HTTP, БД и runtime-зависимостей."""

import re
from dataclasses import asdict, dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any
from urllib.parse import urlsplit
from uuid import UUID, uuid4


def sourcecraft_clone_url(value: str) -> str:
    """Канонизация identity без сетевых запросов и зависимости от runtime."""
    parsed = urlsplit(value)
    if (parsed.scheme != "https" or parsed.hostname not in {"sourcecraft.dev", "git.sourcecraft.dev"}
            or parsed.port is not None or parsed.password is not None
            or parsed.username not in {None, "git"} or parsed.query or parsed.fragment):
        raise ValueError("Expected a public SourceCraft HTTPS repository URL")
    path = parsed.path.rstrip("/").removesuffix(".git")
    if not re.fullmatch(r"/[A-Za-z0-9][A-Za-z0-9_-]{0,99}/[A-Za-z0-9][A-Za-z0-9_.-]{0,99}", path):
        raise ValueError("Expected /organization/repository")
    return f"https://git.sourcecraft.dev{path}.git"


class DataAvailability(StrEnum):
    """Доступность фактов, независимая от качества проверяемого проекта."""

    AVAILABLE = "available"
    NOT_CONFIGURED = "not_configured"
    NO_DATA = "no_data"
    SOURCE_UNAVAILABLE = "source_unavailable"
    PARTIAL = "partial"
    ERROR = "error"
    NOT_APPLICABLE = "not_applicable"


class Category(StrEnum):
    DOCUMENTATION = "documentation"
    CICD = "cicd"
    SECURITY = "security"
    ACTIVITY = "activity"
    ISSUES = "issues"
    CODE_HEALTH = "code_health"


@dataclass(frozen=True)
class RepositoryRef:
    """ID принадлежит сервису; rename платформы не меняет внутренний ID."""

    id: str
    organization_slug: str
    repository_slug: str
    canonical_url: str
    sourcecraft_id: str | None = None
    visibility: str = "unknown"
    default_branch: str | None = None
    head_sha: str | None = None

    def __post_init__(self) -> None:
        UUID(self.id)
        normalized = sourcecraft_clone_url(self.canonical_url)
        expected = f"https://git.sourcecraft.dev/{self.organization_slug}/{self.repository_slug}.git"
        if normalized != expected or self.canonical_url != (
            f"https://sourcecraft.dev/{self.organization_slug}/{self.repository_slug}"
        ):
            raise ValueError("repository identity does not match canonical URL")
        if self.visibility not in {"public", "private", "unknown"}:
            raise ValueError("invalid visibility")

    @classmethod
    def from_url(cls, url: str, **kwargs: Any) -> "RepositoryRef":
        normalized = sourcecraft_clone_url(url)
        organization, repository = normalized.removeprefix("https://git.sourcecraft.dev/")[:-4].split("/")
        return cls(id=kwargs.pop("id", str(uuid4())), organization_slug=organization,
                   repository_slug=repository, canonical_url=f"https://sourcecraft.dev/{organization}/{repository}",
                   **kwargs)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Evidence:
    """Ссылка на факт. summary содержит объяснение, никогда исходник/значение секрета."""

    id: str
    source: str
    type: str
    reference: str
    summary: str
    url: str | None = None
    location: str | None = None
    timestamp: str | None = None


@dataclass(frozen=True)
class Recommendation:
    id: str
    category: Category
    title: str
    description: str
    priority: int
    evidence_refs: tuple[str, ...]
    suggested_action: str
    expected_impact: str | None = None

    def __post_init__(self) -> None:
        if self.priority not in (1, 2, 3) or not self.evidence_refs:
            raise ValueError("recommendation requires priority 1..3 and evidence")


class RunStatus(StrEnum):
    QUEUED = "queued"
    COLLECTING = "collecting"
    ANALYZING = "analyzing"
    SCORING = "scoring"
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"


ACTIVE_STATUSES = ("queued", "collecting", "analyzing", "scoring")
TERMINAL_STATUSES = ("completed", "partial", "failed")


def validate_transition(current: str, target: str) -> None:
    """Повторная доставка задания не позволяет переписать завершённый запуск."""
    allowed = {
        "queued": {"collecting", "failed"},
        "collecting": {"analyzing", "failed"},
        "analyzing": {"scoring", "failed"},
        "scoring": {"completed", "partial", "failed"},
    }
    if target not in allowed.get(current, set()):
        raise ValueError("invalid analysis transition")


def require_utc_aware(value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware")
