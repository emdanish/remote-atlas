from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Literal

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.ai.provider import AIProviderError, chat_completion
from app.auth.deps import get_current_user
from app.config import get_settings
from app.db.session import get_db
from app.matching.fit_brief import build_fit_brief
from app.matching.scoring import (
    build_search_query,
    profile_onboarding_state,
    score_job_breakdown,
)
from app.models import Job, Notification, User
from app.pipeline.enrich import extract_skills
from app.pipeline.freshness import is_fresh
from app.pipeline.source_trust import source_kind, source_kind_label
from app.schemas.auth import OnboardingOut
from app.schemas.job import JobOut
from app.search.hybrid import hybrid_search

router = APIRouter(tags=["phase3"])


class MatchResponse(BaseModel):
    total: int
    freshness_days: int
    results: list[JobOut]
    empty_reason: str | None = None
    profile_complete: bool = False


class NotificationOut(BaseModel):
    id: int
    title: str
    body: str | None = None
    link: str | None = None
    is_read: bool
    created_at: datetime


class ResumeParseResponse(BaseModel):
    skills: list[str]
    technologies: list[str]
    experience_level: str
    summary: str
    raw_chars: int
    seed_skills: list[str] = Field(default_factory=list)
    onboarding: OnboardingOut | None = None


class OnboardingCompleteRequest(BaseModel):
    skipped: bool = False
    seed_skills: list[str] | None = None


class FitBriefResponse(BaseModel):
    job_id: int
    score: float
    breakdown: dict[str, Any]
    verdict: str
    narrative: str
    tips: list[str]
    provider: str
    apply_url: str | None = None
    career_page_url: str | None = None


def _profile_context(profile) -> dict[str, Any]:
    from app.matching.skill_tags import profile_skill_universe

    skills: set[str] = set()
    level = "junior"
    remote_pref = "remote"
    desired_roles: list[str] = []
    cities: list[str] = []
    location_preference: str | None = None
    prefer_pakistan = False
    if profile:
        skills = profile_skill_universe(profile.skills, profile.technologies)
        level = profile.experience_level or "junior"
        remote_pref = profile.remote_preference or "remote"
        desired_roles = profile.desired_roles or []
        cities = profile.cities or []
        location_preference = profile.location_preference
        prefer_pakistan = bool(profile.pakistan_friendly)
    return {
        "skills": skills,
        "level": level,
        "remote_pref": remote_pref,
        "desired_roles": desired_roles,
        "cities": cities,
        "location_preference": location_preference,
        "prefer_pakistan": prefer_pakistan,
    }


