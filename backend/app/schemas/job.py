from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source: str
    external_id: str
    title: str
    company_name: str
    company_url: Optional[str] = None
    career_page_url: Optional[str] = None
    apply_url: Optional[str] = None
    location_raw: Optional[str] = None
    workplace_type: str
    employment_type: Optional[str] = None
    career_stage: str
    skills: list[str] = Field(default_factory=list)
    tech_tags: list[str] = Field(default_factory=list)
    posted_at: Optional[datetime] = None
    first_seen_at: datetime
    last_seen_at: datetime
    is_active: bool
    description_text: Optional[str] = None
    score: Optional[float] = None
    source_kind: Optional[str] = None
    source_kind_label: Optional[str] = None
    match_reasons: list[str] = Field(default_factory=list)
    # Explainable fit ledger (0–100 factors) when ranked for a profile
    match_breakdown: Optional[dict] = None


class JobSearchResponse(BaseModel):
    total: int
    page: int
    page_size: int
    freshness_days: int
    results: list[JobOut]


class SitemapJobEntry(BaseModel):
    """Minimal job row for XML sitemaps (public, non-sensitive)."""

    id: int
    last_modified: datetime


class SitemapEntriesResponse(BaseModel):
    total: int
    page: int
    page_size: int
    freshness_days: int
    entries: list[SitemapJobEntry]


class HealthResponse(BaseModel):
    status: str
    database: str
