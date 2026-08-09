from datetime import datetime
from typing import Optional

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        UniqueConstraint("source", "external_id", name="uq_jobs_source_external_id"),
        Index("ix_jobs_active_posted", "is_active", text("posted_at DESC NULLS LAST")),
        Index("ix_jobs_search_tsv", "search_tsv", postgresql_using="gin"),
        Index(
            "ix_jobs_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
        Index("ix_jobs_skills", "skills", postgresql_using="gin"),
        Index("ix_jobs_tech_tags", "tech_tags", postgresql_using="gin"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[Optional[int]] = mapped_column(ForeignKey("companies.id"), index=True)

    source: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    external_id: Mapped[str] = mapped_column(String(255), nullable=False)

    title: Mapped[str] = mapped_column(String(512), nullable=False)
    company_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    company_url: Mapped[Optional[str]] = mapped_column(String(1024))
    career_page_url: Mapped[Optional[str]] = mapped_column(String(1024))
    apply_url: Mapped[Optional[str]] = mapped_column(String(2048), index=True)

    description_text: Mapped[Optional[str]] = mapped_column(Text)
    description_html: Mapped[Optional[str]] = mapped_column(Text)

    location_raw: Mapped[Optional[str]] = mapped_column(String(512))
    workplace_type: Mapped[str] = mapped_column(String(32), default="unknown", index=True)
    pakistan_friendly: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    employment_type: Mapped[Optional[str]] = mapped_column(String(64))
    career_stage: Mapped[str] = mapped_column(String(32), default="unknown", index=True)

    skills: Mapped[Optional[list[str]]] = mapped_column(ARRAY(String), default=list)
    tech_tags: Mapped[Optional[list[str]]] = mapped_column(ARRAY(String), default=list)

    posted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), index=True)
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    missed_runs: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    search_tsv: Mapped[Optional[object]] = mapped_column(TSVECTOR)
    embedding = mapped_column(Vector(768), nullable=True)
    embedding_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    embedding_provider: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    company: Mapped[Optional["Company"]] = relationship("Company", back_populates="jobs")  # noqa: F821
