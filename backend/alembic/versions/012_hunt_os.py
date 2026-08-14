"""Hunt OS: tracker snapshots, follow-up timestamps, ghosted status.

Revision ID: 012_hunt_os
Revises: 011_junior_eligible
"""

from typing import Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "012_hunt_os"
down_revision: Union[str, None] = "011_junior_eligible"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("saved_jobs", sa.Column("job_title", sa.String(length=512), nullable=True))
    op.add_column("saved_jobs", sa.Column("company_name", sa.String(length=255), nullable=True))
    op.add_column("saved_jobs", sa.Column("apply_url", sa.String(length=2048), nullable=True))
    op.add_column("saved_jobs", sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("saved_jobs", sa.Column("follow_up_on", sa.DateTime(timezone=True), nullable=True))
    op.add_column("saved_jobs", sa.Column("last_touch_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("saved_jobs", sa.Column("resume_tailoring_id", sa.Integer(), nullable=True))
    op.add_column(
        "saved_jobs",
        sa.Column("checklist", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "saved_jobs",
        sa.Column("packet_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.create_index("ix_saved_jobs_follow_up_on", "saved_jobs", ["follow_up_on"])
    op.create_index("ix_saved_jobs_status", "saved_jobs", ["status"])

    op.alter_column("saved_jobs", "job_id", existing_type=sa.Integer(), nullable=True)
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    for fk in inspector.get_foreign_keys("saved_jobs"):
        if fk.get("referred_table") == "jobs" and fk.get("name"):
            op.drop_constraint(fk["name"], "saved_jobs", type_="foreignkey")
    op.create_foreign_key(
        "saved_jobs_job_id_fkey",
        "saved_jobs",
        "jobs",
        ["job_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("saved_jobs_job_id_fkey", "saved_jobs", type_="foreignkey")
    op.execute("DELETE FROM saved_jobs WHERE job_id IS NULL")
    op.alter_column("saved_jobs", "job_id", existing_type=sa.Integer(), nullable=False)
    op.create_foreign_key(
        "saved_jobs_job_id_fkey",
        "saved_jobs",
        "jobs",
        ["job_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.drop_index("ix_saved_jobs_status", table_name="saved_jobs")
    op.drop_index("ix_saved_jobs_follow_up_on", table_name="saved_jobs")
    op.drop_column("saved_jobs", "packet_snapshot")
    op.drop_column("saved_jobs", "checklist")
    op.drop_column("saved_jobs", "resume_tailoring_id")
    op.drop_column("saved_jobs", "last_touch_at")
    op.drop_column("saved_jobs", "follow_up_on")
    op.drop_column("saved_jobs", "applied_at")
    op.drop_column("saved_jobs", "apply_url")
    op.drop_column("saved_jobs", "company_name")
    op.drop_column("saved_jobs", "job_title")
