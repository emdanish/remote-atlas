"""Public SEO taxonomy + title autocomplete endpoints."""

from __future__ import annotations

import re
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import case, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.session import get_db
from app.models import Job
from app.pipeline.freshness import freshness_cutoff
from app.schemas.job import (
    SeoTaxonomyItem,
    SeoTaxonomyListResponse,
    TitleSuggestion,
    TitleSuggestionsResponse,
)
from app.security import enforce_rate_limit
from app.seo.taxonomy import (
    MIN_COMPANY_JOBS,
    MIN_LOCATION_JOBS,
    MIN_SKILL_JOBS,
    SEO_CITIES,
    SEO_COUNTRIES,
    SEO_SKILL_MAP,
    TAG_TO_SKILL_SLUG,
    company_href,
    location_href,
    normalize_title_key,
    skill_href,
    slugify_company,
)

router = APIRouter(prefix="/jobs", tags=["jobs-seo"])


def _fresh_clause():
    settings = get_settings()
    cutoff = freshness_cutoff(settings.freshness_days)
    return (
        Job.is_active.is_(True),
        or_(
            Job.posted_at >= cutoff,
            (Job.posted_at.is_(None)) & (Job.first_seen_at >= cutoff),
        ),
    )


@router.get("/title-suggestions", response_model=TitleSuggestionsResponse)
async def title_suggestions(
    request: Request,
    q: str = Query(..., min_length=2, max_length=80),
    limit: int = Query(8, ge=1, le=15),
    db: AsyncSession = Depends(get_db),
) -> TitleSuggestionsResponse:
    """Autocomplete titles from fresh inventory (not a full job list)."""
    await enforce_rate_limit(request, "title-suggestions", limit=90)
    query = re.sub(r"\s+", " ", q.strip())
    if len(query) < 2:
        return TitleSuggestionsResponse(query=query, suggestions=[])

    active, fresh = _fresh_clause()
    q_lower = query.lower()
    like_prefix = f"{q_lower}%"
    like_word = f"% {q_lower}%"
    like_any = f"%{q_lower}%"

    score = (
        case(
            (func.lower(Job.title).like(like_prefix), 300),
            (func.lower(Job.title).like(like_word), 150),
            else_=50,
        )
        + func.least(func.count(Job.id), 80)
    ).label("score")

    result = await db.execute(
        select(
            func.min(Job.title).label("title"),
            func.count(Job.id).label("cnt"),
            score,
        )
        .where(active, fresh)
        .where(func.length(Job.title).between(5, 90))
        .where(func.lower(Job.title).like(like_any))
        .group_by(func.lower(func.trim(Job.title)))
        .order_by(score.desc(), func.count(Job.id).desc())
        .limit(limit * 3)
    )
    rows = result.all()

    merged: dict[str, tuple[str, int, float]] = {}
    for row in rows:
        display = normalize_title_key(row.title) or row.title.strip()
        key = display.lower()
        if len(key) < 3:
            continue
        prev = merged.get(key)
        sc = float(row.score or 0)
        cnt = int(row.cnt)
        if not prev or cnt > prev[1]:
            merged[key] = (display, cnt, sc)

    ordered = sorted(merged.values(), key=lambda x: (x[2], x[1]), reverse=True)[:limit]
    suggestions = [TitleSuggestion(title=t, count=c) for t, c, _ in ordered]
    return TitleSuggestionsResponse(query=query, suggestions=suggestions)


def _skill_slug_aliases(slug: str) -> list[str]:
    """All DB tags that map to an SEO skill slug (for count + search alignment)."""
    tags = sorted({k for k, v in TAG_TO_SKILL_SLUG.items() if v == slug})
    if not tags:
        tags = [slug.replace("-", " "), slug.replace("-", ".")]
    if slug not in tags:
        tags.append(slug)
    return tags


