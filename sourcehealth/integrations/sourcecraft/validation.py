"""Allowlisted normalization shared by every SourceCraft repository consumer."""

import re
from dataclasses import dataclass
from typing import Any

from .client import SourceCraftError


def _identifier(value: Any) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", value):
        raise SourceCraftError("invalid_response")
    return value


def normalize_default_branch(value: Any) -> str | None:
    """Normalize an empty-repository branch while preserving valid Unicode Git refs."""
    if value in (None, ""):
        return None
    if (not isinstance(value, str) or not 1 <= len(value) <= 255
            or any(ord(char) < 32 or ord(char) == 127 for char in value)):
        raise SourceCraftError("invalid_response")
    return value


def normalize_repository_likes(value: Any) -> int | None:
    if not isinstance(value, dict) or not isinstance(value.get("reaction_counts"), list):
        return None
    likes = None
    for reaction in value["reaction_counts"]:
        if not isinstance(reaction, dict):
            return None
        if reaction.get("type") != "positive_low":
            continue
        count = reaction.get("count")
        if likes is not None or not isinstance(count, str) or not re.fullmatch(r"[0-9]{1,20}", count):
            return None
        likes = int(count)
        if likes > 2_147_483_647:
            return None
    return 0 if likes is None else likes


@dataclass(frozen=True)
class RepositoryMetadata:
    sourcecraft_id: str
    organization_slug: str
    repository_slug: str
    visibility: str
    default_branch: str | None
    is_empty: bool | None
    language: str | None
    likes: int | None

    @property
    def canonical_url(self) -> str:
        return f"https://sourcecraft.dev/{self.organization_slug}/{self.repository_slug}"


def normalize_repository_metadata(raw: Any, *, expected_org: str | None = None,
                                  expected_slug: str | None = None,
                                  require_public: bool = False) -> RepositoryMetadata:
    """Return only safe repository identity and display fields from an untrusted DTO."""
    if not isinstance(raw, dict):
        raise SourceCraftError("invalid_response")
    sourcecraft_id = _identifier(raw.get("id"))
    repository_slug = _identifier(raw.get("slug"))
    organization = raw.get("organization")
    raw_org = organization.get("slug") if isinstance(organization, dict) else None
    organization_slug = _identifier(raw_org if raw_org is not None else expected_org)
    if expected_org is not None and organization_slug != expected_org:
        raise SourceCraftError("invalid_response")
    if expected_slug is not None and repository_slug != expected_slug:
        raise SourceCraftError("invalid_response")
    visibility = raw.get("visibility")
    if visibility not in {"public", "private", "internal"}:
        raise SourceCraftError("invalid_response")
    if require_public and visibility != "public":
        raise SourceCraftError("public_repository_required")
    is_empty = raw.get("is_empty")
    if is_empty is not None and type(is_empty) is not bool:
        raise SourceCraftError("invalid_response")
    language = raw.get("language")
    language = language.get("name") if isinstance(language, dict) else None
    if language is not None and (not isinstance(language, str) or not 1 <= len(language) <= 64
                                 or any(ord(char) < 32 or ord(char) == 127 for char in language)):
        language = None
    return RepositoryMetadata(
        sourcecraft_id=sourcecraft_id, organization_slug=organization_slug,
        repository_slug=repository_slug, visibility=visibility,
        default_branch=normalize_default_branch(raw.get("default_branch")),
        is_empty=is_empty, language=language, likes=normalize_repository_likes(raw.get("rating")),
    )
