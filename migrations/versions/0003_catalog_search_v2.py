"""Catalog search v2: repository metadata, topics and search indexes."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0003_catalog_search_v2"
down_revision = "0002_product_growth"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("repositories", sa.Column("description", sa.String(512), nullable=True))
    op.add_column("repositories", sa.Column("logo_url", sa.String(512), nullable=True))
    op.add_column("repositories", sa.Column("origin", sa.String(32), server_default="unknown", nullable=True))
    op.add_column("repositories", sa.Column("project_slug", sa.String(100), nullable=True))
    op.add_column("repositories", sa.Column("topics", postgresql.JSONB(astext_type=sa.Text()),
                                            server_default=sa.text("'[]'::jsonb"), nullable=False))
    op.add_column("repositories", sa.Column("topic_classifier_version", sa.String(32), nullable=True))

    op.create_index("ix_repository_lower_org", "repositories", [sa.text("lower(organization_slug)")])
    op.create_index("ix_repository_lower_repo", "repositories", [sa.text("lower(repository_slug)")])
    op.create_index("ix_repository_likes", "repositories", [sa.text("likes DESC NULLS LAST"), "id"])
    op.create_index("ix_repository_last_activity", "repositories", [sa.text("last_activity_at DESC NULLS LAST"), "id"])
    op.create_index("ix_repository_origin", "repositories", ["origin"])
    op.create_index("ix_repository_topics", "repositories", ["topics"], postgresql_using="gin")


def downgrade():
    op.drop_index("ix_repository_topics", table_name="repositories", postgresql_using="gin")
    op.drop_index("ix_repository_origin", table_name="repositories")
    op.drop_index("ix_repository_last_activity", table_name="repositories")
    op.drop_index("ix_repository_likes", table_name="repositories")
    op.drop_index("ix_repository_lower_repo", table_name="repositories")
    op.drop_index("ix_repository_lower_org", table_name="repositories")

    op.drop_column("repositories", "topic_classifier_version")
    op.drop_column("repositories", "topics")
    op.drop_column("repositories", "project_slug")
    op.drop_column("repositories", "origin")
    op.drop_column("repositories", "logo_url")
    op.drop_column("repositories", "description")
