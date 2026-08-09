"""Explainable multi-factor job matching.

Designed for Remote Atlas: skill overlap + role intent + seniority + remote +
Pakistan affinity + freshness. Pure functions so scoring is unit-testable and
degradable without AI.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from app.models.job import Job


@dataclass
class MatchBreakdown:
    """0–100 fit ledger shown to the user (why this role surfaced)."""

    total: float
    skill: float = 0.0
    role: float = 0.0
    seniority: float = 0.0
    remote: float = 0.0
    pakistan: float = 0.0
    freshness: float = 0.0
    matched_skills: list[str] = field(default_factory=list)
    missing_skills: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _job_skill_set(job: Job) -> set[str]:
    return {
        s.strip().lower()
        for s in (*(job.skills or []), *(job.tech_tags or []))
        if s and s.strip()
    }


def _normalize_profile_skills(skills: set[str] | list[str] | None) -> set[str]:
    return {s.strip().lower() for s in (skills or []) if s and str(s).strip()}


def score_job_breakdown(
    job: Job,
    *,
    skills: set[str] | list[str] | None = None,
    level: str = "junior",
    remote_pref: str = "remote",
    desired_roles: list[str] | None = None,
    cities: list[str] | None = None,
    location_preference: str | None = None,
    pakistan_friendly: bool = False,
    hybrid_score: float = 0.0,
    now: Optional[datetime] = None,
) -> MatchBreakdown:
    """
    Multi-factor score in 0–100 space.
    hybrid_score is additive prior from FTS/vector (scaled modestly).
    """
    from app.matching.skill_tags import (
        generous_skill_overlap,
        normalize_tag,
        profile_skill_universe,
    )

    profile_skills = profile_skill_universe(skills, None)
    # also accept already-normalized sets
    if skills and not profile_skills:
        profile_skills = {normalize_tag(str(s)) for s in skills if s}

    title = (job.title or "").lower()
    location = (job.location_raw or "").lower()
    now = now or datetime.now(timezone.utc)

    # Skills (0–40) — generous tag + description hits
    overlap, missing = generous_skill_overlap(profile_skills, job)
    skill_raw = min(40.0, len(overlap) * 6.0)
    for s in list(profile_skills)[:16]:
        if s and s in title:
            skill_raw = min(40.0, skill_raw + 2.5)
    if overlap:
        skill_raw = min(40.0, skill_raw + min(10.0, len(overlap) * 1.5))
    skill_score = round(skill_raw, 2)

    # Role intent (0–20) — soft: engineer/developer tokens help
    role_score = 0.0
    for role in desired_roles or []:
        normalized_role = (role or "").strip().lower()
        if not normalized_role:
            continue
        if normalized_role in title:
            role_score = max(role_score, 20.0)
        else:
            role_terms = {
                t for t in re.findall(r"[a-z0-9+#.]+", normalized_role) if len(t) > 2
            }
            title_terms = set(re.findall(r"[a-z0-9+#.]+", title))
            role_score = max(role_score, min(20.0, len(role_terms & title_terms) * 5.0))
    if role_score < 6 and any(w in title for w in ("engineer", "developer", "software", "full stack", "fullstack")):
        if profile_skills:
            role_score = max(role_score, 8.0)

    # Seniority (0–12) — unknown stage no longer heavily penalizes
    seniority_score = 0.0
    level_n = (level or "").lower()
    stage = (job.career_stage or "unknown").lower()
    if level_n and stage == level_n:
        seniority_score = 12.0
    elif stage == "unknown" or not level_n:
        seniority_score = 8.0
    elif {
        "internship": 0,
        "junior": 1,
        "mid": 2,
        "senior": 3,
    }.get(stage, 1) == {
        "internship": 0,
        "junior": 1,
        "mid": 2,
        "senior": 3,
    }.get(level_n, 1):
        seniority_score = 12.0
    elif abs(
        {
            "internship": 0,
            "junior": 1,
            "mid": 2,
            "senior": 3,
        }.get(stage, 1)
        - {
            "internship": 0,
            "junior": 1,
            "mid": 2,
            "senior": 3,
        }.get(level_n, 1)
    ) == 1:
        seniority_score = 9.0
    else:
        seniority_score = 4.0

    # Remote / workplace (0–12) — remote-preferring candidates fit hybrid lightly
    remote_score = 0.0
    pref = (remote_pref or "remote").lower()
    wt = (job.workplace_type or "").lower()
    if pref == "any":
        remote_score = 10.0
    elif pref == wt:
        remote_score = 12.0
    elif pref == "remote" and wt in {"hybrid", "remote"}:
        remote_score = 10.0 if wt == "remote" else 7.0
    elif pref == "remote" and wt in {"", "unknown"}:
        remote_score = 6.0
    elif pref != "onsite":
        remote_score = 4.0

    if any(c.strip().lower() in location for c in (cities or []) if c and c.strip()):
        remote_score = min(12.0, remote_score + 2.0)
    preference = (location_preference or "").strip().lower()
    if preference:
        pref_terms = {
            t
            for t in re.findall(r"[a-z]+", preference)
            if len(t) > 2 and t not in {"remote", "roles", "jobs", "preferred"}
        }
        if any(t in location for t in pref_terms):
            remote_score = min(12.0, remote_score + 1.5)
        if wt == "remote" and pref_terms & {"worldwide", "anywhere", "global"}:
            remote_score = min(12.0, remote_score + 1.5)

    # Pakistan affinity (0–10) — soft by default for remote prefs
    pakistan_score = 0.0
    if pakistan_friendly:
        if job.pakistan_friendly:
            pakistan_score = 10.0
        elif wt == "remote":
            pakistan_score = 5.0
        else:
            pakistan_score = 2.0
    elif wt == "remote":
        pakistan_score = 3.0

    # Freshness (0–10)
    freshness_score = 3.0
    posted = job.posted_at or job.first_seen_at
    if posted is not None:
        if posted.tzinfo is None:
            posted = posted.replace(tzinfo=timezone.utc)
        age_days = max(0.0, (now - posted).total_seconds() / 86400.0)
        freshness_score = round(max(1.0, 10.0 * (2.718281828 ** (-age_days / 10.0))), 2)

    hybrid_boost = min(10.0, max(0.0, float(hybrid_score or 0.0)) * 0.2)

    total = (
        skill_score
        + role_score
        + seniority_score
        + remote_score
        + pakistan_score
        + freshness_score
        + hybrid_boost
    )
    total = round(min(100.0, total), 1)

    reasons: list[str] = []
    if overlap:
        reasons.append("Matched: " + ", ".join(overlap[:5]))
    if role_score >= 12:
        reasons.append("Role title fit")
    if seniority_score >= 10:
        reasons.append(f"{level_n or stage} level")
    if remote_score >= 10 and wt == "remote":
        reasons.append("Remote")
    if pakistan_score >= 8:
        reasons.append("Pakistan-friendly remote")
    if freshness_score >= 7:
        reasons.append("Fresh posting")

    return MatchBreakdown(
        total=total,
        skill=round(skill_score, 1),
        role=round(role_score, 1),
        seniority=round(seniority_score, 1),
        remote=round(remote_score, 1),
        pakistan=round(pakistan_score, 1),
        freshness=round(freshness_score, 1),
        matched_skills=overlap[:8],
        missing_skills=missing,
        reasons=reasons,
    )


def legacy_raw_score(breakdown: MatchBreakdown) -> float:
    """Backward-compatible sort key (higher is better). """
    return breakdown.total


def build_search_query(
    *,
    desired_roles: list[str] | None,
    skills: set[str],
    fallback: str = "software engineer OR developer OR fullstack OR backend OR frontend",
) -> str:
    """Broad websearch-friendly query — prefer roles, else a few high-signal techs."""
    if desired_roles:
        first = (desired_roles[0] or "").strip()
        if first:
            return first
    # Prefer stack terms that appear in job titles often
    priority = (
        "python",
        "typescript",
        "javascript",
        "react",
        "next.js",
        "node.js",
        "fastapi",
        "django",
        "java",
        "go",
        "aws",
        "postgresql",
    )
    lower_skills = {s.strip().lower() for s in skills if s}
    ranked = [p for p in priority if p in lower_skills]
    if not ranked:
        ranked = sorted(lower_skills, key=len)[:5]
    # websearch OR for generous FTS (avoid AND of 5 rare tokens)
    terms = ranked[:4]
    if terms:
        return " OR ".join(terms)
    return fallback


def profile_onboarding_state(profile: Any | None) -> dict[str, Any]:
    """Server-side onboarding signal for soft gates."""
    if profile is None:
        return {
            "has_profile": False,
            "has_skills": False,
            "has_resume": False,
            "has_desired_roles": False,
            "onboarding_complete": False,
            "seed_skills": [],
            "completion_percent": 0,
        }
    extra = profile.extra or {}
    skills = list(profile.skills or [])
    tech = list(profile.technologies or [])
    has_skills = bool(skills or tech)
    has_resume = bool(extra.get("resume_uploaded_at"))
    has_roles = bool(profile.desired_roles)
    skipped = bool(extra.get("onboarding_skipped_at"))
    completed_flag = bool(extra.get("onboarding_completed_at"))
    complete = bool(completed_flag or skipped or (has_skills and has_resume) or (has_skills and has_roles))

    checks = [
        has_skills,
        has_resume or skipped,
        has_roles or skipped,
        bool(profile.remote_preference),
    ]
    pct = int(round(100 * sum(1 for c in checks if c) / len(checks)))
    seed = [s for s in (extra.get("seed_skills") or []) if s][:4]
    if not seed:
        seed = (tech or skills)[:2]

    return {
        "has_profile": True,
        "has_skills": has_skills,
        "has_resume": has_resume,
        "has_desired_roles": has_roles,
        "onboarding_complete": complete,
        "seed_skills": seed,
        "completion_percent": pct,
        "resume_uploaded_at": extra.get("resume_uploaded_at"),
    }