@router.get("/seo/skills", response_model=SeoTaxonomyListResponse)
async def seo_skills(
    request: Request,
    limit: int = Query(40, ge=1, le=80),
    db: AsyncSession = Depends(get_db),
) -> SeoTaxonomyListResponse:
    """Indexable skill landings that pass inventory quality gate."""
    await enforce_rate_limit(request, "seo-skills", limit=60)
    settings = get_settings()
    cutoff = freshness_cutoff(settings.freshness_days)

    # Distinct remote jobs per SEO slug — never sum overlapping tag counts.
    result = await db.execute(
        text(
            """
            SELECT j.id AS job_id, lower(trim(tag)) AS tag
            FROM jobs j,
            LATERAL unnest(
              COALESCE(j.skills, ARRAY[]::varchar[])
              || COALESCE(j.tech_tags, ARRAY[]::varchar[])
            ) AS tag
            WHERE j.is_active = true
              AND lower(coalesce(j.workplace_type, '')) = 'remote'
              AND (
                j.posted_at >= :cutoff
                OR (j.posted_at IS NULL AND j.first_seen_at >= :cutoff)
              )
              AND tag IS NOT NULL AND length(trim(tag)) > 1
            """
        ),
        {"cutoff": cutoff},
    )
    slug_jobs: dict[str, set[int]] = {}
    for row in result.mappings().all():
        mapped = TAG_TO_SKILL_SLUG.get(row["tag"])
        if not mapped or mapped not in SEO_SKILL_MAP:
            continue
        slug_jobs.setdefault(mapped, set()).add(int(row["job_id"]))

    items = [
        SeoTaxonomyItem(
            slug=slug,
            label=SEO_SKILL_MAP[slug],
            count=len(job_ids),
            kind="skill",
            href=skill_href(slug),
        )
        for slug, job_ids in sorted(slug_jobs.items(), key=lambda x: -len(x[1]))
        if len(job_ids) >= MIN_SKILL_JOBS
    ][:limit]
    return SeoTaxonomyListResponse(freshness_days=settings.freshness_days, items=items)


