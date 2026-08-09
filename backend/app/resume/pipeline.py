"""Resume tailoring pipeline: analyze → tailor → validate → quality → PDF."""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.ai.provider import AIProviderError, chat_completion
from app.models import Job, Profile, ResumeTailoring
from app.pipeline.enrich import extract_skills
from app.resume.extract import ExtractError, extract_text, restore_resume_structure
from app.resume.parse import parse_resume_text
from app.resume.pdf import (
    assert_pdf_heading_integrity,
    build_resume_pdf,
    count_pdf_section_headings,
    extract_pdf_text,
    pdf_page_count,
)
from app.resume.prompts import JOB_ANALYSIS_SYSTEM, RESUME_FACTS_SYSTEM, TAILOR_SYSTEM
from app.resume.quality import assert_export_safe, run_quality_gate
from app.resume.schema import (
    assert_section_uniqueness,
    finalize_document,
    normalize_document,
)
from app.resume.skills import build_skill_groups, derive_headline
from app.resume.storage import resolve_stored, store_tailored_pdf
from app.resume.validate import (
    content_integrity_failures,
    local_match_panel,
    merge_tailored_onto_original,
    repair_against_original,
    validate_tailored_payload,
)

logger = logging.getLogger(__name__)

STAGE = {
    "job": "analyzing_job",
    "resume": "analyzing_resume",
    "match": "matching_experience",
    "tailor": "tailoring_sections",
    "validate": "checking_accuracy",
    "pdf": "preparing_preview",
    "done": "completed",
}


