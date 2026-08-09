"""Unit tests for pipeline helpers — no database required."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.collectors.weworkremotely import parse_wwr_title
from app.pipeline.enrich import is_pakistan_friendly_remote
from app.pipeline.freshness import freshness_cutoff, is_fresh
from app.pipeline.normalize import (
    apply_url_is_usable,
    canonical_apply_url,
    fingerprint,
    parse_datetime,
)
from app.pipeline.source_trust import PREFERRED_SOURCES_ORDER, source_kind, source_trust_rank


class _Job:
    def __init__(self, posted_at=None, first_seen_at=None, is_active=True):
        self.posted_at = posted_at
        self.first_seen_at = first_seen_at or datetime.now(timezone.utc)
        self.is_active = is_active


def test_canonical_apply_url_strips_tracking():
    raw = "https://www.Example.com/jobs/123/?utm_source=board&gh_src=xyz&keep=1"
    out = canonical_apply_url(raw)
    assert out is not None
    assert "utm_source" not in out
    assert "gh_src" not in out
    assert "keep=1" in out
    assert out.startswith("https://example.com/jobs/123")


def test_apply_url_rejects_api_hosts():
    assert not apply_url_is_usable("https://api.smartrecruiters.com/v1/companies/x/postings/1")
    assert not apply_url_is_usable("https://boards-api.greenhouse.io/v1/boards/x/jobs")
    assert apply_url_is_usable("https://boards.greenhouse.io/acme/jobs/1")


def test_fingerprint_normalizes_whitespace():
    assert fingerprint("  Senior  Engineer ", " Acme  ") == "senior engineer|acme"


def test_parse_datetime_epoch_ms():
    # 2024-01-01 approx
    dt = parse_datetime(1_704_067_200_000)
    assert dt is not None
    assert dt.year == 2024


def test_source_trust_ordering():
    assert source_kind("greenhouse") == "ats"
    assert source_kind("weworkremotely") == "curated_board"
    assert source_kind("themuse") == "aggregator"
    assert source_trust_rank("greenhouse") < source_trust_rank("remotive")
    assert source_trust_rank("remotive") < source_trust_rank("themuse")
    assert "bamboohr" in PREFERRED_SOURCES_ORDER


def test_wwr_title_parse():
    company, title = parse_wwr_title("Stripe: Senior Backend Engineer")
    assert company == "Stripe"
    assert title == "Senior Backend Engineer"
    company2, title2 = parse_wwr_title("No colon here")
    assert company2 == "Unknown"
    assert title2 == "No colon here"


def test_pakistan_friendly_remote():
    assert is_pakistan_friendly_remote("remote", "Worldwide", None)
    assert is_pakistan_friendly_remote("remote", "Lahore, Pakistan", None)
    assert is_pakistan_friendly_remote("remote", None, "Candidates in APAC welcome")
    assert not is_pakistan_friendly_remote("onsite", "Lahore", None)


def test_freshness_cutoff_and_is_fresh():
    now = datetime.now(timezone.utc)
    cutoff = freshness_cutoff(14)
    assert cutoff < now
    assert is_fresh(_Job(posted_at=now - timedelta(days=7)), 14)
    assert not is_fresh(_Job(posted_at=now - timedelta(days=40)), 14)
    # Null posted_at uses first_seen_at
    assert is_fresh(_Job(posted_at=None, first_seen_at=now - timedelta(days=2)), 14)
    assert not is_fresh(_Job(posted_at=None, first_seen_at=now - timedelta(days=40)), 14)
