from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Job
from app.pipeline.enrich import is_pakistan_friendly_remote
from sqlalchemy import func

from app.pipeline.normalize import NormalizedJob, apply_url_is_usable
from app.pipeline.description import normalize_job_description_fields
from app.pipeline.source_trust import PREFERRED_SOURCES_ORDER

UPSERT_CHUNK = 250


def _row(job: NormalizedJob, now: datetime) -> dict:
    title = (job.title or "")[:500]
    company_name = (job.company_name or "")[:240]
    location_raw = (job.location_raw or None)
    if location_raw:
        location_raw = location_raw[:480]
    employment_type = (job.employment_type or None)
    if employment_type:
        employment_type = employment_type[:60]
    external_id = (job.external_id or "")[:240]
    apply_url = job.apply_url
    if apply_url and len(apply_url) > 2000:
        apply_url = apply_url[:2000]
    company_url = job.company_url
    if company_url and len(company_url) > 1000:
        company_url = company_url[:1000]
    career_page_url = job.career_page_url
    if career_page_url and len(career_page_url) > 1000:
        career_page_url = career_page_url[:1000]

    desc_html, desc_text = normalize_job_description_fields(
        job.description_html,
        job.description_text,
    )

    return {
        "company_id": job.company_id,
        "source": job.source,
        "external_id": external_id,
        "title": title,
        "company_name": company_name,
        "company_url": company_url,
        "career_page_url": career_page_url,
        "apply_url": apply_url,
        "description_text": desc_text,
        "description_html": desc_html,
        "location_raw": location_raw,
        "workplace_type": (job.workplace_type or "unknown")[:32],
        "pakistan_friendly": is_pakistan_friendly_remote(
            job.workplace_type or "unknown", location_raw, desc_text
        ),
        "employment_type": employment_type,
        "career_stage": (job.career_stage or "unknown")[:32],
        "skills": (job.skills or [])[:40],
        "tech_tags": (job.tech_tags or [])[:40],
        "posted_at": job.posted_at,
        "first_seen_at": now,
        "last_seen_at": now,
        "is_active": True,
        "missed_runs": 0,
    }


async def upsert_jobs(session: AsyncSession, jobs: list[NormalizedJob]) -> int:
    if not jobs:
        return 0

    # Deduplicate within batch — Postgres rejects ON CONFLICT affecting same row twice
    deduped: dict[tuple[str, str], NormalizedJob] = {}
    for j in jobs:
        url = (j.apply_url or "").strip()
        if not url or not apply_url_is_usable(url):
            continue
        key = (j.source, (j.external_id or "")[:240])
        deduped[key] = j
    jobs = list(deduped.values())
    if not jobs:
        return 0

    now = datetime.now(timezone.utc)
    upserted = 0
    all_ids: list[int] = []

    for start in range(0, len(jobs), UPSERT_CHUNK):
        chunk = jobs[start : start + UPSERT_CHUNK]
        if not chunk:
            continue
        rows = [_row(j, now) for j in chunk]
        insert_stmt = insert(Job).values(rows)
        # Prefer true posted_at from source over wiping with NULL when re-upserting
        stmt = insert_stmt.on_conflict_do_update(
            constraint="uq_jobs_source_external_id",
            set_={
                "company_id": insert_stmt.excluded.company_id,
                "title": insert_stmt.excluded.title,
                "company_name": insert_stmt.excluded.company_name,
                "company_url": insert_stmt.excluded.company_url,
                "career_page_url": insert_stmt.excluded.career_page_url,
                "apply_url": insert_stmt.excluded.apply_url,
                "description_text": insert_stmt.excluded.description_text,
                "description_html": insert_stmt.excluded.description_html,
                "location_raw": insert_stmt.excluded.location_raw,
                "workplace_type": insert_stmt.excluded.workplace_type,
                "pakistan_friendly": insert_stmt.excluded.pakistan_friendly,
                "employment_type": insert_stmt.excluded.employment_type,
                "career_stage": insert_stmt.excluded.career_stage,
                "skills": insert_stmt.excluded.skills,
                "tech_tags": insert_stmt.excluded.tech_tags,
                "posted_at": func.coalesce(
                    insert_stmt.excluded.posted_at, Job.posted_at
                ),
                "last_seen_at": now,
                "is_active": True,
                "missed_runs": 0,
                "updated_at": now,
            },
        ).returning(Job.id)
        result = await session.execute(stmt)
        ids = [r[0] for r in result.fetchall()]
        all_ids.extend(ids)
        upserted += len(ids)

    if all_ids:
        # One bulk FTS rebuild for the whole batch
        await session.execute(
            text(
                """
                UPDATE jobs j SET search_tsv =
                  setweight(to_tsvector('english', coalesce(j.title, '')), 'A') ||
                  setweight(to_tsvector('english', coalesce(j.company_name, '')), 'A') ||
                  setweight(to_tsvector('english', coalesce(array_to_string(j.skills, ' '), '')), 'B') ||
                  setweight(to_tsvector('english', coalesce(left(j.description_text, 8000), '')), 'C')
                WHERE j.id = ANY(:ids)
                """
            ),
            {"ids": all_ids},
        )

    await session.commit()
    return upserted


