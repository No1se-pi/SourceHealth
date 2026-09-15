"""Relational identity/lifecycle + versioned JSONB для меняющихся результатов."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, Float, ForeignKey, Index, Integer, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    yandex_id: Mapped[str] = mapped_column(String(128), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))


class Repository(Base):
    __tablename__ = "repositories"
    __table_args__ = (
        UniqueConstraint("organization_slug", "repository_slug", name="uq_repository_slug"),
        CheckConstraint("visibility IN ('public','private','unknown')", name="ck_repository_visibility"),
        CheckConstraint("health_score IS NULL OR health_score BETWEEN 0 AND 100", name="ck_repository_score"),
        Index("ix_repository_leaderboard", "visibility", text("health_score DESC NULLS LAST"), "id"),
        Index("ix_repository_due", "next_analysis_at"),
        Index("ix_repository_language", "language"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    sourcecraft_id: Mapped[str | None] = mapped_column(String(128), unique=True)
    organization_slug: Mapped[str] = mapped_column(String(100))
    repository_slug: Mapped[str] = mapped_column(String(100))
    canonical_url: Mapped[str] = mapped_column(String(512), unique=True)
    visibility: Mapped[str] = mapped_column(String(16), default="unknown", server_default="unknown")
    default_branch: Mapped[str | None] = mapped_column(String(256))
    head_sha: Mapped[str | None] = mapped_column(String(64))
    language: Mapped[str | None] = mapped_column(String(64))
    likes: Mapped[int | None] = mapped_column(Integer)
    last_activity_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    health_score: Mapped[float | None] = mapped_column(Float)
    latest_analysis_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey(
        "analysis_runs.id", name="fk_repository_latest_analysis", use_alter=True, ondelete="SET NULL"))
    next_analysis_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))


class AnalysisRun(Base):
    __tablename__ = "analysis_runs"
    __table_args__ = (
        CheckConstraint("status IN ('queued','collecting','analyzing','scoring','completed','partial','failed')",
                        name="ck_run_status"),
        CheckConstraint("trigger IN ('manual','scheduled','refresh','system')", name="ck_run_trigger"),
        CheckConstraint("health_score IS NULL OR health_score BETWEEN 0 AND 100", name="ck_run_score"),
        CheckConstraint("(status IN ('completed','partial','failed')) = (completed_at IS NOT NULL)",
                        name="ck_run_terminal_time"),
        Index("uq_active_repository_profile", "repository_id", "profile", unique=True,
              postgresql_where=text("status IN ('queued','collecting','analyzing','scoring')")),
        Index("ix_run_repository_history", "repository_id", text("queued_at DESC")),
        Index("ix_run_fingerprint", "fingerprint", "completed_at"),
        Index("ix_run_dispatch", "status", "queued_at"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    repository_id: Mapped[UUID] = mapped_column(ForeignKey("repositories.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(String(16), default="queued", server_default="queued")
    trigger: Mapped[str] = mapped_column(String(16))
    profile: Mapped[str] = mapped_column(String(128))
    fingerprint: Mapped[str] = mapped_column(String(64))
    queued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deadline_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    head_sha: Mapped[str | None] = mapped_column(String(64))
    scoring_policy_version: Mapped[str] = mapped_column(String(128), default="unconfigured-v1")
    analyzer_contract_version: Mapped[str] = mapped_column(String(16), default="3.0")
    health_score: Mapped[float | None] = mapped_column(Float)
    category_scores: Mapped[dict] = mapped_column(JSONB, default=dict, server_default=text("'{}'::jsonb"))
    data_coverage: Mapped[dict] = mapped_column(JSONB, default=dict, server_default=text("'{}'::jsonb"))
    recommendations: Mapped[list] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))
    results: Mapped[dict] = mapped_column(JSONB, default=dict, server_default=text("'{}'::jsonb"))
    error_code: Mapped[str | None] = mapped_column(String(64))
