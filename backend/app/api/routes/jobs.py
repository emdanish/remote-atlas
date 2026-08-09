from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.session import get_db
from app.models import Job
from app.pipeline.freshness import is_fresh
from app.pipeline.source_trust import source_kind, source_kind_label
from app.schemas import JobOut, JobSearchResponse
from app.search.fts import search_jobs
from app.search.hybrid import hybrid_search
from app.search.intent import parse_intent
from app.security import enforce_rate_limit

router = APIRouter(prefix="/jobs", tags=["jobs"])


def _job_out(job: Job, score: float | None = None) -> JobOut:
    item = JobOut.model_validate(job)
    item.skills = job.skills or []
    item.tech_tags = job.tech_tags or []
    item.source_kind = source_kind(job.source)
    item.source_kind_label = source_kind_label(job.source)
    if score is not None:
        item.score = score
    return item


@router.get("/search", response_model=JobSearchResponse)
async def jobs_search(
    request: Request,
    q: Optional[str] = Query(None, max_length=200, description="Full-text / semantic query"),
    workplace: Optional[Literal["remote", "hybrid", "onsite", "unknown"]] = Query(None),
    city: Optional[str] = Query(None, max_length=100, description="e.g. Lahore, Karachi, Islamabad"),
    country: Optional[str] = Query(None, max_length=100),
    company: Optional[str] = Query(None, max_length=160),
    employment_type: Optional[str] = Query(None, max_length=80),
    posted_within: Optional[int] = Query(None, ge=1, le=30),
    pakistan_friendly: bool = Query(False, description="Remote roles likely open to PK"),
    skills: Optional[str] = Query(None, description="Comma-separated skills"),
    career_stage: Optional[str] = Query(
        None, description="internship|junior|mid|senior|unknown"
    ),
    source: Optional[str] = Query(None, max_length=64),
    sort: Optional[Literal["newest", "relevance", "company"]] = Query(
        "newest",
        description="newest | relevance | company",
    ),
    hybrid: bool = Query(True, description="Use hybrid search when embeddings available"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> JobSearchResponse:
    await enforce_rate_limit(request, "job-search", limit=120)
    settings = get_settings()
    skill_list = [s.strip() for s in skills.split(",")] if skills else None
    hints = parse_intent(
        q,
        workplace=workplace,
        career_stage=career_stage,
        pakistan_friendly=pakistan_friendly,
        skills=skill_list,
    )
    workplace = hints.workplace or workplace
    career_stage = hints.career_stage or career_stage
    pakistan_friendly = hints.pakistan_friendly or pakistan_friendly
    skill_list = hints.skills or skill_list
    q = hints.cleaned_q or q
    sort_mode = sort or "newest"
    # Relevance + hybrid only when user asks for best match (or leaves sort as relevance)
    use_hybrid = bool(q and hybrid and sort_mode == "relevance")
    if use_hybrid:
        scored, total = await hybrid_search(
            db,
            q=q,
            workplace=workplace,
            city=city,
            country=country,
            company=company,
            employment_type=employment_type,
            posted_within=posted_within,
            pakistan_friendly=pakistan_friendly,
            skills=skill_list,
            career_stage=career_stage,
            source=source,
            sort=sort_mode,
            page=page,
            page_size=page_size,
        )
    else:
        scored, total = await search_jobs(
            db,
            q=q,
            workplace=workplace,
            city=city,
            country=country,
            company=company,
            employment_type=employment_type,
            posted_within=posted_within,
            pakistan_friendly=pakistan_friendly,
            skills=skill_list,
            career_stage=career_stage,
            source=source,
            sort=sort_mode,
            page=page,
            page_size=page_size,
        )

    results: list[JobOut] = []
    for job, score in scored:
        # Configured freshness gate (defense in depth)
        if not is_fresh(job, settings.freshness_days):
            continue
        item = _job_out(job, score)
        # Keep list payload lighter
        if item.description_text and len(item.description_text) > 500:
            item.description_text = item.description_text[:500] + "…"
        results.append(item)

    return JobSearchResponse(
        total=total,
        page=page,
        page_size=page_size,
        freshness_days=settings.freshness_days,
        results=results,
    )


@router.get("/{job_id}", response_model=JobOut)
async def job_detail(job_id: int, db: AsyncSession = Depends(get_db)) -> JobOut:
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return _job_out(job)