async def deactivate_unseen_for_sources(
    session: AsyncSession,
    sources: list[str],
    seen_after: datetime,
) -> int:
    """Soft-deactivate jobs from successful sources not refreshed this run.

    Prevents stale ATS rows (especially those with null posted_at) from staying
    searchable after a freshness-correct re-ingest.
    """
    if not sources:
        return 0
    result = await session.execute(
        text(
            """
            WITH updated AS (
              UPDATE jobs
              SET missed_runs = missed_runs + 1,
                  is_active = CASE WHEN missed_runs + 1 >= 2 THEN false ELSE is_active END,
                  updated_at = now()
              WHERE is_active = true
                AND source = ANY(:sources)
                AND last_seen_at < :seen_after
              RETURNING is_active
            )
            SELECT count(*) FILTER (WHERE is_active = false) FROM updated
            """
        ),
        {"sources": sources, "seen_after": seen_after},
    )
    deactivated = int(result.scalar_one() or 0)
    await session.commit()
    return deactivated


async def suppress_cross_source_duplicates(session: AsyncSession) -> int:
    """Soft-deactivate duplicates by apply-URL key and title+company fingerprint.

    Preference: ATS boards over curated feeds over aggregators, then earliest first_seen.
    """
    preferred = list(PREFERRED_SOURCES_ORDER)
    # Stable order without array_position bind quirks (asyncpg)
    order_case = " ".join(
        f"WHEN source = :src_{i} THEN {i}" for i, _ in enumerate(preferred)
    )
    params = {f"src_{i}": s for i, s in enumerate(preferred)}

    result_url = await session.execute(
        text(
            f"""
            WITH keyed AS (
              SELECT id, source, first_seen_at,
                     lower(
                       regexp_replace(
                         regexp_replace(
                           split_part(
                             regexp_replace(apply_url, '^https?://(www\\.)?', '', 'i'),
                             '?', 1
                           ),
                           '/$', ''
                         ),
                         '#.*$', ''
                       )
                     ) AS apply_key
              FROM jobs
              WHERE is_active = true
                AND apply_url IS NOT NULL
                AND apply_url <> ''
            ),
            ranked AS (
              SELECT id,
                     ROW_NUMBER() OVER (
                       PARTITION BY apply_key
                       ORDER BY
                         CASE {order_case} ELSE 1000 END,
                         first_seen_at ASC,
                         id ASC
                     ) AS rn
              FROM keyed
              WHERE apply_key IS NOT NULL AND apply_key <> ''
            )
            UPDATE jobs j
            SET is_active = false, updated_at = now()
            FROM ranked r
            WHERE j.id = r.id AND r.rn > 1
            RETURNING j.id
            """
        ),
        params,
    )
    deactivated_url = len(result_url.fetchall())

    result_fp = await session.execute(
        text(
            f"""
            WITH ranked AS (
              SELECT id,
                     ROW_NUMBER() OVER (
                       PARTITION BY lower(btrim(title)), lower(btrim(company_name))
                       ORDER BY
                         CASE {order_case} ELSE 1000 END,
                         CASE WHEN posted_at IS NOT NULL THEN 0 ELSE 1 END,
                         first_seen_at ASC,
                         id ASC
                     ) AS rn
              FROM jobs
              WHERE is_active = true
            )
            UPDATE jobs j
            SET is_active = false, updated_at = now()
            FROM ranked r
            WHERE j.id = r.id AND r.rn > 1
            RETURNING j.id
            """
        ),
        params,
    )
    deactivated_fp = len(result_fp.fetchall())
    deactivated = deactivated_url + deactivated_fp
    if deactivated:
        await session.commit()
    return deactivated
