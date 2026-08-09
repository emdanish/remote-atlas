from datetime import datetime
from typing import Any, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class UserResume(Base):
    __tablename__ = "user_resumes"
    __table_args__ = (Index("ix_user_resumes_user_id", "user_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    content_type: Mapped[str] = mapped_column(String(128), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    byte_size: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    extracted_text: Mapped[Optional[str]] = mapped_column(Text)
    analysis_json: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    tailorings: Mapped[list["ResumeTailoring"]] = relationship(
        "ResumeTailoring", back_populates="resume", cascade="all, delete-orphan"
    )


class ResumeTailoring(Base):
    __tablename__ = "resume_tailorings"
    __table_args__ = (
        Index("ix_resume_tailorings_user_job", "user_id", "job_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    resume_id: Mapped[int] = mapped_column(
        ForeignKey("user_resumes.id", ondelete="CASCADE"), nullable=False
    )
    job_id: Mapped[int] = mapped_column(
        ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    # pending | running | completed | failed
    stage: Mapped[Optional[str]] = mapped_column(String(64))
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    model_used: Mapped[Optional[str]] = mapped_column(String(64))
    job_analysis: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB)
    resume_facts: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB)
    tailored_json: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB)
    validation_json: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB)
    changes_json: Mapped[Optional[list[Any]]] = mapped_column(JSONB)
    match_panel: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB)
    pdf_path: Mapped[Optional[str]] = mapped_column(String(1024))
    original_excerpt: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    resume: Mapped["UserResume"] = relationship("UserResume", back_populates="tailorings")
