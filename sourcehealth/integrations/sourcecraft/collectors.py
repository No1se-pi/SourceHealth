"""Коллекторы собирают факты, не назначают оценки и не сохраняют raw payload."""

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol

from sourcehealth.core.domain import DataAvailability, RepositoryRef

from .appsec import SourceCraftAppSecClient
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
    name = "appsec"

    def __init__(self, client: SourceCraftAppSecClient | None) -> None:
        self.client = client

    def collect(self, repository: RepositoryRef, repository_id: str | None = None) -> CollectedFacts:
        if self.client is None:
            return CollectedFacts("sourcecraft_appsec", DataAvailability.NO_DATA,
                                  error="appsec_credential_unavailable")
        if not isinstance(repository_id, str) or not repository_id:
            return CollectedFacts("sourcecraft_appsec", DataAvailability.NO_DATA,
                                  error="appsec_repository_id_unavailable")
        try:
            summary = self.client.get("/v1/scans/latest", params={"gitRepo": repository_id})
            scan_uuid = summary.get("uuid")
            if not isinstance(scan_uuid, str) or not re.fullmatch(r"[A-Za-z0-9-]{1,128}", scan_uuid):
                raise SourceCraftError("invalid_response")
            details = self.client.get(f"/v1/scans/{scan_uuid}", params={"gitRepo": repository_id})
            if details.get("status") != "FINISHED":
                return CollectedFacts("sourcecraft_appsec", DataAvailability.PARTIAL,
                                      {"complete": False}, error="appsec_scan_not_finished")
            counts = {}
            for normalized, official in (("critical", "CRITICAL"), ("high", "HIGH"),
                                         ("medium", "MEDIUM"), ("low", "LOW")):
                count, seen = 0, set()
                for row in self.client.iter_defect_groups(repository_id, scan_uuid, official):
                    # Validate only identity, then release the raw row without retaining sensitive fields.
                    group_uuid = row.get("uuid")
                    if not isinstance(group_uuid, str):
                        raise SourceCraftError("invalid_response")
                    if group_uuid in seen:
                        raise SourceCraftError("invalid_pagination")
                    seen.add(group_uuid)
                    count += 1
                counts[normalized] = count
            facts = {"complete": True, "scan_uuid": scan_uuid, "open_by_severity": counts,
                     "total_open": sum(counts.values())}
            return CollectedFacts("sourcecraft_appsec", DataAvailability.AVAILABLE, facts, schema_version="2")
        except SourceCraftError as error:
            if error.code in {"invalid_response", "invalid_pagination", "page_limit", "response_limit"}:
                return CollectedFacts("sourcecraft_appsec", DataAvailability.PARTIAL,
                                      {"complete": False}, error=f"appsec_{error.code}")
            availability = (DataAvailability.NO_DATA if error.code in {"authentication_required", "access_denied", "not_found"}
                            else DataAvailability.SOURCE_UNAVAILABLE)
            return CollectedFacts("sourcecraft_appsec", availability, error=f"appsec_{error.code}")
