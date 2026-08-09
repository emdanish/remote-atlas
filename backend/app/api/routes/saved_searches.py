"""Saved-search Pulse API — catalogue watches with in-app alerts."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user
from app.db.session import get_db
from app.matching.alerts import notify_for_saved_search, run_saved_search
from app.models import SavedSearch, User
from app.schemas.job import JobOut
from app.pipeline.source_trust import source_kind, source_kind_label

router = APIRouter(prefix="/saved-searches", tags=["saved-searches"])


class SavedSearchCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    query_params: dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True


class SavedSearchUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=160)
    query_params: Optional[dict[str, Any]] = None
    is_active: Optional[bool] = None


class SavedSearchOut(BaseModel):
    id: int
    name: str
    query_params: dict[str, Any]
    is_active: bool
    last_checked_at: Optional[datetime] = None
    last_notified_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class SavedSearchRunOut(BaseModel):
    search: SavedSearchOut
    matched: int
    notified: int
    results: list[JobOut]


def _out(row: SavedSearch) -> SavedSearchOut:
    return SavedSearchOut(
        id=row.id,
        name=row.name,
        query_params=row.query_params or {},
        is_active=row.is_active,
        last_checked_at=row.last_checked_at,
        last_notified_at=row.last_notified_at,
        created_at=row.created_at,
    )


@router.get("", response_model=list[SavedSearchOut])
async def list_saved_searches(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[SavedSearchOut]:
    rows = (
        await db.execute(
            select(SavedSearch)
            .where(SavedSearch.user_id == user.id)
            .order_by(SavedSearch.created_at.desc())
            .limit(50)
        )
    ).scalars().all()
    return [_out(r) for r in rows]


@router.post("", response_model=SavedSearchOut, status_code=201)
async def create_saved_search(
    body: SavedSearchCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SavedSearchOut:
    count = (
        await db.execute(select(SavedSearch.id).where(SavedSearch.user_id == user.id))
    ).scalars().all()
    if len(count) >= 15:
        raise HTTPException(status_code=400, detail="Maximum 15 saved searches")
    row = SavedSearch(
        user_id=user.id,
        name=body.name.strip(),
        query_params=body.query_params or {},
        is_active=body.is_active,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return _out(row)


@router.patch("/{search_id}", response_model=SavedSearchOut)
async def update_saved_search(
    search_id: int,
    body: SavedSearchUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SavedSearchOut:
    row = (
        await db.execute(
            select(SavedSearch).where(
                SavedSearch.id == search_id, SavedSearch.user_id == user.id
            )
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Saved search not found")
    data = body.model_dump(exclude_unset=True)
    if "name" in data and data["name"]:
        row.name = data["name"].strip()
    if "query_params" in data and data["query_params"] is not None:
        row.query_params = data["query_params"]
    if "is_active" in data and data["is_active"] is not None:
        row.is_active = data["is_active"]
    await db.commit()
    await db.refresh(row)
    return _out(row)


@router.delete("/{search_id}", status_code=204, response_class=Response)
async def delete_saved_search(
    search_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    row = (
        await db.execute(
            select(SavedSearch).where(
                SavedSearch.id == search_id, SavedSearch.user_id == user.id
            )
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Saved search not found")
    await db.delete(row)
    await db.commit()
    return Response(status_code=204)


@router.post("/{search_id}/run", response_model=SavedSearchRunOut)
async def run_saved_search_now(
    search_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SavedSearchRunOut:
    """Run pulse now — surface matching jobs and notify for brand-new first_seen."""
    row = (
        await db.execute(
            select(SavedSearch).where(
                SavedSearch.id == search_id, SavedSearch.user_id == user.id
            )
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Saved search not found")

    # Preview: all matches under filters (not only newer)
    preview = await run_saved_search(db, row, only_newer_than=None)
    # Alerts: only newer than last check
    new_jobs = await run_saved_search(db, row, only_newer_than=row.last_checked_at)
    notes = await notify_for_saved_search(db, row, new_jobs)
    row.last_checked_at = datetime.now(timezone.utc)
    if notes:
        row.last_notified_at = row.last_checked_at
    await db.commit()
    await db.refresh(row)

    results: list[JobOut] = []
    for job in preview:
        item = JobOut.model_validate(job)
        item.source_kind = source_kind(job.source)
        item.source_kind_label = source_kind_label(job.source)
        if item.description_text and len(item.description_text) > 400:
            item.description_text = item.description_text[:400] + "…"
        results.append(item)

    return SavedSearchRunOut(
        search=_out(row),
        matched=len(preview),
        notified=len(notes),
        results=results,
    )
