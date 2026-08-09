"""Initial schema with pgvector

Revision ID: 001_initial
Revises:
Create Date: 2026-08-01

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "companies",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("website", sa.String(length=512), nullable=True),
        sa.Column("ats_type", sa.String(length=64), nullable=True),
        sa.Column("ats_slug", sa.String(length=128), nullable=True),
        sa.Column("career_page_url", sa.String(length=1024), nullable=True),
        sa.Column("region_focus", sa.String(length=32), nullable=False, server_default="global"),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_companies_name", "companies", ["name"])
    op.create_index("ix_companies_ats_type", "companies", ["ats_type"])
    op.create_index("ix_companies_ats_slug", "companies", ["ats_slug"])
    op.create_index(
        "uq_companies_ats_type_slug",
        "companies",
        ["ats_type", "ats_slug"],
        unique=True,
    )

    op.create_table(
        "ingest_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("jobs_fetched", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("jobs_upserted", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("errors", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ingest_runs_source", "ingest_runs", ["source"])

    op.create_table(
        "jobs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=True),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("external_id", sa.String(length=255), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("company_name", sa.String(length=255), nullable=False),
        sa.Column("company_url", sa.String(length=1024), nullable=True),
        sa.Column("career_page_url", sa.String(length=1024), nullable=True),
        sa.Column("apply_url", sa.String(length=2048), nullable=True),
        sa.Column("description_text", sa.Text(), nullable=True),
        sa.Column("description_html", sa.Text(), nullable=True),
        sa.Column("location_raw", sa.String(length=512), nullable=True),
        sa.Column(
            "workplace_type",
            sa.String(length=32),
            nullable=False,
            server_default="unknown",
        ),
        sa.Column("employment_type", sa.String(length=64), nullable=True),
        sa.Column(
            "career_stage",
            sa.String(length=32),
            nullable=False,
            server_default="unknown",
        ),
        sa.Column("skills", postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column("tech_tags", postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "first_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("search_tsv", postgresql.TSVECTOR(), nullable=True),
        sa.Column("embedding", Vector(768), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source", "external_id", name="uq_jobs_source_external_id"),
    )
    op.create_index("ix_jobs_company_id", "jobs", ["company_id"])
    op.create_index("ix_jobs_source", "jobs", ["source"])
    op.create_index("ix_jobs_company_name", "jobs", ["company_name"])
    op.create_index("ix_jobs_apply_url", "jobs", ["apply_url"])
    op.create_index("ix_jobs_workplace_type", "jobs", ["workplace_type"])
    op.create_index("ix_jobs_career_stage", "jobs", ["career_stage"])
    op.create_index("ix_jobs_posted_at", "jobs", ["posted_at"])
    op.create_index("ix_jobs_is_active", "jobs", ["is_active"])
    op.create_index(
        "ix_jobs_active_posted",
        "jobs",
        ["is_active", sa.text("posted_at DESC NULLS LAST")],
    )
    op.create_index("ix_jobs_search_tsv", "jobs", ["search_tsv"], postgresql_using="gin")
    op.create_index("ix_jobs_skills", "jobs", ["skills"], postgresql_using="gin")
    op.create_index("ix_jobs_tech_tags", "jobs", ["tech_tags"], postgresql_using="gin")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_jobs_embedding_hnsw ON jobs "
        "USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_jobs_embedding_hnsw")
    op.drop_table("jobs")
    op.drop_table("ingest_runs")
    op.drop_table("companies")
