"""Track the vector space used for each job embedding.

Revision ID: 006_embedding_provider
Revises: 005_repair_smartrecruiters_urls
Create Date: 2026-08-02
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "006_embedding_provider"
down_revision: Union[str, None] = "005_repair_smartrecruiters_urls"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("embedding_provider", sa.String(length=64), nullable=True))
    op.create_index("ix_jobs_embedding_provider", "jobs", ["embedding_provider"])


def downgrade() -> None:
    op.drop_index("ix_jobs_embedding_provider", table_name="jobs")
    op.drop_column("jobs", "embedding_provider")
