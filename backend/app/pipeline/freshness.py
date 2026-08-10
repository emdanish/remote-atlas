from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import Job


def freshness_cutoff(days: int | None = None) -> datetime:
    window = days if days is not None else get_settings().freshness_days
    return datetime.now(timezone.utc) - timedelta(days=window)


def job_age_anchor(job: Job) -> datetime | None:
    return job.posted_at or job.first_seen_at


def is_fresh(job: Job, days: int | None = None) -> bool:
    if not job.is_active:
        return False
    anchor = job_age_anchor(job)
    if anchor is None:
        return False
    return anchor >= freshness_cutoff(days)


async def expire_stale_jobs(session: AsyncSession, days: int | None = None) -> int:
    """Soft-deactivate jobs whose age is outside the freshness window.

    Never touches jobs with posted_at/first_seen_at inside the window.
    """
    cutoff = freshness_cutoff(days)
    result = await session.execute(
        update(Job)
        .where(Job.is_active.is_(True))
        .where(
            (Job.posted_at < cutoff)
            | ((Job.posted_at.is_(None)) & (Job.first_seen_at < cutoff))
        )
        .values(is_active=False)
    )
    await session.commit()
    return result.rowcount or 0


async def purge_expired_jobs(
    session: AsyncSession,
    days: int | None = None,
    *,
    batch_size: int = 500,
) -> int:
    """Hard-delete jobs older than the freshness window (flush past inventory).

    Safety:
    - Uses the same age anchor as search: COALESCE(posted_at, first_seen_at)
    - Never deletes a row whose anchor is still inside the window
    - Batched deletes to avoid long locks and peak memory

    Related rows with ON DELETE CASCADE (saved_jobs, resume_tailorings) go with them.
    """
    cutoff = freshness_cutoff(days)
    total = 0
    while True:
        # Batch by id to keep each statement small
        result = await session.execute(
            text(
                """
                WITH doomed AS (
                  SELECT id
                  FROM jobs
                  WHERE COALESCE(posted_at, first_seen_at) < :cutoff
                  ORDER BY id
                  LIMIT :batch
                )
                DELETE FROM jobs j
                USING doomed d
                WHERE j.id = d.id
                RETURNING j.id
                """
            ),
            {"cutoff": cutoff, "batch": batch_size},
        )
        n = len(result.fetchall())
        total += n
        await session.commit()
        if n < batch_size:
            break
    return total
