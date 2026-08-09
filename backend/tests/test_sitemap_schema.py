"""Unit tests for SEO-facing job route helpers and schemas (no live DB)."""

from app.schemas.job import SitemapEntriesResponse, SitemapJobEntry
from datetime import datetime, timezone


def test_sitemap_entry_schema():
    entry = SitemapJobEntry(
        id=42,
        last_modified=datetime(2026, 8, 1, tzinfo=timezone.utc),
    )
    assert entry.id == 42
    payload = SitemapEntriesResponse(
        total=1,
        page=1,
        page_size=5000,
        freshness_days=30,
        entries=[entry],
    )
    assert payload.total == 1
    assert payload.entries[0].id == 42
