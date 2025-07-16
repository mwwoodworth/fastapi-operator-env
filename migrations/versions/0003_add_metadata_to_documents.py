"""add metadata column to documents table"""

from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("metadata", sa.JSON, nullable=True))


def downgrade() -> None:
    op.drop_column("documents", "metadata")
