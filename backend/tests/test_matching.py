"""Unit tests for explainable matching (no DB)."""

from datetime import datetime, timezone
from types import SimpleNamespace

from app.matching.scoring import (
    build_search_query,
    profile_onboarding_state,
    score_job_breakdown,
)
from app.matching.skill_tags import partition_skills_and_technologies


def _job(**kwargs):
    defaults = dict(
        title="Senior React Engineer",
        company_name="Acme",
        skills=["react", "typescript", "node.js"],
        tech_tags=["react", "graphql"],
        career_stage="senior",
        workplace_type="remote",
        location_raw="Worldwide",
        pakistan_friendly=True,
        posted_at=datetime.now(timezone.utc),
        first_seen_at=datetime.now(timezone.utc),
        description_text="Build UI with React and TypeScript on a remote team",
    )
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def test_score_prefers_skill_overlap():
    strong = score_job_breakdown(
        _job(),
        skills={"react", "typescript"},
        level="senior",
        remote_pref="remote",
        pakistan_friendly=True,
    )
    weak = score_job_breakdown(
        _job(),
        skills={"cobol", "fortran"},
        level="internship",
        remote_pref="onsite",
        pakistan_friendly=False,
    )
    assert strong.total > weak.total
    assert "react" in strong.matched_skills
    assert strong.pakistan >= 8


def test_score_matches_skill_in_description_not_only_tags():
    job = _job(
        skills=[],
        tech_tags=[],
        description_text="Looking for FastAPI and PostgreSQL experience",
    )
    bd = score_job_breakdown(
        job,
        skills={"fastapi", "postgresql", "python"},
        level="junior",
        remote_pref="remote",
    )
    assert bd.skill > 0
    assert bd.matched_skills


def test_build_search_query_roles_first():
    q = build_search_query(desired_roles=["Flutter developer"], skills={"python"})
    assert q == "Flutter developer"
    q2 = build_search_query(desired_roles=[], skills={"python", "django", "react"})
    assert " OR " in q2 or "python" in q2


def test_partition_skills_and_technologies_not_identical():
    skills, tech = partition_skills_and_technologies(
        ["python", "react", "fastapi", "postgresql", "docker"],
        ["agile collaboration", "full-stack development", "prompt engineering"],
        ["python", "react"],
    )
    assert "python" in tech
    assert "react" in tech
    assert "python" not in skills
    assert "agile collaboration" in skills or "full-stack development" in skills
    assert set(skills) != set(tech)


def test_onboarding_seed_and_complete():
    profile = SimpleNamespace(
        skills=["react"],
        technologies=["typescript"],
        desired_roles=[],
        remote_preference="remote",
        extra={
            "resume_uploaded_at": "2026-01-01T00:00:00Z",
            "seed_skills": ["react", "typescript"],
        },
    )
    state = profile_onboarding_state(profile)
    assert state["has_skills"] is True
    assert state["has_resume"] is True
    assert state["onboarding_complete"] is True
    assert state["seed_skills"] == ["react", "typescript"]

    empty = profile_onboarding_state(None)
    assert empty["onboarding_complete"] is False
    assert empty["completion_percent"] == 0