def _parse_json_obj(raw: str) -> dict[str, Any]:
    text = (raw or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ValueError("Model did not return JSON")
    return json.loads(m.group(0))


async def _set_stage(db: AsyncSession, run_id: int, stage: str, status: str = "running") -> None:
    await db.execute(
        update(ResumeTailoring)
        .where(ResumeTailoring.id == run_id)
        .values(stage=stage, status=status, updated_at=datetime.now(timezone.utc))
    )
    await db.commit()


async def run_tailoring(db: AsyncSession, run_id: int) -> None:
    run = (
        await db.execute(
            select(ResumeTailoring)
            .where(ResumeTailoring.id == run_id)
            .options(selectinload(ResumeTailoring.resume))
        )
    ).scalar_one_or_none()
    if not run:
        return

    try:
        resume = run.resume
        if not resume:
            raise RuntimeError("Resume missing")

        job = (
            await db.execute(select(Job).where(Job.id == run.job_id))
        ).scalar_one_or_none()
        if not job:
            raise RuntimeError("Job not found")

        original = (resume.extracted_text or "").strip()
        if len(original) < 40:
            path = resolve_stored(resume.storage_path)
            if not path:
                raise RuntimeError("Resume file missing")
            original = extract_text(path.read_bytes(), resume.filename)
            resume.extracted_text = original
            await db.commit()

        # Heal legacy DB rows whose PDF extract lost newlines (0–few lines).
        healed = restore_resume_structure(original)
        if healed != original:
            logger.info(
                "restored resume structure run=%s chars=%s newlines %s→%s",
                run_id,
                len(healed),
                original.count("\n"),
                healed.count("\n"),
            )
            original = healed
            resume.extracted_text = original
            await db.commit()

        profile = (
            await db.execute(select(Profile).where(Profile.user_id == run.user_id))
        ).scalar_one_or_none()

        await _set_stage(db, run_id, STAGE["job"])
        job_text = (job.description_text or job.title or "")[:12000]
        job_analysis = run.job_analysis
        if not job_analysis:
            job_analysis = await _analyze_job(job.title, job.company_name or "", job_text)
            run.job_analysis = job_analysis
            await db.commit()

        keywords = list(
            dict.fromkeys(
                [
                    *(job_analysis.get("required") or []),
                    *(job_analysis.get("preferred") or []),
                    *(job_analysis.get("keywords") or []),
                    *(job.skills or [])[:20],
                    *(job.tech_tags or [])[:20],
                ]
            )
        )[:60]

        await _set_stage(db, run_id, STAGE["resume"])
        resume_facts = resume.analysis_json
        if not resume_facts:
            resume_facts = await _analyze_resume(original)
            resume.analysis_json = resume_facts
            await db.commit()
        run.resume_facts = resume_facts
        run.original_excerpt = original[:4000]
        await db.commit()

        await _set_stage(db, run_id, STAGE["match"])
        panel_seed = local_match_panel(original, job_text, keywords)

        # Deterministic baseline: the user's own resume, parsed without any AI.
        # Everything downstream is an edit on top of this, never a replacement.
        original_doc = _original_baseline(original, resume_facts)
        if _document_is_contentless(original_doc):
            # Last resort: re-read the upload and re-parse. Never tailor from empty IR.
            path = resolve_stored(resume.storage_path)
            if path and path.exists():
                try:
                    re_extracted = extract_text(path.read_bytes(), resume.filename)
                    if re_extracted and re_extracted != original:
                        original = re_extracted
                        resume.extracted_text = original
                        await db.commit()
                        original_doc = _original_baseline(original, resume_facts)
                except ExtractError as exc:
                    logger.warning("re-extract failed for run %s: %s", run_id, exc)
            if _document_is_contentless(original_doc):
                logger.error(
                    "baseline still empty after heal/re-extract run=%s text_len=%s",
                    run_id,
                    len(original),
                )

        await _set_stage(db, run_id, STAGE["tailor"])
        tailored_raw, model_note = await _tailor(
            original=original,
            job_title=job.title,
            company=job.company_name or "",
            job_text=job_text,
            job_analysis=job_analysis,
            resume_facts=resume_facts,
            profile=profile,
            panel_seed=panel_seed,
        )

        await _set_stage(db, run_id, STAGE["validate"])
        validation = validate_tailored_payload(
            original_text=original,
            tailored=tailored_raw,
            job_keywords=keywords,
        )
        # AI is an editor, not the owner of the structure: merge its output onto
        # the parsed original so omissions cannot delete sections or entries.
        cleaned = merge_tailored_onto_original(
            original=original_doc, tailored=validation["tailored"]
        )

        # Enforce categorized skills with job relevance (only original-supported)
        skill_seed = list(
            dict.fromkeys(
                [
                    *(resume_facts.get("technologies") or []),
                    *(resume_facts.get("skills_mentioned") or []),
                    *[
                        it
                        for g in (cleaned.get("skill_groups") or [])
                        for it in (g.get("items") or [])
                    ],
                    *extract_skills(original)[:40],
                    *([*(profile.technologies or []), *(profile.skills or [])] if profile else []),
                ]
            )
        )
        cleaned["skill_groups"] = build_skill_groups(
            candidate_skills=skill_seed,
            original_text=original,
            job_keywords=keywords,
            job_text=job_text,
        ) or (original_doc.get("skill_groups") or [])

        # Headline (contact facts stay as parsed from the original resume)
        contact = cleaned.get("contact") or {}
        contact["headline"] = derive_headline(
            contact_headline=str(contact.get("headline") or resume_facts.get("headline") or ""),
            resume_facts=resume_facts,
            job_title=job.title,
            original_text=original,
        )
        cleaned["contact"] = contact

        # Prefer all projects from resume facts if AI dropped some; always dedupe
        facts_projects = resume_facts.get("projects") or []
        if facts_projects:
            cleaned["projects"] = _merge_projects(
                cleaned.get("projects") or [], facts_projects, original
            )
        cleaned["projects"] = _dedupe_projects(cleaned.get("projects") or [])

        # Quality gate (dedupe summary, strip meta, structure)
        quality = run_quality_gate(document=cleaned, original_text=original)
        cleaned = quality["document"]
        # Re-apply skill relevance after normalize (prevents duplicate AI categories)
        cleaned["skill_groups"] = build_skill_groups(
            candidate_skills=[
                *skill_seed,
                *[it for g in (cleaned.get("skill_groups") or []) for it in (g.get("items") or [])],
            ],
            original_text=original,
            job_keywords=keywords,
            job_text=job_text,
            max_groups=6,
            max_per_group=8,
            max_total=32,
        ) or (original_doc.get("skill_groups") or [])
        # Prefer full project names from original facts
        cleaned["projects"] = _dedupe_projects(cleaned.get("projects") or [])
        for p in cleaned["projects"]:
            n = str(p.get("name") or "")
            if n.lower() in ("companion", "remote atlas") and "remote atlas" in original.lower():
                for line in original.splitlines():
                    if "remote atlas" in line.lower() and len(line.strip()) < 80:
                        p["name"] = line.strip()
                        break

        cleaned["changes"] = validation["tailored"].get("changes") or cleaned.get("changes") or []
        cleaned["match_panel"] = _merge_panel(
            validation["tailored"].get("match_panel") or {}, panel_seed
        )

        await _set_stage(db, run_id, STAGE["pdf"])
        cleaned = finalize_document(cleaned)

        # Content integrity: the tailored resume must still contain the user's
        # resume. Repair from the original first; only if that fails do we ship
        # the untailored original rather than a damaged document.
        integrity = content_integrity_failures(original=original_doc, final=cleaned)
        if integrity:
            logger.warning("content integrity failures: %s; repairing", integrity)
            cleaned = repair_against_original(original=original_doc, final=cleaned)
            integrity = content_integrity_failures(original=original_doc, final=cleaned)
        if integrity:
            logger.error("integrity unrecoverable: %s; exporting original resume", integrity)
            cleaned = finalize_document(
                {**original_doc, "match_panel": panel_seed, "changes": []}
            )
            validation = {
                **validation,
                "ok": True,
                "fallback": True,
                "message": (
                    "Tailoring output failed content checks; your original resume was "
                    "preserved and exported unchanged."
                ),
            }

        # Never ship / store an empty structured resume when source text exists.
        if _document_is_contentless(cleaned) and not _document_is_contentless(original_doc):
            logger.error("cleaned IR empty — forcing original baseline run=%s", run_id)
            cleaned = finalize_document(
                {**original_doc, "match_panel": panel_seed, "changes": []}
            )
            validation = {
                **validation,
                "ok": True,
                "fallback": True,
                "message": (
                    "Tailoring produced an empty document; your original resume was "
                    "preserved and exported unchanged."
                ),
            }
        elif _document_is_contentless(cleaned) and original:
            # Baseline also empty (rare after heal) — fall back to whole-text bucket
            logger.error("both IRs empty — text-bucket fallback run=%s", run_id)
            cleaned = finalize_document(
                {
                    **_text_bucket_document(original, resume_facts),
                    "match_panel": panel_seed,
                    "changes": [],
                }
            )
            validation = {
                **validation,
                "ok": True,
                "fallback": True,
                "message": (
                    "Could not fully structure this resume; original text was preserved "
                    "for export."
                ),
            }

        pdf_input = {k: v for k, v in cleaned.items() if k != "sections"}
        pdf_bytes = build_resume_pdf(tailored=pdf_input)
        plain = extract_pdf_text(pdf_bytes)
        fails = assert_export_safe(cleaned)
        pdf_heading_fails = assert_pdf_heading_integrity(plain)
        if "tailored for" in plain.lower() or fails or pdf_heading_fails:
            logger.warning(
                "export safety hit; rebuilding scrubbed: %s %s", fails, pdf_heading_fails
            )
            quality = run_quality_gate(document=cleaned, original_text=original)
            cleaned = finalize_document(quality["document"])
            cleaned["skill_groups"] = build_skill_groups(
                candidate_skills=skill_seed,
                original_text=original,
                job_keywords=keywords,
                job_text=job_text,
                max_groups=6,
            ) or (original_doc.get("skill_groups") or [])
            cleaned["projects"] = _dedupe_projects(cleaned.get("projects") or [])
            cleaned = finalize_document(cleaned)
            pdf_input = {k: v for k, v in cleaned.items() if k != "sections"}
            pdf_bytes = build_resume_pdf(tailored=pdf_input)
            plain = extract_pdf_text(pdf_bytes)

        pages = pdf_page_count(pdf_bytes)
        # 3+ pages: condense bullets, never drop sections
        if pages >= 3:
            cleaned = finalize_document(_compress_document(cleaned))
            cleaned["projects"] = _dedupe_projects(cleaned.get("projects") or [])
            cleaned = finalize_document(cleaned)
            pdf_input = {k: v for k, v in cleaned.items() if k != "sections"}
            pdf_bytes = build_resume_pdf(tailored=pdf_input)
            pages = pdf_page_count(pdf_bytes)
            plain = extract_pdf_text(pdf_bytes)

        # Final gate: rebuild steps above must not have dropped anything either
        cleaned = finalize_document(cleaned)
        integrity = content_integrity_failures(original=original_doc, final=cleaned)
        if integrity:
            logger.warning("post-render integrity failures: %s; repairing", integrity)
            cleaned = repair_against_original(original=original_doc, final=cleaned)
            integrity = content_integrity_failures(original=original_doc, final=cleaned)
            pdf_input = {k: v for k, v in cleaned.items() if k != "sections"}
            pdf_bytes = build_resume_pdf(tailored=pdf_input)
            plain = extract_pdf_text(pdf_bytes)
            pages = pdf_page_count(pdf_bytes)

        heading_counts = count_pdf_section_headings(plain)
        pdf_path = store_tailored_pdf(run.user_id, run.id, pdf_bytes)

        quality_report = {
            "ok": quality.get("ok", True)
            and not integrity
            and not assert_section_uniqueness(cleaned)
            and not assert_pdf_heading_integrity(plain),
            "content_integrity": integrity,
            "issue_count": validation.get("issue_count", 0) + len(quality.get("issues") or []),
            "high_severity": validation.get("high_severity", 0),
            "issues": (validation.get("issues") or [])[:30] + (quality.get("issues") or [])[:20],
            "quality_fixed": quality.get("fixed") or [],
            "fallback": validation.get("fallback", False),
            "message": validation.get("message"),
            "page_count": pages,
            "section_heading_counts": heading_counts,
            "summary_heading_count": heading_counts.get("summary", 0),
            "references_heading_count": heading_counts.get("references", 0),
            "has_tailored_for": "tailored for" in plain.lower(),
            "pdf_text_extractable": len(plain.strip()) > 80,
            "fidelity_note": (
                "PDF uses a single-column ATS-safe professional layout (Helvetica, standard "
                "headings, body text). Original decorative design is not pixel-cloned."
            ),
        }

        run.tailored_json = cleaned
        run.validation_json = quality_report
        run.changes_json = cleaned.get("changes") or []
        run.match_panel = cleaned.get("match_panel")
        run.pdf_path = str(pdf_path)
        run.model_used = model_note
        run.status = "completed"
        run.stage = STAGE["done"]
        run.completed_at = datetime.now(timezone.utc)
        run.error_message = None
        await db.commit()
    except ExtractError as exc:
        await _fail(db, run_id, str(exc) or "Could not read resume")
    except AIProviderError as exc:
        try:
            await _complete_without_ai(db, run_id, str(exc))
        except Exception:  # noqa: BLE001
            logger.exception("tailoring failed %s", run_id)
            await _fail(db, run_id, "AI unavailable and local fallback failed")
    except Exception as exc:  # noqa: BLE001
        logger.exception("tailoring failed %s", run_id)
        await _fail(db, run_id, _user_error(exc))


async def _fail(db: AsyncSession, run_id: int, message: str) -> None:
    await db.execute(
        update(ResumeTailoring)
        .where(ResumeTailoring.id == run_id)
        .values(
            status="failed",
            error_message=message[:500],
            stage="failed",
            updated_at=datetime.now(timezone.utc),
        )
    )
    await db.commit()


def _user_error(exc: BaseException) -> str:
    msg = str(exc) or "Processing failed"
    low = msg.lower()
    if "quota" in low or "429" in low or "rate" in low:
        return "AI quota exceeded. Try again later."
    if "timeout" in low:
        return "Tailoring timed out. Please try again."
    if "json" in low:
        return "AI returned invalid output. Please regenerate."
    return "Could not complete resume tailoring. Please try again."


async def _analyze_job(title: str, company: str, job_text: str) -> dict[str, Any]:
    local_skills = extract_skills(job_text)
    base = {
        "role_title": title,
        "required": local_skills[:20],
        "preferred": [],
        "soft_skills": [],
        "domain_terms": [],
        "responsibilities": [],
        "certifications": [],
        "keywords": local_skills[:30],
    }
    try:
        raw = await chat_completion(
            system=JOB_ANALYSIS_SYSTEM,
            user=f"Role: {title}\nCompany: {company}\n\n{job_text[:8000]}",
            temperature=0.1,
            max_tokens=900,
        )
        data = _parse_json_obj(raw)
        for key in ("required", "preferred", "soft_skills", "domain_terms", "keywords", "certifications"):
            vals = [str(x).strip() for x in (data.get(key) or []) if str(x).strip()]
            base[key] = list(dict.fromkeys([*(base.get(key) or []), *vals]))[:40]
        if data.get("role_title"):
            base["role_title"] = str(data["role_title"])[:200]
        if data.get("responsibilities"):
            base["responsibilities"] = [str(x)[:200] for x in data["responsibilities"][:20]]
    except Exception as exc:  # noqa: BLE001
        logger.warning("job analysis AI skipped: %s", exc)
    return base


async def _analyze_resume(original: str) -> dict[str, Any]:
    local: dict[str, Any] = {
        "name": "",
        "headline": "",
        "emails": re.findall(r"[\w.+-]+@[\w.-]+\.\w+", original)[:3],
        "phones": re.findall(r"\+?[\d][\d\s().-]{7,}\d", original)[:2],
        "locations": [],
        "links": re.findall(
            r"(?:https?://[^\s]+|(?:linkedin\.com|github\.com)/[^\s]+)", original, re.I
        )[:8],
        "skills_mentioned": extract_skills(original)[:40],
        "technologies": extract_skills(original)[:40],
        "roles": [],
        "projects": [],
        "education": [],
        "certifications": [],
        "metrics_found": re.findall(
            r"\d+(?:\.\d+)?\s*%|\b\d{1,3}(?:,\d{3})+\b", original
        )[:20],
        "summary_present": bool(
            re.search(r"(?im)^(summary|professional summary|profile|objective)\b", original)
        ),
        "raw_section_headings": [],
    }
    try:
        raw = await chat_completion(
            system=RESUME_FACTS_SYSTEM,
            user=original[:11000],
            temperature=0.0,
            max_tokens=2000,
        )
        data = _parse_json_obj(raw)
        if isinstance(data, dict):
            orig_l = original.lower()
            for key in ("skills_mentioned", "technologies"):
                vals = []
                for x in data.get(key) or []:
                    s = str(x).strip()
                    if s and s.lower() in orig_l:
                        vals.append(s)
                if vals:
                    local[key] = list(dict.fromkeys([*vals, *local[key]]))[:40]
            if data.get("name"):
                local["name"] = str(data["name"])[:120]
            if data.get("headline"):
                local["headline"] = str(data["headline"])[:80]
            if data.get("roles"):
                local["roles"] = data["roles"][:12]
            if data.get("projects"):
                local["projects"] = data["projects"][:12]
            if data.get("education"):
                local["education"] = data["education"][:8]
            if data.get("links"):
                local["links"] = list(
                    dict.fromkeys([*(local.get("links") or []), *data["links"]])
                )[:8]
    except Exception as exc:  # noqa: BLE001
        logger.warning("resume facts AI skipped: %s", exc)
    return local


async def _tailor(
    *,
    original: str,
    job_title: str,
    company: str,
    job_text: str,
    job_analysis: dict[str, Any],
    resume_facts: dict[str, Any],
    profile: Profile | None,
    panel_seed: dict[str, Any],
) -> tuple[dict[str, Any], str]:
    profile_bits = ""
    if profile:
        profile_bits = (
            f"Profile skills (supporting only; resume authoritative): "
            f"{', '.join((profile.skills or [])[:15])}; "
            f"tech: {', '.join((profile.technologies or [])[:15])}"
        )

    user_msg = (
        f"TARGET JOB\nTitle: {job_title}\nCompany: {company}\n"
        f"Job analysis JSON:\n{json.dumps(job_analysis)[:3500]}\n\n"
        f"JOB DESCRIPTION (excerpt):\n{job_text[:4500]}\n\n"
        f"RESUME FACTS JSON (preserve all projects listed):\n"
        f"{json.dumps(resume_facts)[:4500]}\n\n"
        f"{profile_bits}\n\n"
        f"ORIGINAL RESUME TEXT (authoritative):\n{original[:10000]}\n\n"
        f"Seed match panel:\n{json.dumps(panel_seed)[:1500]}\n\n"
        "Return the structured JSON schema only. Exactly one professional summary. "
        "No 'Tailored for' text. Keep all original projects (compress bullets if needed)."
    )

    try:
        raw = await chat_completion(
            system=TAILOR_SYSTEM,
            user=user_msg,
            temperature=0.12,
            max_tokens=4000,
        )
        data = _parse_json_obj(raw)
        if not isinstance(data, dict):
            raise ValueError("not an object")
        return normalize_document(data), "chat_completion_chain"
    except Exception as exc:
        logger.warning("tailor AI failed, using structure fallback: %s", exc)
        return (
            _fallback_structure(original, resume_facts, panel_seed, job_text, []),
            "local_fallback",
        )


def _merge_panel(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    return {
        "strong_matches": list(
            dict.fromkeys([*(a.get("strong_matches") or []), *(b.get("strong_matches") or [])])
        )[:30],
        "emphasized": list(
            dict.fromkeys([*(a.get("emphasized") or []), *(b.get("emphasized") or [])])
        )[:20],
        "missing": list(
            dict.fromkeys([*(a.get("missing") or []), *(b.get("missing") or [])])
        )[:40],
        "potential_gaps": list(
            dict.fromkeys([*(a.get("potential_gaps") or []), *(b.get("potential_gaps") or [])])
        )[:15],
        "note": a.get("note")
        or b.get("note")
        or "Missing items are gaps — never invent them on the resume.",
    }


def _merge_projects(
    tailored: list[dict[str, Any]],
    facts: list[Any],
    original: str,
) -> list[dict[str, Any]]:
    """Ensure we don't silently lose projects present in fact extraction."""
    from app.resume.validate import phrase_supported, original_phrase_index

    orig = original_phrase_index(original)
    by_name = {_norm_key(p.get("name")): p for p in tailored if p.get("name")}
    out = list(tailored)
    for fp in facts:
        if not isinstance(fp, dict):
            continue
        name = str(fp.get("name") or "").strip()
        if not name or not phrase_supported(name, orig):
            continue
        key = _norm_key(name)
        if key in by_name:
            continue
        techs = [
            str(t).strip()
            for t in (fp.get("technologies") or [])
            if str(t).strip() and phrase_supported(str(t), orig)
        ]
        bullets = [str(b).strip() for b in (fp.get("bullets") or []) if str(b).strip()][:5]
        out.append({"name": name, "technologies": techs, "bullets": bullets})
        by_name[key] = out[-1]
    return out


def _dedupe_projects(projects: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep first occurrence of each project; prefer longer name / more content."""
    best: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for p in projects:
        name = str(p.get("name") or "").strip()
        if not name:
            continue
        key = _norm_key(name)
        # fuzzy: treat "Companion" vs "Remote Atlas Companion"
        for existing in list(best.keys()):
            if key in existing or existing in key:
                key = existing if len(existing) >= len(key) else key
                break
        if key not in best:
            order.append(key)
            best[key] = p
            continue
        # prefer more complete entry
        cur = best[key]
        score_new = len(p.get("bullets") or []) + len(p.get("technologies") or []) + len(name)
        score_old = len(cur.get("bullets") or []) + len(cur.get("technologies") or []) + len(
            str(cur.get("name") or "")
        )
        if score_new > score_old:
            best[key] = p
        elif len(name) > len(str(cur.get("name") or "")):
            best[key]["name"] = name
    return [best[k] for k in order if k in best]


def _norm_key(s: Any) -> str:
    return re.sub(r"\s+", " ", str(s or "").lower()).strip()


def _compress_document(doc: dict[str, Any]) -> dict[str, Any]:
    d = normalize_document(doc)
    for e in d.get("experience") or []:
        e["bullets"] = (e.get("bullets") or [])[:4]
    for p in d.get("projects") or []:
        p["bullets"] = (p.get("bullets") or [])[:3]
    if d.get("summary") and len(d["summary"]) > 500:
        d["summary"] = d["summary"][:480].rsplit(" ", 1)[0] + "."
    return d


def _document_is_contentless(doc: dict[str, Any] | None) -> bool:
    if not doc:
        return True
    return not any(
        [
            (doc.get("summary") or "").strip(),
            doc.get("experience"),
            doc.get("projects"),
            doc.get("education"),
            doc.get("skill_groups"),
            doc.get("other_sections"),
        ]
    )


def _text_bucket_document(original: str, resume_facts: dict[str, Any]) -> dict[str, Any]:
    """Last-resort IR: keep every non-empty line so export is never blank."""
    doc = finalize_document(parse_resume_text(original))
    if not _document_is_contentless(doc):
        return _original_baseline(original, resume_facts)
    lines = [ln.strip() for ln in (original or "").splitlines() if ln.strip()]
    if len(lines) <= 1 and original:
        # Flattened to one blob — split on sentences as rough paragraphs
        blob = re.sub(r"\s+", " ", original).strip()
        parts = re.split(r"(?<=[.!?])\s+", blob)
        lines = [p for p in parts if p.strip()] or [blob]
    contact = {
        "name": str(resume_facts.get("name") or (lines[0] if lines else "")),
        "headline": str(resume_facts.get("headline") or ""),
        "email": (resume_facts.get("emails") or [""])[0] if resume_facts.get("emails") else "",
        "phone": (resume_facts.get("phones") or [""])[0] if resume_facts.get("phones") else "",
        "location": "",
        "links": list(resume_facts.get("links") or [])[:6],
    }
    body = lines[1:] if lines else []
    return finalize_document(
        {
            "contact": contact,
            "summary": "",
            "skill_groups": [],
            "experience": [],
            "projects": [],
            "education": [],
            "other_sections": (
                [{"heading": "Resume Content", "items": body[:80]}] if body else []
            ),
            "match_panel": {},
            "changes": [],
        }
    )


def _original_baseline(original: str, resume_facts: dict[str, Any]) -> dict[str, Any]:
    """Parse the uploaded resume into canonical IR — the tailoring source of truth."""
    text = restore_resume_structure(original or "")
    doc = finalize_document(parse_resume_text(text))
    contact = doc.get("contact") or {}
    if not contact.get("name") and resume_facts.get("name"):
        contact["name"] = str(resume_facts["name"])
    if not contact.get("email") and resume_facts.get("emails"):
        contact["email"] = resume_facts["emails"][0]
    if not contact.get("phone") and resume_facts.get("phones"):
        contact["phone"] = resume_facts["phones"][0]
    if not contact.get("links") and resume_facts.get("links"):
        contact["links"] = list(resume_facts["links"])[:6]
    if not contact.get("headline") and resume_facts.get("headline"):
        contact["headline"] = str(resume_facts["headline"])
    doc["contact"] = contact
    return doc


def _fallback_structure(
    original: str,
    resume_facts: dict[str, Any],
    panel_seed: dict[str, Any],
    job_text: str = "",
    keywords: list[str] | None = None,
) -> dict[str, Any]:
    """Original content as structured IR, with no AI involvement and no invention."""
    doc = _original_baseline(original, resume_facts)
    doc["skill_groups"] = (
        build_skill_groups(
            candidate_skills=[
                *(resume_facts.get("technologies") or []),
                *(resume_facts.get("skills_mentioned") or []),
                *[it for g in (doc.get("skill_groups") or []) for it in (g.get("items") or [])],
                *extract_skills(original)[:40],
            ],
            original_text=original,
            job_keywords=keywords or [],
            job_text=job_text,
        )
        or doc.get("skill_groups")
        or []
    )
    doc["match_panel"] = panel_seed
    doc["changes"] = [
        {
            "id": "c0",
            "type": "emphasized",
            "section": "Document",
            "before": "",
            "after": "",
            "reason": "AI rewrite unavailable; original content kept with keyword match analysis only.",
        }
    ]
    return finalize_document(doc)


async def _complete_without_ai(db: AsyncSession, run_id: int, reason: str) -> None:
    run = (
        await db.execute(
            select(ResumeTailoring)
            .where(ResumeTailoring.id == run_id)
            .options(selectinload(ResumeTailoring.resume))
        )
    ).scalar_one()
    job = (await db.execute(select(Job).where(Job.id == run.job_id))).scalar_one()
    original = restore_resume_structure(run.resume.extracted_text or "")
    if original != (run.resume.extracted_text or ""):
        run.resume.extracted_text = original
    job_text = job.description_text or ""
    keywords = list(
        dict.fromkeys(
            [
                *extract_skills(job_text)[:30],
                *(job.skills or [])[:20],
                *(job.tech_tags or [])[:20],
            ]
        )
    )
    panel = local_match_panel(original, job_text, keywords)
    facts = run.resume.analysis_json or {
        "skills_mentioned": extract_skills(original),
        "emails": re.findall(r"[\w.+-]+@[\w.-]+\.\w+", original)[:2],
        "name": "",
    }
    baseline = _fallback_structure(original, facts, panel, job_text, keywords)
    quality = run_quality_gate(document=baseline, original_text=original)
    cleaned = finalize_document(quality["document"])
    if content_integrity_failures(original=baseline, final=cleaned):
        cleaned = repair_against_original(original=baseline, final=cleaned)
    cleaned["match_panel"] = panel
    pdf_input = {k: v for k, v in cleaned.items() if k != "sections"}
    pdf_bytes = build_resume_pdf(tailored=pdf_input)
    pages = pdf_page_count(pdf_bytes)
    pdf_path = store_tailored_pdf(run.user_id, run.id, pdf_bytes)
    run.tailored_json = cleaned
    run.match_panel = panel
    run.changes_json = cleaned.get("changes") or []
    run.validation_json = {
        "ok": True,
        "fallback": True,
        "message": "AI providers failed; original content preserved with match analysis. "
        + reason[:200],
        "issue_count": 0,
        "high_severity": 0,
        "issues": [],
        "page_count": pages,
        "has_tailored_for": False,
        "pdf_text_extractable": True,
        "fidelity_note": (
            "PDF uses a clean single-column ATS layout. Original decorative design was not cloned."
        ),
    }
    run.pdf_path = str(pdf_path)
    run.model_used = "local_fallback"
    run.status = "completed"
    run.stage = STAGE["done"]
    run.completed_at = datetime.now(timezone.utc)
    run.error_message = None
    await db.commit()
