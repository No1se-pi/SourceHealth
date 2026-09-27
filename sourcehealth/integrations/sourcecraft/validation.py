"""Shared validation for SourceCraft fields used by more than one integration path."""

from typing import Any

from .client import SourceCraftError


def normalize_default_branch(value: Any) -> str | None:
    """Normalize an empty-repository branch while preserving valid Unicode Git refs."""
    if value in (None, ""):
        return None
    if (not isinstance(value, str) or not 1 <= len(value) <= 255
            or any(ord(char) < 32 or ord(char) == 127 for char in value)):
        raise SourceCraftError("invalid_response")
    return value
