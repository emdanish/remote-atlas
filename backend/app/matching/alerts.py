"""Saved-search pulse — notify users when catalogue has new matching roles."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job import Job
from app.models.user import Notification, SavedSearch
from app.search.fts import search_jobs

logger = logging.getLogger(__name__)

MAX_ALERTS_PER_SEARCH = 5


def _filters_from_query(params: dict[str, Any]) -> dict[str, Any]:
    skills_raw = params.get("skills")
    skill_list: Optional[list[str]] = None
    if isinstance(skills_raw, str) and skills_raw.strip():
        skill_list = [s.strip() for s in skills_raw.split(",") if s.strip()]
    elif isinstance(skills_raw, list):
        skill_list = [str(s).strip() for s in skills_raw if str(s).strip()]

    posted = params.get("posted_within")
    try:
        posted_within = int(posted) if posted is not None else 7
    except (TypeError, ValueError):
        posted_within = 7
    posted_within = max(1, min(30, posted_within))

    return {
        "q": (params.get("q") or None) or None,
        "workplace": params.get("workplace") or None,
        "city": params.get("city") or None,
        "country": params.get("country") or None,
        "company": params.get("company") or None,
        "employment_type": params.get("employment_type") or None,
        "posted_within": posted_within,
        "pakistan_friendly": bool(params.get("pakistan_friendly")),
        "skills": skill_list,
        "career_stage": params.get("career_stage") or None,
        "source": params.get("source") or None,
        "sort": "newest",
        "page": 1,
        "page_size": 20,
    }


async def run_saved_search(
    db: AsyncSession,
    saved: SavedSearch,
    *,
    only_newer_than: Optional[datetime] = None,
) -> list[Job]:
    filters = _filters_from_query(saved.query_params or {})
    scored, _total = await search_jobs(db, **filters)
    jobs = [j for j, _ in scored]
    if only_newer_than is not None:
        cutoff = only_newer_than
        if cutoff.tzinfo is None:
            cutoff = cutoff.replace(tzinfo=timezone.utc)
        filtered: list[Job] = []
        for j in jobs:
            seen = j.first_seen_at or j.posted_at
            if seen is None:
                continue
            if seen.tzinfo is None:
                seen = seen.replace(tzinfo=timezone.utc)
            if seen > cutoff:
                filtered.append(j)
        jobs = filtered
    return jobs[:MAX_ALERTS_PER_SEARCH]


async def notify_for_saved_search(
    db: AsyncSession,
    saved: SavedSearch,
    jobs: list[Job],
) -> list[Notification]:
    created: list[Notification] = []
    for job in jobs:
        link = f"/jobs/{job.id}"
        exists = (
            await db.execute(
                select(Notification.id).where(
                    Notification.user_id == saved.user_id,
                    Notification.link == link,
                )
            )
        ).scalar_one_or_none()
        if exists:
            continue
        n = Notification(
            user_id=saved.user_id,
            title=f"Pulse: {job.title}",
            body=f"{saved.name}: {job.company_name} · {job.workplace_type} · new catalogue match",
            link=link,
            is_read=False,
        )
        db.add(n)
        created.append(n)
    return created


async def process_all_saved_search_alerts(db: AsyncSession) -> dict[str, int]:
    """Called from scheduler after ingest. Fail-soft per search."""
    rows = (
        await db.execute(
            select(SavedSearch).where(SavedSearch.is_active.is_(True)).limit(500)
        )
    ).scalars().all()
    checked = 0
    notified = 0
    for saved in rows:
        try:
            jobs = await run_saved_search(
                db,
                saved,
                only_newer_than=saved.last_checked_at,
            )
            notes = await notify_for_saved_search(db, saved, jobs)
            saved.last_checked_at = datetime.now(timezone.utc)
            if notes:
                saved.last_notified_at = saved.last_checked_at
                notified += len(notes)
            checked += 1
        except Exception:  # noqa: BLE001
            logger.exception("Saved-search alert failed id=%s", saved.id)
    await db.commit()
    return {"checked": checked, "notified": notified}
