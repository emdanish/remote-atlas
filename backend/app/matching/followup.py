"""In-app follow-up and ghosted transitions for the application tracker."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import Notification, SavedJob

logger = logging.getLogger(__name__)

FOLLOW_UP_DAYS = 7
GHOSTED_DAYS = 14


def schedule_follow_up(now: datetime | None = None) -> datetime:
    now = now or datetime.now(timezone.utc)
    return now + timedelta(days=FOLLOW_UP_DAYS)


def mark_applied(saved: SavedJob, now: datetime | None = None) -> None:
    now = now or datetime.now(timezone.utc)
    saved.status = "applied"
    if saved.applied_at is None:
        saved.applied_at = now
    saved.last_touch_at = now
    saved.follow_up_on = schedule_follow_up(now)


async def process_application_followups(db: AsyncSession) -> dict[str, int]:
    now = datetime.now(timezone.utc)
    ghost_cutoff = now - timedelta(days=GHOSTED_DAYS)
    rows = (
        await db.execute(
            select(SavedJob).where(SavedJob.status == "applied")
        )
    ).scalars().all()

    followups = 0
    ghosted = 0
    for saved in rows:
        applied = saved.applied_at or saved.last_touch_at
        if applied and applied.tzinfo is None:
            applied = applied.replace(tzinfo=timezone.utc)
        if applied and applied <= ghost_cutoff:
            saved.status = "ghosted"
            saved.last_touch_at = now
            ghosted += 1
            title = saved.job_title or "a role"
            company = saved.company_name or "the company"
            n = Notification(
                user_id=saved.user_id,
                title=f"Marked ghosted: {title}",
                body=f"{company} — 14 days since you applied with no interview logged. Update status if they replied.",
                link="/saved",
                is_read=False,
            )
            db.add(n)
            continue
        due = saved.follow_up_on
        if due is None:
            continue
        if due.tzinfo is None:
            due = due.replace(tzinfo=timezone.utc)
        if due > now:
            continue
        title = saved.job_title or "a role"
        company = saved.company_name or "the company"
        link = f"/jobs/{saved.job_id}" if saved.job_id else "/saved"
        exists = (
            await db.execute(
                select(Notification.id).where(
                    Notification.user_id == saved.user_id,
                    Notification.title == f"Follow up: {title}",
                )
            )
        ).scalar_one_or_none()
        if exists:
            continue
        n = Notification(
            user_id=saved.user_id,
            title=f"Follow up: {title}",
            body=f"{company} — you applied about 7 days ago. A short note on their ATS or careers email is enough. We never send it for you.",
            link=link,
            is_read=False,
        )
        db.add(n)
        saved.follow_up_on = now + timedelta(days=FOLLOW_UP_DAYS)
        followups += 1

    await db.commit()
    logger.info("Hunt follow-ups | reminded=%s ghosted=%s", followups, ghosted)
    return {"reminded": followups, "ghosted": ghosted}
