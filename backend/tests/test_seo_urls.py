"""Smoke tests for HTML sanitization helpers (Node/TS mirrored rules in pure unit style)."""

from app.seo.taxonomy import SEO_SKILL_MAP, skill_href


def test_known_skill_urls_unique():
    hrefs = {skill_href(s) for s in SEO_SKILL_MAP}
    assert len(hrefs) == len(SEO_SKILL_MAP)
    assert all(h.startswith("/remote-") and h.endswith("-jobs") for h in hrefs)
