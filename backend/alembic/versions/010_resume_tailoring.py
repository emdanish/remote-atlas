"""Resume storage and AI tailoring job tracking.

Revision ID: 010_resume_tailoring
Revises: 009_saved_searches
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "010_resume_tailoring"
down_revision = "009_saved_searches"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_resumes",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("filename", sa.String(length=512), nullable=False),
        sa.Column("content_type", sa.String(length=128), nullable=False),
        sa.Column("storage_path", sa.String(length=1024), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("extracted_text", sa.Text(), nullable=True),
        sa.Column("analysis_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_user_resumes_user_id", "user_resumes", ["user_id"])
    op.create_index("ix_user_resumes_sha256", "user_resumes", ["sha256"])

    op.create_table(
        "resume_tailorings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("resume_id", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("stage", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("model_used", sa.String(length=64), nullable=True),
        sa.Column("job_analysis", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("resume_facts", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("tailored_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("validation_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("changes_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("match_panel", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("pdf_path", sa.String(length=1024), nullable=True),
        sa.Column("original_excerpt", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["resume_id"], ["user_resumes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_resume_tailorings_user_id", "resume_tailorings", ["user_id"])
    op.create_index("ix_resume_tailorings_job_id", "resume_tailorings", ["job_id"])
    op.create_index(
        "ix_resume_tailorings_user_job",
        "resume_tailorings",
        ["user_id", "job_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_resume_tailorings_user_job", table_name="resume_tailorings")
    op.drop_index("ix_resume_tailorings_job_id", table_name="resume_tailorings")
    op.drop_index("ix_resume_tailorings_user_id", table_name="resume_tailorings")
    op.drop_table("resume_tailorings")
    op.drop_index("ix_user_resumes_sha256", table_name="user_resumes")
    op.drop_index("ix_user_resumes_user_id", table_name="user_resumes")
    op.drop_table("user_resumes")
