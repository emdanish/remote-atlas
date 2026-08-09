from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete as sa_delete
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user
from app.db.session import get_db
from app.models import Job, SavedJob, User
from app.schemas.auth import SavedJobCreate, SavedJobOut

router = APIRouter(prefix="/saved-jobs", tags=["saved-jobs"])


@router.get("", response_model=list[SavedJobOut])
async def list_saved(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[SavedJobOut]:
    result = await db.execute(
        select(SavedJob, Job)
        .join(Job, Job.id == SavedJob.job_id)
        .where(SavedJob.user_id == user.id)
        .order_by(SavedJob.created_at.desc())
    )
    rows = result.all()
    out: list[SavedJobOut] = []
    for saved, job in rows:
        out.append(
            SavedJobOut(
                id=saved.id,
                job_id=saved.job_id,
                notes=saved.notes,
                status=saved.status,
                created_at=saved.created_at,
                job_title=job.title,
                company_name=job.company_name,
                apply_url=job.apply_url,
            )
        )
    return out


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
        existing.notes = body.notes
        existing.status = body.status
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
        db.add(saved)
        await db.commit()
        await db.refresh(saved)

    return SavedJobOut(
        id=saved.id,
        job_id=saved.job_id,
        notes=saved.notes,
        status=saved.status,
        created_at=saved.created_at,
        job_title=job.title,
        company_name=job.company_name,
        apply_url=job.apply_url,
    )


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
