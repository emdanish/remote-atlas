"""Unit tests for SEO taxonomy mapping (no DB)."""

from app.seo.taxonomy import (
    SEO_SKILL_MAP,
    TAG_TO_SKILL_SLUG,
    skill_href,
    slugify_company,
    normalize_title_key,
)


def test_skill_href_remote_ok_style():
    assert skill_href("javascript") == "/remote-javascript-jobs"
    assert "javascript" in SEO_SKILL_MAP
    assert TAG_TO_SKILL_SLUG["next.js"] == "next-js"


def test_slugify_company():
    assert slugify_company("Google LLC") == "google-llc"
    assert slugify_company("  OpenAI  ") == "openai"


def test_normalize_title_key_strips_remote_suffix():
    assert "remote" not in normalize_title_key("Software Engineer (Remote)").lower()
    assert normalize_title_key("Senior Engineer - Remote") == "Senior Engineer"
