"""Add embedding_hash for cheap re-embed detection

Revision ID: 004_embedding_hash
Revises: 003_phase3
Create Date: 2026-08-01
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "004_embedding_hash"
down_revision: Union[str, None] = "003_phase3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("embedding_hash", sa.String(length=64), nullable=True))


def downgrade() -> None:
    op.drop_column("jobs", "embedding_hash")
