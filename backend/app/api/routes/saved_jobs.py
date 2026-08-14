from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete as sa_delete
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user
from app.db.session import get_db
from app.matching.apply_kit import DEFAULT_CHECKLIST
from app.matching.followup import mark_applied
from app.models import Job, SavedJob, User
from app.schemas.auth import SavedJobCreate, SavedJobOut

router = APIRouter(prefix="/saved-jobs", tags=["saved-jobs"])


def _out(saved: SavedJob, job: Job | None = None) -> SavedJobOut:
    title = saved.job_title or (job.title if job else None)
    company = saved.company_name or (job.company_name if job else None)
    apply = saved.apply_url or (job.apply_url if job else None)
    return SavedJobOut(
        id=saved.id,
        job_id=saved.job_id,
        notes=saved.notes,
        status=saved.status,
        created_at=saved.created_at,
        job_title=title,
        company_name=company,
        apply_url=apply,
        applied_at=saved.applied_at,
        follow_up_on=saved.follow_up_on,
        last_touch_at=saved.last_touch_at,
        checklist=saved.checklist,
        listing_gone=saved.job_id is None or job is None,
    )


def _snapshot(saved: SavedJob, job: Job) -> None:
    saved.job_title = job.title
    saved.company_name = job.company_name
    saved.apply_url = job.apply_url
    if not saved.checklist:
        saved.checklist = dict(DEFAULT_CHECKLIST)


@router.get("", response_model=list[SavedJobOut])
async def list_saved(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[SavedJobOut]:
    result = await db.execute(
        select(SavedJob, Job)
        .outerjoin(Job, Job.id == SavedJob.job_id)
        .where(SavedJob.user_id == user.id)
        .order_by(SavedJob.created_at.desc())
    )
    return [_out(saved, job) for saved, job in result.all()]


@router.post("", response_model=SavedJobOut, status_code=status.HTTP_201_CREATED)
async def save_job(
    body: SavedJobCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SavedJobOut:
    job = (await db.execute(select(Job).where(Job.id == body.job_id))).scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    existing = (
        await db.execute(
            select(SavedJob).where(SavedJob.user_id == user.id, SavedJob.job_id == body.job_id)
        )
    ).scalar_one_or_none()
    if existing:
        existing.notes = body.notes if body.notes is not None else existing.notes
        existing.status = body.status
        _snapshot(existing, job)
        if body.status == "applied":
            mark_applied(existing)
        elif body.status in {"interview", "offer"}:
            existing.last_touch_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(existing)
        saved = existing
    else:
        saved = SavedJob(
            user_id=user.id,
            job_id=body.job_id,
            notes=body.notes,
            status=body.status,
        )
        _snapshot(saved, job)
        if body.status == "applied":
            mark_applied(saved)
        db.add(saved)
        await db.commit()
        await db.refresh(saved)

    return _out(saved, job)


@router.delete("/{saved_id}", status_code=status.HTTP_204_NO_CONTENT)
async def unsave_job(
    saved_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    saved = (
        await db.execute(
            select(SavedJob).where(SavedJob.id == saved_id, SavedJob.user_id == user.id)
        )
    ).scalar_one_or_none()
    if not saved:
        raise HTTPException(status_code=404, detail="Saved job not found")
    await db.execute(sa_delete(SavedJob).where(SavedJob.id == saved_id, SavedJob.user_id == user.id))
    await db.commit()
