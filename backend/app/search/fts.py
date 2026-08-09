from __future__ import annotations

from typing import Optional

from sqlalchemy import Select, and_, case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import Job
from app.pipeline.freshness import freshness_cutoff


def _base_fresh_query(days: int | None = None) -> Select:
    cutoff = freshness_cutoff(days)
    return (
        select(Job)
        .where(Job.is_active.is_(True))
        .where(
            or_(
                Job.posted_at >= cutoff,
                and_(Job.posted_at.is_(None), Job.first_seen_at >= cutoff),
            )
        )
    )


def _trust_case():
    return case(
        (
            Job.source.in_(
                [
                    "greenhouse",
                    "lever",
                    "ashby",
                    "smartrecruiters",
                    "recruitee",
                    "workable",
                    "personio",
                    "teamtailor",
                    "breezy",
                    "workday",
                    "bamboohr",
                ]
            ),
            0,
        ),
        (
            Job.source.in_(
                [
                    "weworkremotely",
                    "remotive",
                    "remoteok",
                    "jobicy",
                    "himalayas",
                    "arbeitnow",
                    "remotejobsorg",
                ]
            ),
            1,
        ),
        else_=2,
    )


async def search_jobs(
    session: AsyncSession,
    *,
    q: Optional[str] = None,
    workplace: Optional[str] = None,
    city: Optional[str] = None,
    country: Optional[str] = None,
    company: Optional[str] = None,
    employment_type: Optional[str] = None,
    posted_within: Optional[int] = None,
    pakistan_friendly: bool = False,
    skills: Optional[list[str]] = None,
    career_stage: Optional[str] = None,
    source: Optional[str] = None,
    sort: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[tuple[Job, float]], int]:
    settings = get_settings()
    page = max(1, page)
    page_size = min(max(1, page_size), 100)
    offset = (page - 1) * page_size

    effective_days = min(posted_within or settings.freshness_days, settings.freshness_days)
    stmt = _base_fresh_query(effective_days)

    trust_case = _trust_case()
    posted_certainty = case((Job.posted_at.is_not(None), 0), else_=1)
    mode = (sort or "relevance").lower().strip()
    if mode not in {"newest", "relevance", "company"}:
        mode = "relevance"

    if q and mode == "relevance":
        ts_query = func.websearch_to_tsquery("english", q)
        stmt = stmt.where(Job.search_tsv.op("@@")(ts_query))
        age_days = func.greatest(
            func.extract(
                "epoch",
                func.now() - func.coalesce(Job.posted_at, Job.first_seen_at),
            )
            / 86400.0,
            0.0,
        )
        freshness_boost = func.exp(-age_days / 7.0)
        rank_expr = func.ts_rank_cd(Job.search_tsv, ts_query) * freshness_boost
        stmt = stmt.order_by(
            rank_expr.desc(),
            trust_case.asc(),
            posted_certainty.asc(),
            Job.posted_at.desc().nullslast(),
        )
    elif mode == "company":
        if q:
            ts_query = func.websearch_to_tsquery("english", q)
            stmt = stmt.where(Job.search_tsv.op("@@")(ts_query))
        stmt = stmt.order_by(
            func.lower(Job.company_name).asc(),
            Job.posted_at.desc().nullslast(),
            Job.id.asc(),
        )
    else:
        # newest
        if q:
            ts_query = func.websearch_to_tsquery("english", q)
            stmt = stmt.where(Job.search_tsv.op("@@")(ts_query))
        stmt = stmt.order_by(
            Job.posted_at.desc().nullslast(),
            Job.first_seen_at.desc(),
            trust_case.asc(),
            posted_certainty.asc(),
        )

    if workplace:
        stmt = stmt.where(Job.workplace_type == workplace.lower())

    if city:
        stmt = stmt.where(Job.location_raw.ilike(f"%{city}%"))

    if country:
        stmt = stmt.where(Job.location_raw.ilike(f"%{country}%"))

    if company:
        stmt = stmt.where(Job.company_name.ilike(f"%{company}%"))

    if employment_type:
        stmt = stmt.where(Job.employment_type.ilike(f"%{employment_type}%"))

    if career_stage:
        stage = career_stage.lower()
        if stage in {"fresh", "fresh_graduate", "new_grad", "entry"}:
            stage = "junior"
        stmt = stmt.where(Job.career_stage == stage)

    if source:
        stmt = stmt.where(Job.source == source.lower())

    if skills:
        normalized = [s.strip().lower() for s in skills if s.strip()]
        if normalized:
            stmt = stmt.where(Job.skills.overlap(normalized) | Job.tech_tags.overlap(normalized))

    if pakistan_friendly:
        stmt = stmt.where(Job.pakistan_friendly.is_(True))

    count_stmt = select(func.count()).select_from(stmt.order_by(None).subquery())
    total = (await session.execute(count_stmt)).scalar_one()

    result = await session.execute(stmt.offset(offset).limit(page_size))
    jobs = list(result.scalars().all())

    scored: list[tuple[Job, float]] = []
    for idx, job in enumerate(jobs):
        score = float(page_size - idx)
        scored.append((job, score))
    return scored, int(total)