@router.get("/recommendations", response_model=MatchResponse)
async def recommendations(
    page: int = 1,
    page_size: int = 20,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MatchResponse:
    settings = get_settings()
    result = await db.execute(
        select(User).options(selectinload(User.profile)).where(User.id == user.id)
    )
    user = result.scalar_one()
    profile = user.profile
    ctx = _profile_context(profile)
    skills = ctx["skills"]
    onboarding = profile_onboarding_state(profile)

    if not skills and not (profile and profile.desired_roles):
        return MatchResponse(
            total=0,
            freshness_days=settings.freshness_days,
            results=[],
            empty_reason="Add skills or a resume so we can rank the catalogue for you.",
            profile_complete=bool(onboarding.get("onboarding_complete")),
        )

    q = build_search_query(
        desired_roles=ctx["desired_roles"],
        skills=skills,
    )

    # Generous catalogue pull: do NOT hard-filter pakistan_friendly or skill tags in FTS.
    # Workplace is soft unless user only wants onsite.
    workplace = None
    if ctx["remote_pref"] == "onsite":
        workplace = "onsite"
    elif ctx["remote_pref"] == "hybrid":
        workplace = "hybrid"

    candidate_jobs: list[tuple[Job, float]] = []
    total = 0
    queries = [
        q,
        build_search_query(desired_roles=None, skills=skills),
        "software engineer OR developer OR backend OR frontend OR fullstack",
        "",
    ]
    seen_q: set[str] = set()
    try:
        for query in queries:
            key = query.strip().lower()
            if key in seen_q:
                continue
            seen_q.add(key)
            scored, tot = await hybrid_search(
                db,
                q=query,
                workplace=workplace,
                pakistan_friendly=False,
                skills=None,
                career_stage=None,
                sort="newest" if not query.strip() else "relevance",
                page=1,
                page_size=min(100, max(page_size * 5, 60)),
            )
            total = max(total, tot)
            by_id = {j.id: (j, float(s or 0)) for j, s in candidate_jobs}
            for job, hs in scored:
                prev = by_id.get(job.id)
                if not prev or float(hs or 0) > prev[1]:
                    by_id[job.id] = (job, float(hs or 0))
            candidate_jobs = list(by_id.values())
            if len(candidate_jobs) >= 40:
                break
    except Exception:  # noqa: BLE001
        return MatchResponse(
            total=0,
            freshness_days=settings.freshness_days,
            results=[],
            empty_reason="Matches are temporarily unavailable. Browse Jobs while we recover.",
            profile_complete=bool(onboarding.get("onboarding_complete")),
        )

    reranked: list[tuple[Job, Any]] = []
    for job, hybrid_s in candidate_jobs:
        bd = score_job_breakdown(
            job,
            skills=skills,
            level=ctx["level"],
            remote_pref=ctx["remote_pref"],
            desired_roles=ctx["desired_roles"],
            cities=ctx["cities"],
            location_preference=ctx["location_preference"],
            pakistan_friendly=ctx["prefer_pakistan"],
            hybrid_score=float(hybrid_s or 0),
        )
        reranked.append((job, bd))
    # Keep even modest scores — prefer skill hits, but never empty if catalogue has roles
    reranked.sort(key=lambda x: (x[1].total, x[1].skill), reverse=True)
    if not reranked:
        empty_reason = (
            "No jobs in the fresh catalogue yet. Check back after ingestion, or browse Jobs."
        )
        return MatchResponse(
            total=0,
            freshness_days=settings.freshness_days,
            results=[],
            empty_reason=empty_reason,
            profile_complete=bool(onboarding.get("onboarding_complete")),
        )

    start = (max(1, page) - 1) * page_size
    page_rows = reranked[start : start + page_size]
    results: list[JobOut] = []
    for job, bd in page_rows:
        if not is_fresh(job, settings.freshness_days):
            continue
        item = JobOut.model_validate(job)
        item.score = float(bd.total)
        item.skills = job.skills or []
        item.tech_tags = job.tech_tags or []
        item.source_kind = source_kind(job.source)
        item.source_kind_label = source_kind_label(job.source)
        item.match_reasons = bd.reasons or (["Catalogue role"] if bd.total < 15 else [])
        item.match_breakdown = bd.as_dict()
        if item.description_text and len(item.description_text) > 400:
            item.description_text = item.description_text[:400] + "…"
        results.append(item)

    empty_reason = None
    if not results:
        empty_reason = (
            "No strong matches in the fresh catalogue yet. "
            "Try pulse alerts or broaden desired roles."
        )
    return MatchResponse(
        total=max(total, len(reranked)),
        freshness_days=settings.freshness_days,
        results=results,
        empty_reason=empty_reason,
        profile_complete=bool(onboarding.get("onboarding_complete")),
    )


@router.get("/jobs/{job_id}/fit-brief", response_model=FitBriefResponse)
async def job_fit_brief(
    job_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FitBriefResponse:
    """Atlas Fit Brief — explainable apply decision for this role."""
    result = await db.execute(
        select(User).options(selectinload(User.profile)).where(User.id == user.id)
    )
    user = result.scalar_one()
    job = (
        await db.execute(select(Job).where(Job.id == job_id, Job.is_active.is_(True)))
    ).scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    ctx = _profile_context(user.profile)
    if not ctx["skills"]:
        raise HTTPException(
            status_code=400,
            detail="Add skills or upload a resume to unlock Fit Brief.",
        )
    brief = await build_fit_brief(
        job,
        skills=ctx["skills"],
        level=ctx["level"],
        remote_pref=ctx["remote_pref"],
        desired_roles=ctx["desired_roles"],
        cities=ctx["cities"],
        location_preference=ctx["location_preference"],
        pakistan_friendly=ctx["prefer_pakistan"],
        use_ai=True,
    )
    return FitBriefResponse(**brief)


@router.post("/onboarding/complete", response_model=OnboardingOut)
async def complete_onboarding(
    body: OnboardingCompleteRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> OnboardingOut:
    result = await db.execute(
        select(User).options(selectinload(User.profile)).where(User.id == user.id)
    )
    user = result.scalar_one()
    if not user.profile:
        raise HTTPException(status_code=400, detail="Profile missing")
    extra = dict(user.profile.extra or {})
    now = datetime.now(timezone.utc).isoformat()
    if body.skipped:
        extra["onboarding_skipped_at"] = now
    else:
        extra["onboarding_completed_at"] = now
    if body.seed_skills:
        extra["seed_skills"] = [s.strip().lower() for s in body.seed_skills if s.strip()][:4]
    elif not extra.get("seed_skills"):
        techs = list(user.profile.technologies or user.profile.skills or [])
        extra["seed_skills"] = [str(s).lower() for s in techs[:2]]
    user.profile.extra = extra
    await db.commit()
    await db.refresh(user.profile)
    return OnboardingOut(**profile_onboarding_state(user.profile))


@router.get("/onboarding/status", response_model=OnboardingOut)
async def onboarding_status(
    user: User = Depends(get_current_user),
) -> OnboardingOut:
    return OnboardingOut(**profile_onboarding_state(user.profile))


@router.post("/resume/parse", response_model=ResumeParseResponse)
async def parse_resume(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ResumeParseResponse:
    raw = await file.read()
    if len(raw) > 2_000_000:
        raise HTTPException(status_code=400, detail="Resume too large (max 2MB)")
    name = file.filename or "resume.txt"
    try:
        from app.resume.extract import ExtractError, extract_text
        from app.resume.storage import (
            sha256_bytes,
            store_resume_bytes,
        )
        from app.models import UserResume
        from sqlalchemy import update as sa_update

        text = extract_text(raw, name)
    except Exception as exc:  # noqa: BLE001
        msg = str(exc) or "Could not parse resume"
        if "unsupported" in msg.lower() or "read" in msg.lower() or "short" in msg.lower():
            raise HTTPException(status_code=400, detail=msg) from exc
        # legacy path for plain text
        try:
            text = raw.decode("utf-8", errors="ignore")
            text = re.sub(r"\s+", " ", text).strip()
            if len(text) < 40:
                raise HTTPException(status_code=400, detail="Resume text too short / unreadable")
        except HTTPException:
            raise
        except Exception as exc2:  # noqa: BLE001
            raise HTTPException(status_code=400, detail="Unsupported resume format") from exc2

    text = re.sub(r"\s+", " ", text).strip()
    if len(text) < 40:
        raise HTTPException(status_code=400, detail="Resume text too short / unreadable")

    # Persist file for later "Tailor My Resume" (original kept immutable)
    try:
        from app.models import UserResume
        from app.resume.storage import sha256_bytes, store_resume_bytes
        from sqlalchemy import update as sa_update

        await db.execute(
            sa_update(UserResume)
            .where(UserResume.user_id == user.id, UserResume.is_primary.is_(True))
            .values(is_primary=False)
        )
        path = store_resume_bytes(user.id, name, raw)
        db.add(
            UserResume(
                user_id=user.id,
                filename=name[:500],
                content_type=(file.content_type or "application/octet-stream")[:120],
                storage_path=str(path),
                byte_size=len(raw),
                sha256=sha256_bytes(raw),
                extracted_text=text,
                is_primary=True,
            )
        )
        await db.flush()
    except Exception:  # noqa: BLE001
        pass

    skills = extract_skills(text)
    technologies: list[str] = []
    summary = ""
    experience_level = "junior"
    try:
        ai = await chat_completion(
            system=(
                "Extract a concise JSON profile from a developer resume. "
                "Return ONLY JSON with keys: "
                '{"skills":[],"technologies":[],"experience_level":"internship|junior|mid|senior","summary":""}. '
                "STRICT separation: "
                "technologies = concrete languages, frameworks, libraries, databases, cloud, tools "
                "(e.g. python, react, postgresql, docker, fastapi). "
                "skills = professional capabilities and methods "
                "(e.g. full-stack development, system design, agile collaboration, prompt engineering, devops practices). "
                "Do NOT put the same strings in both arrays. Prefer short lowercase labels."
            ),
            user=text[:8000],
            temperature=0.1,
            max_tokens=700,
        )
        import json

        m = re.search(r"\{.*\}", ai, re.S)
        if m:
            payload = json.loads(m.group(0))
            ai_skills = [str(s).lower().strip() for s in payload.get("skills", []) if s]
            ai_techs = [str(t).lower().strip() for t in payload.get("technologies", []) if t]
            from app.matching.skill_tags import partition_skills_and_technologies

            skills, technologies = partition_skills_and_technologies(
                skills, ai_skills, ai_techs
            )
            experience_level = payload.get("experience_level") or experience_level
            summary = payload.get("summary") or ""
    except (AIProviderError, Exception):
        summary = "Parsed with skill lexicon only (AI unavailable)."
        from app.matching.skill_tags import partition_skills_and_technologies

        skills, technologies = partition_skills_and_technologies(skills)

    if not technologies and skills:
        from app.matching.skill_tags import partition_skills_and_technologies

        skills, technologies = partition_skills_and_technologies(skills)
    if not skills and not technologies:
        from app.matching.skill_tags import partition_skills_and_technologies

        skills, technologies = partition_skills_and_technologies(extract_skills(text))

    seed_skills = [s for s in (technologies or skills) if s][:4]

    result = await db.execute(
        select(User).options(selectinload(User.profile)).where(User.id == user.id)
    )
    user = result.scalar_one()
    if user.profile:
        user.profile.skills = skills
        user.profile.technologies = technologies
        user.profile.experience_level = experience_level
        if summary:
            user.profile.bio = summary[:2000]
        extra = {**(user.profile.extra or {})}
        extra["resume_uploaded_at"] = datetime.now(timezone.utc).isoformat()
        extra["seed_skills"] = seed_skills
        extra["onboarding_completed_at"] = datetime.now(timezone.utc).isoformat()
        user.profile.extra = extra
        await db.commit()
        await db.refresh(user.profile)

    return ResumeParseResponse(
        skills=skills,
        technologies=technologies,
        experience_level=experience_level,
        summary=summary,
        raw_chars=len(text),
        seed_skills=seed_skills,
        onboarding=OnboardingOut(**profile_onboarding_state(user.profile)),
    )


@router.get("/notifications", response_model=list[NotificationOut])
async def list_notifications(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[NotificationOut]:
    rows = (
        await db.execute(
            select(Notification)
            .where(Notification.user_id == user.id)
            .order_by(Notification.created_at.desc())
            .limit(50)
        )
    ).scalars().all()
    return [
        NotificationOut(
            id=n.id,
            title=n.title,
            body=n.body,
            link=n.link,
            is_read=n.is_read,
            created_at=n.created_at,
        )
        for n in rows
    ]


@router.post("/notifications/mark-read")
async def mark_notifications_read(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    result = await db.execute(
        update(Notification)
        .where(Notification.user_id == user.id, Notification.is_read.is_(False))
        .values(is_read=True)
        .returning(Notification.id)
    )
    updated = len(result.scalars().all())
    await db.commit()
    return {"updated": updated}


@router.patch("/notifications/{notification_id}/read")
async def mark_notification_read(
    notification_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    result = await db.execute(
        update(Notification)
        .where(Notification.id == notification_id, Notification.user_id == user.id)
        .values(is_read=True)
        .returning(Notification.id)
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Notification not found")
    await db.commit()
    return {"id": notification_id, "is_read": True}


@router.post("/notifications/generate-matches", response_model=list[NotificationOut])
async def generate_match_notifications(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[NotificationOut]:
    match = await recommendations(page=1, page_size=5, user=user, db=db)
    created: list[Notification] = []
    for job in match.results[:5]:
        link = f"/jobs/{job.id}"
        exists = (
            await db.execute(
                select(Notification.id).where(
                    Notification.user_id == user.id,
                    Notification.link == link,
                )
            )
        ).scalar_one_or_none()
        if exists:
            continue
        score_s = f"{job.score:.0f}" if job.score is not None else "—"
        n = Notification(
            user_id=user.id,
            title=f"Fresh match: {job.title}",
            body=f"{job.company_name} · fit {score_s} · {job.workplace_type}",
            link=link,
            is_read=False,
        )
        db.add(n)
        created.append(n)
    await db.commit()
    for n in created:
        await db.refresh(n)
    return [
        NotificationOut(
            id=n.id,
            title=n.title,
            body=n.body,
            link=n.link,
            is_read=n.is_read,
            created_at=n.created_at,
        )
        for n in created
    ]


class ApplicationUpdate(BaseModel):
    status: Literal["saved", "applied", "interview", "offer", "rejected"]
    notes: str | None = Field(default=None, max_length=5000)


@router.patch("/applications/{saved_id}")
async def update_application(
    saved_id: int,
    body: ApplicationUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    from app.models import SavedJob

    saved = (
        await db.execute(
            select(SavedJob).where(SavedJob.id == saved_id, SavedJob.user_id == user.id)
        )
    ).scalar_one_or_none()
    if not saved:
        raise HTTPException(status_code=404, detail="Application not found")
    saved.status = body.status
    if body.notes is not None:
        saved.notes = body.notes
    await db.commit()
    return {"id": saved.id, "status": saved.status, "notes": saved.notes}
