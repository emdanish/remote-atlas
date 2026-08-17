from __future__ import annotations

from typing import Optional

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import defer

from app.config import get_settings
from app.models import Job
from app.pipeline.freshness import freshness_cutoff
from app.search.embeddings import embed_texts
from app.search.fts import search_jobs
from app.search.intent import parse_intent
from app.pipeline.seniority import seniority_query


def reciprocal_rank_fusion(
    ranked_lists: list[list[int]],
    k: int = 60,
) -> list[tuple[int, float]]:
    scores: dict[int, float] = {}
    for ranked in ranked_lists:
        for rank, job_id in enumerate(ranked, start=1):
            scores[job_id] = scores.get(job_id, 0.0) + 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda x: x[1], reverse=True)


async def hybrid_search(
    session: AsyncSession,
    *,
    q: str,
    workplace: Optional[str] = None,
    city: Optional[str] = None,
    country: Optional[str] = None,
    company: Optional[str] = None,
    employment_type: Optional[str] = None,
    posted_within: Optional[int] = None,
    pakistan_friendly: bool = False,
    skills: Optional[list[str]] = None,
    career_stage: Optional[str] = None,
    junior_eligible: bool = False,
    source: Optional[str] = None,
    sort: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[tuple[Job, float]], int]:
    """FTS + vector RRF when embeddings available; otherwise FTS-only."""
    settings = get_settings()
    mode = (sort or "relevance").lower().strip()
    if mode not in {"newest", "relevance", "company"}:
        mode = "relevance"

    # Non-relevance sorts use pure FTS (faster, predictable ordering)
    if mode != "relevance":
        return await search_jobs(
            session,
            q=q,
            workplace=workplace,
            city=city,
            country=country,
            company=company,
            employment_type=employment_type,
            posted_within=posted_within,
            pakistan_friendly=pakistan_friendly,
            skills=skills,
            career_stage=career_stage,
            junior_eligible=junior_eligible,
            source=source,
            sort=mode,
            page=page,
            page_size=page_size,
        )

    hints = parse_intent(
        q,
        workplace=workplace,
        career_stage=career_stage,
        pakistan_friendly=pakistan_friendly,
        skills=skills,
    )
    workplace = hints.workplace or workplace
    career_stage = hints.career_stage or career_stage
    pakistan_friendly = hints.pakistan_friendly or pakistan_friendly
    skills = hints.skills or skills
    q = hints.cleaned_q or q

    fts_results, fts_total = await search_jobs(
        session,
        q=q,
        workplace=workplace,
        city=city,
        country=country,
        company=company,
        employment_type=employment_type,
        posted_within=posted_within,
        pakistan_friendly=pakistan_friendly,
        skills=skills,
        career_stage=career_stage,
        junior_eligible=junior_eligible,
        source=source,
        sort="relevance",
        page=1,
        page_size=50,
    )

    if not q.strip():
        return await search_jobs(
            session,
            q=q,
            workplace=workplace,
            city=city,
            country=country,
            company=company,
            employment_type=employment_type,
            posted_within=posted_within,
            pakistan_friendly=pakistan_friendly,
            skills=skills,
            career_stage=career_stage,
            junior_eligible=junior_eligible,
            source=source,
            sort="newest",
            page=page,
            page_size=page_size,
        )

    query_vecs = await embed_texts([q])
    if not query_vecs:
        start = (page - 1) * page_size
        end = start + page_size
        return fts_results[start:end], fts_total

    query_vec = query_vecs[0]
    from app.ai.provider import embedding_provider_name

    provider_name = embedding_provider_name()
    if not provider_name:
        start = (page - 1) * page_size
        end = start + page_size
        return fts_results[start:end], fts_total
    effective_days = min(posted_within or settings.freshness_days, settings.freshness_days)
    cutoff = freshness_cutoff(effective_days)

    filters = [
        "is_active = true",
        "embedding IS NOT NULL",
        "embedding_provider = :embedding_provider",
        "(posted_at >= :cutoff OR (posted_at IS NULL AND first_seen_at >= :cutoff))",
    ]
    params: dict = {"cutoff": cutoff, "embedding_provider": provider_name}
    if workplace:
        filters.append("workplace_type = :workplace")
        params["workplace"] = workplace.lower()
    if city:
        filters.append("location_raw ILIKE :city")
        params["city"] = f"%{city}%"
    if country:
        filters.append("location_raw ILIKE :country")
        params["country"] = f"%{country}%"
    if company:
        filters.append("company_name ILIKE :company")
        params["company"] = f"%{company}%"
    if employment_type:
        filters.append("employment_type ILIKE :employment_type")
        params["employment_type"] = f"%{employment_type}%"
    use_eligible, exact_stage = seniority_query(
        career_stage, junior_eligible=junior_eligible
    )
    if use_eligible:
        filters.append("junior_eligible = true")
    elif exact_stage:
        filters.append("career_stage = :career_stage")
        params["career_stage"] = exact_stage
    if source:
        filters.append("source = :source")
        params["source"] = source.lower()
    if skills:
        filters.append("(skills && CAST(:skills AS varchar[]) OR tech_tags && CAST(:skills AS varchar[]))")
        params["skills"] = [s.strip().lower() for s in skills if s and s.strip()]
    if pakistan_friendly:
        filters.append("pakistan_friendly = true")

    where_sql = " AND ".join(filters)
    vec_sql = text(
        f"""
        SELECT id
        FROM jobs
        WHERE {where_sql}
        ORDER BY embedding <=> CAST(:qvec AS vector)
        LIMIT 120
        """
    )
    vec_literal = "[" + ",".join(str(float(x)) for x in query_vec) + "]"
    params["qvec"] = vec_literal
    vec_rows = (await session.execute(vec_sql, params)).fetchall()

    vec_ids: list[int] = []
    for row in vec_rows:
        jid = row[0]
        vec_ids.append(jid)
        if len(vec_ids) >= 50:
            break

    fts_ids = [job.id for job, _ in fts_results]
    fused = reciprocal_rank_fusion([fts_ids, vec_ids])
    if not fused:
        start = (page - 1) * page_size
        end = start + page_size
        return fts_results[start:end], fts_total

    start = (page - 1) * page_size
    page_slice = fused[start : start + page_size]
    page_ids = [jid for jid, _ in page_slice]
    if not page_ids:
        return await search_jobs(
            session,
            q=q,
            workplace=workplace,
            city=city,
            country=country,
            company=company,
            employment_type=employment_type,
            posted_within=posted_within,
            pakistan_friendly=pakistan_friendly,
            skills=skills,
            career_stage=career_stage,
            junior_eligible=junior_eligible,
            source=source,
            sort="relevance",
            page=page,
            page_size=page_size,
        )

    result = await session.execute(
        select(Job)
        .options(
            defer(Job.embedding),
            defer(Job.description_html),
            defer(Job.search_tsv),
        )
        .where(Job.id.in_(page_ids))
    )
    by_id = {j.id: j for j in result.scalars().all()}
    scored = [(by_id[jid], score) for jid, score in page_slice if jid in by_id]
    total = max(fts_total, len(fused))
    return scored, total
