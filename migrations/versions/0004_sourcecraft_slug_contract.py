"""Align persisted SourceCraft slug lengths with the validated API contract."""

import sqlalchemy as sa
from alembic import op

revision = "0004_sourcecraft_slug_contract"
down_revision = "0003_catalog_search_v2"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column("repositories", "organization_slug", existing_type=sa.String(100),
                    type_=sa.String(128), existing_nullable=False)
    op.alter_column("repositories", "repository_slug", existing_type=sa.String(100),
                    type_=sa.String(128), existing_nullable=False)
    op.alter_column("repositories", "project_slug", existing_type=sa.String(100),
                    type_=sa.String(128), existing_nullable=True)


def downgrade():
    # Never truncate data: PostgreSQL must reject this if long slugs exist.
    op.alter_column("repositories", "project_slug", existing_type=sa.String(128),
                    type_=sa.String(100), existing_nullable=True)
    op.alter_column("repositories", "repository_slug", existing_type=sa.String(128),
                    type_=sa.String(100), existing_nullable=False)
    op.alter_column("repositories", "organization_slug", existing_type=sa.String(128),
                    type_=sa.String(100), existing_nullable=False)
