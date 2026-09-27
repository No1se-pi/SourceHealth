"""Коллекторы собирают факты, не назначают оценки и не сохраняют raw payload."""

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol

from sourcehealth.core.domain import DataAvailability, RepositoryRef

from .appsec import SourceCraftAppSecClient
from .client import SourceCraftClient, SourceCraftError
from .validation import normalize_repository_likes, normalize_repository_metadata


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
            metadata = normalize_repository_metadata(
                raw, expected_org=repository.organization_slug,
                expected_slug=repository.repository_slug, require_public=True)
            facts = {"id": metadata.sourcecraft_id, "slug": metadata.repository_slug,
                     "visibility": metadata.visibility, "default_branch": metadata.default_branch,
                     "is_empty": metadata.is_empty, "likes": metadata.likes}
            if metadata.language is not None:
                facts["language"] = metadata.language
            return CollectedFacts("sourcecraft", DataAvailability.AVAILABLE, facts)
        except SourceCraftError as error:
            availability = (DataAvailability.NO_DATA if error.code in {
                "not_found", "access_denied", "public_repository_required"}
                            else DataAvailability.SOURCE_UNAVAILABLE)
            return CollectedFacts("sourcecraft", availability, error=error.code)


def repository_likes(rating: Any) -> int | None:
    """Backward-compatible entry point for the shared repository rating normalizer."""
    return normalize_repository_likes(rating)


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
