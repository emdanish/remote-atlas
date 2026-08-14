"""Resume upload + AI tailor-for-job APIs."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.deps import get_current_user
from app.db.session import AsyncSessionLocal, get_db
from app.security import enforce_rate_limit
from app.models import Job, ResumeTailoring, User, UserResume
from app.resume.extract import ExtractError, extract_text
from app.resume.pipeline import run_tailoring
from app.resume.storage import (
    ALLOWED_CONTENT_TYPES,
    ALLOWED_EXTENSIONS,
    MAX_RESUME_BYTES,
    resolve_stored,
    safe_filename,
    sha256_bytes,
    store_resume_bytes,
)

router = APIRouter(tags=["resume-tailor"])


class ResumeOut(BaseModel):
    id: int
    filename: str
    content_type: str
    byte_size: int
    is_primary: bool
    created_at: datetime
    has_text: bool

    class Config:
        from_attributes = True


class TailorStartRequest(BaseModel):
    resume_id: Optional[int] = None


class TailorOut(BaseModel):
    id: int
    job_id: int
    resume_id: int
    status: str
    stage: str | None = None
    error_message: str | None = None
    model_used: str | None = None
    created_at: datetime
    completed_at: datetime | None = None
    original_excerpt: str | None = None
    tailored: dict[str, Any] | None = None
    changes: list[Any] | None = None
    match_panel: dict[str, Any] | None = None
    validation: dict[str, Any] | None = None
    job_analysis: dict[str, Any] | None = None
    has_pdf: bool = False
    fidelity_note: str | None = None


def _resume_out(r: UserResume) -> ResumeOut:
    return ResumeOut(
        id=r.id,
        filename=r.filename,
        content_type=r.content_type,
        byte_size=r.byte_size,
        is_primary=r.is_primary,
        created_at=r.created_at,
        has_text=bool(r.extracted_text),
    )


def _tailor_out(t: ResumeTailoring, *, full: bool = True) -> TailorOut:
    val = t.validation_json or {}
    return TailorOut(
        id=t.id,
        job_id=t.job_id,
        resume_id=t.resume_id,
        status=t.status,
        stage=t.stage,
        error_message=t.error_message,
        model_used=t.model_used,
        created_at=t.created_at,
        completed_at=t.completed_at,
        original_excerpt=t.original_excerpt if full else None,
        tailored=t.tailored_json if full else None,
        changes=t.changes_json if full else None,
        match_panel=t.match_panel if full else None,
        validation=t.validation_json if full else None,
        job_analysis=t.job_analysis if full else None,
        has_pdf=bool(t.pdf_path),
        fidelity_note=val.get("fidelity_note") if full else None,
    )


@router.get("/resumes", response_model=list[ResumeOut])
async def list_resumes(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ResumeOut]:
    rows = (
        await db.execute(
            select(UserResume)
            .where(UserResume.user_id == user.id)
            .order_by(UserResume.created_at.desc())
        )
    ).scalars().all()
    return [_resume_out(r) for r in rows]


@router.post("/resumes", response_model=ResumeOut)
async def upload_resume(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ResumeOut:
    raw = await file.read()
    if len(raw) > MAX_RESUME_BYTES:
        raise HTTPException(status_code=400, detail="Resume too large (max 2MB)")
    if len(raw) < 20:
        raise HTTPException(status_code=400, detail="Empty file")

    filename = safe_filename(file.filename or "resume.pdf")
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail="Unsupported type. Use PDF, DOCX, or plain text.",
        )
    ctype = (file.content_type or "application/octet-stream").split(";")[0].strip()
    if ctype not in ALLOWED_CONTENT_TYPES and ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Unsupported content type")

    try:
        text = extract_text(raw, filename)
    except ExtractError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # demote prior primaries
    await db.execute(
        update(UserResume)
        .where(UserResume.user_id == user.id, UserResume.is_primary.is_(True))
        .values(is_primary=False)
    )

    path = store_resume_bytes(user.id, filename, raw)
    row = UserResume(
        user_id=user.id,
        filename=filename,
        content_type=ctype or "application/octet-stream",
        storage_path=str(path),
        byte_size=len(raw),
        sha256=sha256_bytes(raw),
        extracted_text=text,
        analysis_json=None,
        is_primary=True,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return _resume_out(row)


@router.delete("/resumes/{resume_id}")
async def delete_resume(
    resume_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    row = (
        await db.execute(
            select(UserResume).where(
                UserResume.id == resume_id, UserResume.user_id == user.id
            )
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Resume not found")
    path = resolve_stored(row.storage_path)
    await db.delete(row)
    await db.commit()
    if path:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass
    return {"status": "deleted"}


@router.post("/jobs/{job_id}/tailor-resume", response_model=TailorOut)
async def start_tailor(
    job_id: int,
    body: TailorStartRequest,
    background: BackgroundTasks,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TailorOut:
    await enforce_rate_limit(
        request, "tailor", limit=3, period_seconds=3600, identity=str(user.id)
    )
    inflight = (
        await db.execute(
            select(ResumeTailoring.id).where(
                ResumeTailoring.user_id == user.id,
                ResumeTailoring.status.in_(("pending", "running")),
            )
        )
    ).scalar_one_or_none()
    if inflight:
        raise HTTPException(
            status_code=429,
            detail="A resume tailor is already running. Wait for it to finish.",
        )
    job = (await db.execute(select(Job).where(Job.id == job_id))).scalar_one_or_none()
    if not job or not job.is_active:
        raise HTTPException(status_code=404, detail="Job not found")

    resume: UserResume | None = None
    if body.resume_id:
        resume = (
            await db.execute(
                select(UserResume).where(
                    UserResume.id == body.resume_id,
                    UserResume.user_id == user.id,
                )
            )
        ).scalar_one_or_none()
        if not resume:
            raise HTTPException(status_code=404, detail="Resume not found")
    else:
        resume = (
            await db.execute(
                select(UserResume)
                .where(UserResume.user_id == user.id)
                .order_by(UserResume.is_primary.desc(), UserResume.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if not resume:
            raise HTTPException(
                status_code=400,
                detail="Upload a resume first before tailoring.",
            )

    run = ResumeTailoring(
        user_id=user.id,
        resume_id=resume.id,
        job_id=job_id,
        status="pending",
        stage="queued",
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)

    run_id = run.id

    async def _bg() -> None:
        async with AsyncSessionLocal() as session:
            await run_tailoring(session, run_id)

    background.add_task(_bg)
    return _tailor_out(run, full=False)


@router.get("/tailorings/{tailoring_id}", response_model=TailorOut)
async def get_tailoring(
    tailoring_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TailorOut:
    run = (
        await db.execute(
            select(ResumeTailoring).where(
                ResumeTailoring.id == tailoring_id,
                ResumeTailoring.user_id == user.id,
            )
        )
    ).scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Tailoring not found")
    return _tailor_out(run, full=True)


@router.get("/jobs/{job_id}/tailorings", response_model=list[TailorOut])
async def list_job_tailorings(
    job_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[TailorOut]:
    rows = (
        await db.execute(
            select(ResumeTailoring)
            .where(
                ResumeTailoring.user_id == user.id,
                ResumeTailoring.job_id == job_id,
            )
            .order_by(ResumeTailoring.created_at.desc())
            .limit(20)
        )
    ).scalars().all()
    return [_tailor_out(r, full=False) for r in rows]


@router.get("/tailorings/{tailoring_id}/pdf")
async def download_tailored_pdf(
    tailoring_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FileResponse:
    """Serve tailored PDF. Rebuild from canonical IR when the stored file is stale/broken."""
    from app.resume.parse import parse_resume_text
    from app.resume.pdf import (
        assert_pdf_heading_integrity,
        build_resume_pdf,
        extract_pdf_text,
    )
    from app.resume.schema import finalize_document
    from app.resume.storage import store_tailored_pdf
    from app.resume.validate import content_integrity_failures, repair_against_original

    run = (
        await db.execute(
            select(ResumeTailoring)
            .where(
                ResumeTailoring.id == tailoring_id,
                ResumeTailoring.user_id == user.id,
            )
            .options(selectinload(ResumeTailoring.resume))
        )
    ).scalar_one_or_none()
    if not run or run.status != "completed":
        raise HTTPException(status_code=404, detail="PDF not ready")

    path = resolve_stored(run.pdf_path) if run.pdf_path else None
    if not path:
        candidate = Path(run.pdf_path) if run.pdf_path else None
        if candidate and candidate.is_file() and "uploads" in str(candidate):
            path = candidate

    # A stored document that lost content (e.g. produced during a provider
    # outage) is repaired from the user's original resume before download.
    original_doc = None
    if run.resume and run.resume.extracted_text:
        original_doc = finalize_document(parse_resume_text(run.resume.extracted_text))

    need_rebuild = not path or not path.is_file()
    if path and path.is_file() and run.tailored_json:
        try:
            plain = extract_pdf_text(path.read_bytes())
            if assert_pdf_heading_integrity(plain):
                need_rebuild = True
        except Exception:  # noqa: BLE001
            need_rebuild = True
    if original_doc and run.tailored_json:
        if content_integrity_failures(original=original_doc, final=run.tailored_json):
            need_rebuild = True

    if need_rebuild and run.tailored_json:
        cleaned = finalize_document(run.tailored_json)
        if original_doc and content_integrity_failures(original=original_doc, final=cleaned):
            cleaned = repair_against_original(original=original_doc, final=cleaned)
        pdf_input = {k: v for k, v in cleaned.items() if k != "sections"}
        pdf_bytes = build_resume_pdf(tailored=pdf_input)
        path = store_tailored_pdf(run.user_id, run.id, pdf_bytes)
        run.pdf_path = str(path)
        run.tailored_json = cleaned
        await db.commit()

    if not path or not path.is_file():
        raise HTTPException(status_code=404, detail="PDF file missing")
    return FileResponse(
        path,
        media_type="application/pdf",
        filename=f"tailored-resume-{tailoring_id}.pdf",
    )


@router.delete("/tailorings/{tailoring_id}")
async def delete_tailoring(
    tailoring_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    run = (
        await db.execute(
            select(ResumeTailoring).where(
                ResumeTailoring.id == tailoring_id,
                ResumeTailoring.user_id == user.id,
            )
        )
    ).scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Tailoring not found")
    if run.pdf_path:
        path = resolve_stored(run.pdf_path)
        if path:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass
    await db.delete(run)
    await db.commit()
    return {"status": "deleted"}


@router.post("/tailorings/{tailoring_id}/regenerate", response_model=TailorOut)
async def regenerate_tailoring(
    tailoring_id: int,
    background: BackgroundTasks,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TailorOut:
    await enforce_rate_limit(
        request, "tailor", limit=3, period_seconds=3600, identity=str(user.id)
    )
    old = (
        await db.execute(
            select(ResumeTailoring).where(
                ResumeTailoring.id == tailoring_id,
                ResumeTailoring.user_id == user.id,
            )
        )
    ).scalar_one_or_none()
    if not old:
        raise HTTPException(status_code=404, detail="Tailoring not found")

    run = ResumeTailoring(
        user_id=user.id,
        resume_id=old.resume_id,
        job_id=old.job_id,
        status="pending",
        stage="queued",
        job_analysis=old.job_analysis,  # reuse job analysis
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)
    run_id = run.id

    async def _bg() -> None:
        async with AsyncSessionLocal() as session:
            await run_tailoring(session, run_id)

    background.add_task(_bg)
    return _tailor_out(run, full=False)
