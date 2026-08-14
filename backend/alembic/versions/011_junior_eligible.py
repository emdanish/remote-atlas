"""Junior-eligible flags, years required, company hires_juniors.

Revision ID: 011_junior_eligible
Revises: 010_resume_tailoring
"""

from typing import Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "011_junior_eligible"
down_revision: Union[str, None] = "010_resume_tailoring"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("years_required_min", sa.Integer(), nullable=True))
    op.add_column(
        "jobs",
        sa.Column(
            "junior_eligible",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "jobs",
        sa.Column(
            "seniority_signals",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.create_index("ix_jobs_junior_eligible", "jobs", ["junior_eligible"])
    op.add_column(
        "companies",
        sa.Column(
            "hires_juniors",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("companies", "hires_juniors")
    op.drop_index("ix_jobs_junior_eligible", table_name="jobs")
    op.drop_column("jobs", "seniority_signals")
    op.drop_column("jobs", "junior_eligible")
    op.drop_column("jobs", "years_required_min")
