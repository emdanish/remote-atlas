"""Tests for saved-search filter shaping."""

from app.matching.alerts import _filters_from_query


def test_filters_from_query_skills_string():
    f = _filters_from_query(
        {
            "q": "python",
            "skills": "python, django",
            "workplace": "remote",
            "posted_within": 3,
            "pakistan_friendly": True,
        }
    )
    assert f["q"] == "python"
    assert f["skills"] == ["python", "django"]
    assert f["posted_within"] == 3
    assert f["pakistan_friendly"] is True
    assert f["sort"] == "newest"


def test_filters_clamp_posted_within():
    f = _filters_from_query({"posted_within": 999})
    assert f["posted_within"] == 30
    f2 = _filters_from_query({"posted_within": "x"})
    assert f2["posted_within"] == 7
