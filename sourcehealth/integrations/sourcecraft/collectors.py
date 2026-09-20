"""Коллекторы собирают факты, не назначают оценки и не сохраняют raw payload."""

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol

from sourcehealth.core.domain import DataAvailability, RepositoryRef

from .client import SourceCraftClient, SourceCraftError


@dataclass(frozen=True)
class CollectedFacts:
    source: str
    availability: DataAvailability
    facts: dict[str, Any] = field(default_factory=dict)
    collected_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    error: str | None = None
    schema_version: str = "1"


class Collector(Protocol):
    name: str

    def collect(self, repository: RepositoryRef) -> CollectedFacts: ...


class RepositoryCollector:
    name = "repository_metadata"

    def __init__(self, client: SourceCraftClient) -> None:
        self.client = client

    def collect(self, repository: RepositoryRef) -> CollectedFacts:
        try:
            raw = self.client.repository(repository.organization_slug, repository.repository_slug)
            if raw.get("visibility") != "public":
                return CollectedFacts("sourcecraft", DataAvailability.NO_DATA, error="public_repository_required")
            if not isinstance(raw.get("id"), str) or not isinstance(raw.get("slug"), str):
                raise SourceCraftError("invalid_response")
            if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", raw["id"]) or raw["slug"] != repository.repository_slug:
                raise SourceCraftError("invalid_response")
            if "default_branch" in raw and (not isinstance(raw["default_branch"], str) or
                    not re.fullmatch(r"[A-Za-z0-9_./-]{1,255}", raw["default_branch"])):
                raise SourceCraftError("invalid_response")
            if "is_empty" in raw and type(raw["is_empty"]) is not bool:
                raise SourceCraftError("invalid_response")
            # Allowlist: description, clone credentials and arbitrary links never reach persistence.
            facts = {k: raw[k] for k in ("id", "slug", "default_branch", "visibility", "is_empty") if k in raw}
            language = raw.get("language")
            if isinstance(language, dict) and isinstance(language.get("name"), str):
                if re.fullmatch(r"[A-Za-z0-9+# ._-]{1,64}", language["name"]):
                    facts["language"] = language["name"]
            facts["likes"] = repository_likes(raw.get("rating"))
            return CollectedFacts("sourcecraft", DataAvailability.AVAILABLE, facts)
        except SourceCraftError as error:
            return CollectedFacts("sourcecraft", DataAvailability.SOURCE_UNAVAILABLE, error=error.code)


def repository_likes(rating: Any) -> int | None:
    """Like — только positive_low; неизвестный/невалидный счётчик не становится нулём.

    API отдаёт sparse uint64 counters. Хранилище использует signed int32:
    переполнение оставляем неизвестным, не обрезаем и не роняем весь import.
    """
    if not isinstance(rating, dict) or not isinstance(rating.get("reaction_counts"), list):
        return None
    likes = None
    for reaction in rating["reaction_counts"]:
        if not isinstance(reaction, dict):
            return None
        if reaction.get("type") != "positive_low":
            continue
        value = reaction.get("count")
        if likes is not None or not isinstance(value, str) or not re.fullmatch(r"[0-9]{1,20}", value):
            return None
        likes = int(value)
        if likes > 2_147_483_647:
            return None
    return 0 if likes is None else likes


class AppSecCollector:
    """Boundary до подтверждения официального интерфейса выгрузки findings.

    NO_DATA честно означает отсутствие подключённого источника. Эндпоинт secrets
    хранит CI-секреты и НЕ является API secret-scanning: к нему не обращаемся.
    """

    name = "appsec"

    def collect(self, repository: RepositoryRef) -> CollectedFacts:
        return CollectedFacts("sourcecraft_appsec", DataAvailability.NO_DATA, error="appsec_interface_unconfirmed")
