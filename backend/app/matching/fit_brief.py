"""Atlas Fit Brief — unique apply decision aid (not a generic cover-letter bot).

Produces a short, grounded brief:
- Fit ledger numbers (deterministic)
- Matched / missing stack
- Remote & Pakistan affinity signal
- Optional one-paragraph AI “should you apply?” with multi-provider fallback
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from app.ai.provider import AIProviderError, chat_completion
from app.matching.scoring import MatchBreakdown, score_job_breakdown
from app.models.job import Job

logger = logging.getLogger(__name__)


def _deterministic_narrative(job: Job, bd: MatchBreakdown) -> str:
    company = job.company_name or "This company"
    title = job.title or "the role"
    if bd.total >= 70:
        opener = f"Strong Atlas fit for {title} at {company}."
    elif bd.total >= 50:
        opener = f"Solid but not perfect fit for {title} at {company}."
    else:
        opener = f"Stretch role: {title} at {company} — apply only if you’re targeting growth."

    bits: list[str] = [opener]
    if bd.matched_skills:
        bits.append(f"Your stack hits: {', '.join(bd.matched_skills[:5])}.")
    if bd.missing_skills:
        bits.append(f"Likely gaps to address in your application: {', '.join(bd.missing_skills[:4])}.")
    if bd.pakistan >= 8:
        bits.append("Listing signals openness to Pakistan / worldwide remote candidates.")
    elif bd.remote >= 10:
        bits.append("Fully remote workplace — confirm time-zone expectations on the career page.")
    bits.append("Always apply on the official career page shown on Remote Atlas.")
    return " ".join(bits)


async def build_fit_brief(
    job: Job,
    *,
    skills: list[str] | set[str],
    level: str,
    remote_pref: str,
    desired_roles: list[str] | None,
    cities: list[str] | None,
    location_preference: str | None,
    pakistan_friendly: bool,
    use_ai: bool = True,
) -> dict[str, Any]:
    bd = score_job_breakdown(
        job,
        skills=skills,
        level=level,
        remote_pref=remote_pref,
        desired_roles=desired_roles,
        cities=cities,
        location_preference=location_preference,
        pakistan_friendly=pakistan_friendly,
    )
    narrative = _deterministic_narrative(job, bd)
    provider = "lexicon"
    tips: list[str] = []

    if bd.missing_skills:
        tips.append(f"Call out related experience for: {', '.join(bd.missing_skills[:3])}.")
    if bd.matched_skills:
        tips.append(f"Lead your pitch with: {', '.join(bd.matched_skills[:3])}.")
    if job.pakistan_friendly:
        tips.append("Mention timezone flexibility (PK/UTC+5) if you work async.")
    tips.append("Use the official apply URL — never third-party apply hosts.")

    if use_ai:
        try:
            system = (
                "You help job seekers decide whether to apply to a real remote role. "
                "Return ONLY compact JSON: "
                '{"verdict":"apply|maybe|skip","narrative":"2-3 sentences","tips":["..."]}. '
                "Ground only in the provided skills and job facts. No fluff. No salary invention."
            )
            user_payload = {
                "job_title": job.title,
                "company": job.company_name,
                "workplace": job.workplace_type,
                "career_stage": job.career_stage,
                "pakistan_friendly": job.pakistan_friendly,
                "location": job.location_raw,
                "job_skills": list(_safe_slice(job.skills or job.tech_tags or [], 20)),
                "profile_skills": list(_safe_slice(list(skills), 30)),
                "fit_total": bd.total,
                "matched": bd.matched_skills,
                "missing": bd.missing_skills,
                "snippet": (job.description_text or "")[:1200],
            }
            raw = await chat_completion(
                system=system,
                user=json.dumps(user_payload),
                temperature=0.2,
                max_tokens=400,
            )
            m = re.search(r"\{.*\}", raw, re.S)
            if m:
                payload = json.loads(m.group(0))
                narrative = str(payload.get("narrative") or narrative)[:800]
                ai_tips = [str(t) for t in (payload.get("tips") or []) if t][:5]
                if ai_tips:
                    tips = ai_tips
                provider = "ai"
        except (AIProviderError, Exception) as exc:  # noqa: BLE001
            logger.info("Fit brief AI fallback: %s", exc)
            provider = "lexicon"

    return {
        "job_id": job.id,
        "score": bd.total,
        "breakdown": bd.as_dict(),
        "verdict": _verdict(bd.total),
        "narrative": narrative,
        "tips": tips[:5],
        "provider": provider,
        "apply_url": job.apply_url,
        "career_page_url": job.career_page_url,
    }


def _verdict(total: float) -> str:
    if total >= 70:
        return "apply"
    if total >= 45:
        return "maybe"
    return "skip"


def _safe_slice(items: list[Any], n: int) -> list[Any]:
    out = []
    for x in items:
        if x is None:
            continue
        out.append(str(x)[:80])
        if len(out) >= n:
            break
    return out
