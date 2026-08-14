"""Deterministic apply kit: field card, ATS estimate, skill-gap catalog.

We never submit applications. Copy is for the candidate to paste into the
employer's ATS.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

from app.models.job import Job
from app.models.user import Profile, User

_CATALOG_PATH = Path(__file__).resolve().parents[2] / "data" / "skill_paths.json"
_CATALOG: dict[str, Any] | None = None

DEFAULT_CHECKLIST = {
    "resume_ready": False,
    "tailored": False,
    "fields_copied": False,
    "submitted_on_ats": False,
    "followed_up": False,
}

_ATS_MINUTES = (
    (("workday",), (20, 35), "Workday forms are long and often need work history retyped."),
    (("greenhouse",), (8, 14), "Greenhouse is usually a resume upload plus a few questions."),
    (("lever",), (8, 12), "Lever is typically short if your resume parses cleanly."),
    (("ashby",), (6, 12), "Ashby is usually a compact form."),
    (("smartrecruiters",), (10, 18), "SmartRecruiters often has extra screening questions."),
    (("workable",), (8, 15), "Workable length varies; have LinkedIn ready."),
    (("bamboohr",), (10, 16), "BambooHR often repeats contact and work authorization."),
    (("personio",), (10, 18), "Personio can include GDPR and eligibility screens."),
)


def load_skill_catalog() -> dict[str, Any]:
    global _CATALOG
    if _CATALOG is None:
        _CATALOG = json.loads(_CATALOG_PATH.read_text(encoding="utf-8"))
    return _CATALOG


def ats_time_estimate(apply_url: Optional[str], source: Optional[str] = None) -> dict[str, Any]:
    blob = f"{apply_url or ''} {source or ''}".lower()
    host = ""
    if apply_url:
        host = urlparse(apply_url).netloc.lower()
    hay = f"{host} {blob}"
    for needles, (lo, hi), note in _ATS_MINUTES:
        if any(n in hay for n in needles):
            return {
                "host": host or source or "unknown",
                "minutes_low": lo,
                "minutes_high": hi,
                "note": note,
            }
    return {
        "host": host or source or "unknown",
        "minutes_low": 10,
        "minutes_high": 20,
        "note": "Budget a focused block. We never submit the form for you.",
    }


def field_card(user: User, profile: Optional[Profile]) -> dict[str, str]:
    extra = (profile.extra if profile else None) or {}
    years = extra.get("years_experience") or extra.get("honest_years") or ""
    auth = extra.get("work_authorization") or (
        "Open to remote; confirm eligibility on the employer form"
        if profile and profile.pakistan_friendly
        else ""
    )
    return {
        "full_name": (user.full_name or "").strip(),
        "email": user.email,
        "linkedin": str(extra.get("linkedin") or extra.get("linkedin_url") or ""),
        "github": str(extra.get("github") or extra.get("github_url") or ""),
        "honest_years": str(years),
        "work_authorization": str(auth),
        "location_preference": (profile.location_preference if profile else None) or "",
        "experience_level": (profile.experience_level if profile else None) or "",
    }


def _skill_gaps(job: Job, profile: Optional[Profile]) -> list[str]:
    job_skills = {
        s.strip().lower()
        for s in (*(job.skills or []), *(job.tech_tags or []))
        if s and str(s).strip()
    }
    have = {
        s.strip().lower()
        for s in (*((profile.skills if profile else None) or []), *((profile.technologies if profile else None) or []))
        if s and str(s).strip()
    }
    return sorted(job_skills - have)[:8]


def skill_gap_path(gaps: list[str]) -> dict[str, Any]:
    catalog = load_skill_catalog()
    for gap in gaps:
        key = re.sub(r"[^a-z0-9]+", "", gap.lower())
        for cat_key, payload in catalog.items():
            if cat_key == "default":
                continue
            if cat_key in gap.lower() or key == cat_key:
                return {"skill": gap, **payload}
    return {"skill": gaps[0] if gaps else "core", **catalog["default"]}


def short_answers(user: User, profile: Optional[Profile], job: Job) -> list[dict[str, str]]:
    card = field_card(user, profile)
    skills = ", ".join(((profile.technologies if profile else None) or (profile.skills if profile else None) or [])[:6])
    level = card["experience_level"] or "early-career"
    name = card["full_name"] or "I"
    return [
        {
            "prompt": "Why this role?",
            "answer": (
                f"{name} is looking for a {level} role as {job.title} at {job.company_name}. "
                f"I want to contribute on the stack listed in this posting and learn from the team."
            )[:400],
        },
        {
            "prompt": "Relevant experience",
            "answer": (
                f"Skills I can honestly claim: {skills or 'see resume'}. "
                "I will not invent job titles or dates that are not on my resume."
            )[:400],
        },
        {
            "prompt": "Work authorization / location",
            "answer": (
                card["work_authorization"]
                or card["location_preference"]
                or "I will complete the employer’s eligibility questions truthfully on their form."
            )[:400],
        },
        {
            "prompt": "Notice period / start date",
            "answer": "I can confirm start date on the employer form. I am applying as myself — Remote Atlas does not submit this application.",
        },
        {
            "prompt": "Salary / compensation",
            "answer": "Happy to discuss a range after learning more about the role’s scope. I will enter this on the ATS if required.",
        },
        {
            "prompt": "How did you hear about us?",
            "answer": f"Company career page / ATS listing indexed by Remote Atlas ({job.source}). I am applying directly on your site.",
        },
    ]


def cover_note(user: User, profile: Optional[Profile], job: Job) -> str:
    skills = ", ".join(((profile.technologies if profile else None) or [])[:5]) or "the skills on my resume"
    name = (user.full_name or "the applicant").split()[0]
    text = (
        f"Hello {job.company_name} hiring team — I’m {name}, applying for {job.title}. "
        f"I’m an early-career candidate focused on {skills}. "
        f"This note is grounded in my resume and this posting; I have not invented experience. "
        f"I will submit the official application on your career site myself."
    )
    words = text.split()
    if len(words) > 120:
        text = " ".join(words[:120])
    return text


def build_apply_kit(user: User, job: Job) -> dict[str, Any]:
    profile = user.profile
    gaps = _skill_gaps(job, profile)
    years = getattr(job, "years_required_min", None)
    skip_reason = None
    if years is not None and years >= 3:
        skip_reason = f"This listing asks for {years}+ years. Treat as stretch or skip."
    if (job.career_stage or "") in {"senior", "mid"}:
        skip_reason = skip_reason or "Title is mid/senior — not junior-eligible by default."
    return {
        "disclaimer": "We never submit applications for you.",
        "job_id": job.id,
        "title": job.title,
        "company_name": job.company_name,
        "apply_url": job.apply_url,
        "field_card": field_card(user, profile),
        "short_answers": short_answers(user, profile, job),
        "cover_note": cover_note(user, profile, job),
        "ats_estimate": ats_time_estimate(job.apply_url, job.source),
        "skill_gaps": gaps,
        "skill_path": skill_gap_path(gaps),
        "years_required_min": years,
        "junior_eligible": bool(getattr(job, "junior_eligible", False)),
        "skip_reason": skip_reason,
        "checklist": dict(DEFAULT_CHECKLIST),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
