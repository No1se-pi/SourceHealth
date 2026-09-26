"""Product growth: catalog checkpoint and user repository preferences."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0002_product_growth"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("sourcecraft_retention_seconds", sa.Integer(),
                                     server_default="1800", nullable=False))
    op.create_table(
        "catalog_sync_state",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("page_token", sa.String(1024)),
        sa.Column("cycle_started_at", sa.DateTime(timezone=True)),
        sa.Column("last_completed_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_table(
        "user_repositories",
        sa.Column("user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("repository_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("repositories.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("refresh_preference", sa.String(16), server_default="adaptive", nullable=False),
        sa.Column("use_pat_for_scheduled_analysis", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.CheckConstraint("refresh_preference IN ('adaptive','1h','6h','24h','7d','off')",
                           name="ck_user_repository_refresh"),
    )
    op.create_index("ix_user_repository_repository", "user_repositories", ["repository_id"])


def downgrade():
    op.drop_index("ix_user_repository_repository", table_name="user_repositories")
    op.drop_table("user_repositories")
    op.drop_table("catalog_sync_state")
    op.drop_column("users", "sourcecraft_retention_seconds")
