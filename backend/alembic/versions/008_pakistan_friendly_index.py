"""Materialize Pakistan-friendly eligibility for fast filtering.

Revision ID: 008_pakistan_friendly_index
Revises: 007_ingest_miss_tolerance
"""

from alembic import op
import sqlalchemy as sa


revision = "008_pakistan_friendly_index"
down_revision = "007_ingest_miss_tolerance"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "jobs",
        sa.Column("pakistan_friendly", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.execute(
        """
        UPDATE jobs
        SET pakistan_friendly = true
        WHERE workplace_type = 'remote'
          AND concat_ws(' ', location_raw, description_text) ~*
              '\\m(pakistan|pk|worldwide|anywhere|timezone.?flexible|work from anywhere|remote[ -]first|candidates in apac|based in apac|all countries)\\M'
        """
    )
    op.create_index("ix_jobs_pakistan_friendly", "jobs", ["pakistan_friendly"])


def downgrade() -> None:
    op.drop_index("ix_jobs_pakistan_friendly", table_name="jobs")
    op.drop_column("jobs", "pakistan_friendly")