@router.get("/seo/skills/{slug}", response_model=SeoTaxonomyItem)
async def seo_skill_meta(
    slug: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> SeoTaxonomyItem:
    await enforce_rate_limit(request, "seo-skill-one", limit=120)
    if slug not in SEO_SKILL_MAP:
        raise HTTPException(status_code=404, detail="Skill not available")
    settings = get_settings()
    cutoff = freshness_cutoff(settings.freshness_days)
    tags = _skill_slug_aliases(slug)
    result = await db.execute(
        text(
            """
            SELECT count(*) AS cnt
            FROM jobs j
            WHERE j.is_active = true
              AND lower(coalesce(j.workplace_type, '')) = 'remote'
              AND (
                j.posted_at >= :cutoff
                OR (j.posted_at IS NULL AND j.first_seen_at >= :cutoff)
              )
              AND EXISTS (
                SELECT 1
                FROM unnest(
                  COALESCE(j.skills, ARRAY[]::varchar[])
                  || COALESCE(j.tech_tags, ARRAY[]::varchar[])
                ) AS t(tag)
                WHERE lower(trim(tag)) = ANY(CAST(:tags AS varchar[]))
              )
            """
        ),
        {"cutoff": cutoff, "tags": tags},
    )
    cnt = int(result.scalar_one() or 0)
    if cnt < MIN_SKILL_JOBS:
        raise HTTPException(status_code=404, detail="Not enough fresh jobs for this skill")
    return SeoTaxonomyItem(
        slug=slug,
        label=SEO_SKILL_MAP[slug],
        count=cnt,
        kind="skill",
        href=skill_href(slug),
    )




@router.get("/seo/companies", response_model=SeoTaxonomyListResponse)
async def seo_companies(
    request: Request,
    limit: int = Query(40, ge=1, le=80),
    db: AsyncSession = Depends(get_db),
) -> SeoTaxonomyListResponse:
    await enforce_rate_limit(request, "seo-companies", limit=60)
    settings = get_settings()
    active, fresh = _fresh_clause()
    result = await db.execute(
        select(Job.company_name, func.count().label("cnt"))
        .where(active, fresh)
        .where(func.length(Job.company_name) > 1)
        .group_by(Job.company_name)
        .having(func.count() >= MIN_COMPANY_JOBS)
        .order_by(func.count().desc())
        .limit(limit * 2)
    )
    items: list[SeoTaxonomyItem] = []
    seen_slugs: set[str] = set()
    for row in result.all():
        slug = slugify_company(row.company_name)
        if slug in seen_slugs:
            continue
        seen_slugs.add(slug)
        items.append(
            SeoTaxonomyItem(
                slug=slug,
                label=row.company_name,
                count=int(row.cnt),
                kind="company",
                href=company_href(slug),
            )
        )
        if len(items) >= limit:
            break
    return SeoTaxonomyListResponse(freshness_days=settings.freshness_days, items=items)


@router.get("/seo/companies/{slug}", response_model=SeoTaxonomyItem)
async def seo_company_meta(
    slug: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> SeoTaxonomyItem:
    await enforce_rate_limit(request, "seo-company-one", limit=120)
    settings = get_settings()
    active, fresh = _fresh_clause()
    # Find company names that slugify to this slug
    result = await db.execute(
        select(Job.company_name, func.count().label("cnt"))
        .where(active, fresh)
        .group_by(Job.company_name)
        .order_by(func.count().desc())
        .limit(2000)
    )
    match_name: Optional[str] = None
    match_cnt = 0
    for row in result.all():
        if slugify_company(row.company_name) == slug:
            match_name = row.company_name
            match_cnt = int(row.cnt)
            break
    if not match_name or match_cnt < MIN_COMPANY_JOBS:
        raise HTTPException(status_code=404, detail="Company not available")
    return SeoTaxonomyItem(
        slug=slug,
        label=match_name,
        count=match_cnt,
        kind="company",
        href=company_href(slug),
    )


@router.get("/seo/locations", response_model=SeoTaxonomyListResponse)
async def seo_locations(
    request: Request,
    kind: Literal["country", "city"] = Query("country"),
    db: AsyncSession = Depends(get_db),
) -> SeoTaxonomyListResponse:
    await enforce_rate_limit(request, "seo-locations", limit=60)
    settings = get_settings()
    cutoff = freshness_cutoff(settings.freshness_days)
    items: list[SeoTaxonomyItem] = []

    catalog = SEO_COUNTRIES if kind == "country" else SEO_CITIES
    for slug, meta in catalog.items():
        patterns = meta["patterns"]
        clauses = [f"lower(coalesce(location_raw,'')) LIKE :p{i}" for i in range(len(patterns))]
        params: dict = {"cutoff": cutoff, "min_jobs": MIN_LOCATION_JOBS}
        for i, p in enumerate(patterns):
            params[f"p{i}"] = f"%{p.lower()}%"
        pk_clause = ""
        if kind == "country" and meta.get("use_pakistan_friendly"):
            pk_clause = " OR pakistan_friendly = true"
        sql = text(
            f"""
            SELECT count(*) AS cnt
            FROM jobs
            WHERE is_active = true
              AND (
                posted_at >= :cutoff
                OR (posted_at IS NULL AND first_seen_at >= :cutoff)
              )
              AND (({' OR '.join(clauses)}){pk_clause})
            """
        )
        cnt = int((await db.execute(sql, params)).scalar_one() or 0)
        if cnt >= MIN_LOCATION_JOBS:
            items.append(
                SeoTaxonomyItem(
                    slug=slug,
                    label=meta["label"],
                    count=cnt,
                    kind=kind,
                    href=location_href(slug, city=(kind == "city")),
                )
            )
    items.sort(key=lambda x: -x.count)
    return SeoTaxonomyListResponse(freshness_days=settings.freshness_days, items=items)


@router.get("/seo/locations/{slug}", response_model=SeoTaxonomyItem)
async def seo_location_meta(
    slug: str,
    request: Request,
    kind: Literal["country", "city"] = Query("country"),
    db: AsyncSession = Depends(get_db),
) -> SeoTaxonomyItem:
    await enforce_rate_limit(request, "seo-location-one", limit=120)
    catalog = SEO_COUNTRIES if kind == "country" else SEO_CITIES
    meta = catalog.get(slug)
    if not meta:
        raise HTTPException(status_code=404, detail="Location not available")
    settings = get_settings()
    cutoff = freshness_cutoff(settings.freshness_days)
    patterns = meta["patterns"]
    clauses = [f"lower(coalesce(location_raw,'')) LIKE :p{i}" for i in range(len(patterns))]
    params: dict = {"cutoff": cutoff}
    for i, p in enumerate(patterns):
        params[f"p{i}"] = f"%{p.lower()}%"
    pk_clause = ""
    if kind == "country" and meta.get("use_pakistan_friendly"):
        pk_clause = " OR pakistan_friendly = true"
    sql = text(
        f"""
        SELECT count(*) AS cnt
        FROM jobs
        WHERE is_active = true
          AND (
            posted_at >= :cutoff
            OR (posted_at IS NULL AND first_seen_at >= :cutoff)
          )
          AND (({' OR '.join(clauses)}){pk_clause})
        """
    )
    cnt = int((await db.execute(sql, params)).scalar_one() or 0)
    if cnt < MIN_LOCATION_JOBS:
        raise HTTPException(status_code=404, detail="Not enough fresh jobs for this location")
    return SeoTaxonomyItem(
        slug=slug,
        label=meta["label"],
        count=cnt,
        kind=kind,
        href=location_href(slug, city=(kind == "city")),
    )
