from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import update
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
    cutoff = freshness_cutoff(days)
    result = await session.execute(
        update(Job)
        .where(Job.is_active.is_(True))
        .where(
            # Prefer posted_at; fall back to first_seen_at
            (Job.posted_at < cutoff)
            | ((Job.posted_at.is_(None)) & (Job.first_seen_at < cutoff))
        )
        .values(is_active=False)
    )
    await session.commit()
    return result.rowcount or 0
