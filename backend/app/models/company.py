from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Company(Base):
    __tablename__ = "companies"
    __table_args__ = (
        Index("uq_companies_ats_type_slug", "ats_type", "ats_slug", unique=True),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    website: Mapped[Optional[str]] = mapped_column(String(512))
    ats_type: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    ats_slug: Mapped[Optional[str]] = mapped_column(String(128), index=True)
    career_page_url: Mapped[Optional[str]] = mapped_column(String(1024))
    region_focus: Mapped[str] = mapped_column(String(32), default="global")
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    hires_juniors: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    jobs: Mapped[list["Job"]] = relationship("Job", back_populates="company")  # noqa: F821
