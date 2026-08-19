"""Shared structured data returned by the Git collector."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class Commit:
    """A normalized Git commit that can be consumed by any analyzer."""

    hash: str
    author_name: str
    author_email: str
    datetime: datetime
    message: str

    def __post_init__(self) -> None:
        if self.datetime.tzinfo is None or self.datetime.utcoffset() is None:
            raise ValueError("Commit datetime must be timezone-aware")

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation of the commit."""

        return {
            "hash": self.hash,
            "author_name": self.author_name,
            "author_email": self.author_email,
            "datetime": self.datetime.isoformat(),
            "message": self.message,
        }
