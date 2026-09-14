"""Stable identities and run lifecycle; analyzer payloads use versioned JSONB.

The circular latest pointer is added after both tables exist. It is removed
first on downgrade. A downgrade destroys history and requires an operator backup.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("users",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("yandex_id", sa.String(128), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")))
    op.create_table("repositories",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("sourcecraft_id", sa.String(128), unique=True),
        sa.Column("organization_slug", sa.String(100), nullable=False),
        sa.Column("repository_slug", sa.String(100), nullable=False),
        sa.Column("canonical_url", sa.String(512), nullable=False, unique=True),
        sa.Column("visibility", sa.String(16), nullable=False, server_default="unknown"),
        sa.Column("default_branch", sa.String(256)), sa.Column("head_sha", sa.String(64)),
        sa.Column("language", sa.String(64)), sa.Column("likes", sa.Integer()),
        sa.Column("last_activity_at", sa.DateTime(timezone=True)), sa.Column("health_score", sa.Float()),
        sa.Column("latest_analysis_id", pg.UUID(as_uuid=True)),
        sa.Column("next_analysis_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("organization_slug", "repository_slug", name="uq_repository_slug"),
        sa.CheckConstraint("visibility IN ('public','private','unknown')", name="ck_repository_visibility"),
        sa.CheckConstraint("health_score IS NULL OR health_score BETWEEN 0 AND 100", name="ck_repository_score"))
    op.create_table("analysis_runs",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("repository_id", pg.UUID(as_uuid=True), sa.ForeignKey("repositories.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="queued"),
        sa.Column("trigger", sa.String(16), nullable=False), sa.Column("profile", sa.String(128), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("queued_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("started_at", sa.DateTime(timezone=True)), sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("deadline_at", sa.DateTime(timezone=True)), sa.Column("head_sha", sa.String(64)),
        sa.Column("scoring_policy_version", sa.String(128), nullable=False),
        sa.Column("analyzer_contract_version", sa.String(16), nullable=False),
        sa.Column("health_score", sa.Float()),
        sa.Column("category_scores", pg.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("data_coverage", pg.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("recommendations", pg.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("results", pg.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("error_code", sa.String(64)),
        sa.CheckConstraint("status IN ('queued','collecting','analyzing','scoring','completed','partial','failed')",
                           name="ck_run_status"),
        sa.CheckConstraint("trigger IN ('manual','scheduled','refresh','system')", name="ck_run_trigger"),
        sa.CheckConstraint("health_score IS NULL OR health_score BETWEEN 0 AND 100", name="ck_run_score"),
        sa.CheckConstraint("(status IN ('completed','partial','failed')) = (completed_at IS NOT NULL)",
                           name="ck_run_terminal_time"))
    op.create_foreign_key("fk_repository_latest_analysis", "repositories", "analysis_runs",
                          ["latest_analysis_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_repository_leaderboard", "repositories",
                    ["visibility", sa.text("health_score DESC NULLS LAST"), "id"])
    op.create_index("ix_repository_due", "repositories", ["next_analysis_at"])
    op.create_index("ix_repository_language", "repositories", ["language"])
    op.create_index("uq_active_repository_profile", "analysis_runs", ["repository_id", "profile"], unique=True,
                    postgresql_where=sa.text("status IN ('queued','collecting','analyzing','scoring')"))
    op.create_index("ix_run_repository_history", "analysis_runs", ["repository_id", sa.text("queued_at DESC")])
    op.create_index("ix_run_fingerprint", "analysis_runs", ["fingerprint", "completed_at"])
    op.create_index("ix_run_dispatch", "analysis_runs", ["status", "queued_at"])


def downgrade():
    op.drop_constraint("fk_repository_latest_analysis", "repositories", type_="foreignkey")
    op.drop_table("analysis_runs")
    op.drop_table("repositories")
    op.drop_table("users")
