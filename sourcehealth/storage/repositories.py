"""Shared SourceCraft repository identity reconciliation for manual and catalog imports."""

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError

from .models import Repository


class RepositoryIdentityConflict(RuntimeError):
    pass


def upsert_sourcecraft_repository(db, values: dict) -> Repository:
    """Reconcile mutable slugs around the immutable SourceCraft repository ID."""
    sourcecraft_id = values["sourcecraft_id"]
    row = db.scalar(select(Repository).where(
        Repository.sourcecraft_id == sourcecraft_id).with_for_update())
    collision = db.scalar(select(Repository).where(or_(
        Repository.canonical_url == values["canonical_url"],
        (Repository.organization_slug == values["organization_slug"])
        & (Repository.repository_slug == values["repository_slug"]),
    )).with_for_update())
    if row is not None and collision is not None and collision.id != row.id:
        raise RepositoryIdentityConflict
    if row is None and collision is not None:
        if collision.sourcecraft_id not in {None, sourcecraft_id}:
            raise RepositoryIdentityConflict
        row = collision
    if row is None:
        if "next_analysis_at" not in values:
            from datetime import UTC, datetime, timedelta
            values["next_analysis_at"] = datetime.now(UTC) + timedelta(days=365)
        row = Repository(**values)
        db.add(row)
    else:
        row.sourcecraft_id = sourcecraft_id
        for key in ("organization_slug", "repository_slug", "canonical_url", "visibility",
                    "default_branch", "language", "likes", "description", "logo_url",
                    "origin", "project_slug", "topics", "topic_classifier_version"):
            if key in values:
                setattr(row, key, values[key])
    if hasattr(db, "flush"):
        try:
            db.flush()
        except IntegrityError:
            raise RepositoryIdentityConflict from None
    return row
