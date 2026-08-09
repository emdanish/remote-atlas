"""Factual validation: original resume is the sole source of truth."""

from __future__ import annotations

import re
from typing import Any

from app.resume.schema import document_plain_text, normalize_document

# Metric patterns that must appear in the original if claimed in the tailored text
_METRIC_RE = re.compile(
    r"(?:\d+(?:\.\d+)?\s*%|\b\d{1,3}(?:,\d{3})+(?:\+)?\b|\b\d+\s*(?:x|times)\b)",
    re.I,
)

_MULTI_TECH = [
    "machine learning",
    "deep learning",
    "computer vision",
    "natural language processing",
    "rest api",
    "rest apis",
    "graphql",
    "ci/cd",
    "unit testing",
    "test driven",
    "pair programming",
    "object oriented",
    "full stack",
    "front end",
    "back end",
    "react native",
    "node.js",
    "next.js",
    "vue.js",
    ".net",
    "c#",
    "c++",
    "amazon web services",
    "google cloud",
    "microsoft azure",
    "pgvector",
    "prompt engineering",
]


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").lower()).strip()


def original_phrase_index(original: str) -> str:
    return _norm(original)


def extract_metrics(text: str) -> set[str]:
    return {_norm(m.group(0)) for m in _METRIC_RE.finditer(text or "")}


def unsupported_metrics(original: str, tailored: str) -> list[str]:
    orig = extract_metrics(original)
    bad: list[str] = []
    for m in extract_metrics(tailored):
        if m not in orig and m not in _norm(original):
            bad.append(m)
    return bad


def phrase_supported(phrase: str, original_norm: str) -> bool:
    p = _norm(phrase)
    if not p:
        return True
    if p in original_norm:
        return True
    tokens = [
        t
        for t in re.findall(r"[a-z0-9+#.]{2,}", p)
        if t
        not in {
            "and",
            "the",
            "for",
            "with",
            "using",
            "from",
            "into",
            "that",
            "this",
            "able",
        }
    ]
    if not tokens:
        return True
    hits = sum(1 for t in tokens if t in original_norm)
    if len(tokens) <= 3:
        return hits == len(tokens)
    return hits / len(tokens) >= 0.85


def validate_tailored_payload(
    *,
    original_text: str,
    tailored: dict[str, Any],
    job_keywords: list[str] | None = None,
) -> dict[str, Any]:
    """
    Compare AI output to the original resume.

    Accepts legacy sections payload or structured IR; returns cleaned structured document.
    """
    original_norm = original_phrase_index(original_text)
    job_kw = {_norm(k) for k in (job_keywords or []) if k}
    issues: list[dict[str, Any]] = []

    raw = normalize_document(tailored)
    cleaned = {
        "contact": dict(raw.get("contact") or {}),
        "summary": raw.get("summary") or "",
        "skill_groups": [],
        "experience": [],
        "projects": [],
        "education": [],
        "other_sections": [],
        "changes": [],
        "match_panel": raw.get("match_panel") or {},
    }

    # Contact entity grounding (soft — blank unsupported)
    for field in ("name", "headline", "email", "phone", "location"):
        val = cleaned["contact"].get(field) or ""
        if val and field != "headline" and not phrase_supported(str(val), original_norm):
            # emails often match pattern in original even if spacing differs
            if field == "email" and _norm(str(val)) in original_norm:
                continue
            issues.append(
                {
                    "severity": "medium",
                    "kind": "unsupported_contact",
                    "field": field,
                    "value": val,
                    "action": "cleared",
                }
            )
            cleaned["contact"][field] = ""
        elif field == "headline" and val and not phrase_supported(str(val), original_norm):
            # allow short conservative titles if generic SWE language + supported
            if not _headline_allowed(str(val), original_norm):
                issues.append(
                    {
                        "severity": "medium",
                        "kind": "unsupported_headline",
                        "value": val,
                        "action": "cleared",
                    }
                )
                cleaned["contact"]["headline"] = ""

    link_out = []
    for link in cleaned["contact"].get("links") or []:
        if phrase_supported(str(link), original_norm) or _norm(str(link)) in original_norm:
            link_out.append(str(link))
        else:
            # allow domain if present
            domain = re.sub(r"^https?://(www\.)?", "", str(link), flags=re.I).split("/")[0]
            if domain and domain.lower() in original_norm:
                link_out.append(str(link))
            else:
                issues.append(
                    {
                        "severity": "low",
                        "kind": "unsupported_link",
                        "value": link,
                        "action": "dropped",
                    }
                )
    cleaned["contact"]["links"] = link_out

    # Summary
    if cleaned["summary"]:
        bad_m = unsupported_metrics(original_text, cleaned["summary"])
        if bad_m:
            issues.append(
                {
                    "severity": "high",
                    "kind": "invented_metric",
                    "value": cleaned["summary"],
                    "metrics": bad_m,
                    "action": "cleared_summary",
                }
            )
            cleaned["summary"] = _pick_summary_from_original(original_text)
        elif not _bullet_grounded(str(cleaned["summary"]), original_norm, loose=True):
            issues.append(
                {
                    "severity": "medium",
                    "kind": "unsupported_summary",
                    "action": "replaced_from_original",
                }
            )
            cleaned["summary"] = _pick_summary_from_original(original_text)

    # Skills — only supported
    for g in raw.get("skill_groups") or []:
        cat = str(g.get("category") or "Skills")[:60]
        items_ok = []
        for it in g.get("items") or []:
            s = str(it).strip()
            if not s:
                continue
            if phrase_supported(s, original_norm):
                items_ok.append(s)
            else:
                issues.append(
                    {
                        "severity": "high",
                        "kind": "unsupported_skill",
                        "value": s,
                        "action": "dropped",
                    }
                )
        if items_ok:
            cleaned["skill_groups"].append({"category": cat, "items": items_ok})

    # Experience
    for role in raw.get("experience") or []:
        title = str(role.get("title") or "")
        org = str(role.get("org") or "")
        dates = str(role.get("dates") or "")
        location = str(role.get("location") or "")
        for label, val in (("title", title), ("org", org), ("dates", dates), ("location", location)):
            if val and not phrase_supported(val, original_norm):
                issues.append(
                    {
                        "severity": "high",
                        "kind": "unsupported_entity",
                        "field": label,
                        "value": val,
                        "action": "reverted",
                    }
                )
                if label == "title":
                    title = ""
                elif label == "org":
                    org = ""
                elif label == "dates":
                    dates = ""
                else:
                    location = ""
        bullets_out = []
        for bullet in role.get("bullets") or []:
            b = str(bullet).strip()
            if not b:
                continue
            metrics_bad = unsupported_metrics(original_text, b)
            if metrics_bad:
                issues.append(
                    {
                        "severity": "high",
                        "kind": "invented_metric",
                        "value": b,
                        "metrics": metrics_bad,
                        "action": "dropped",
                    }
                )
                continue
            if not _bullet_grounded(b, original_norm):
                issues.append(
                    {
                        "severity": "high",
                        "kind": "unsupported_claim",
                        "value": b,
                        "action": "dropped",
                    }
                )
                continue
            bullets_out.append(b)
        if title or org or bullets_out:
            cleaned["experience"].append(
                {
                    "title": title,
                    "org": org,
                    "location": location,
                    "dates": dates,
                    "bullets": bullets_out,
                }
            )

    # Projects — preserve when grounded
    for proj in raw.get("projects") or []:
        name = str(proj.get("name") or "")
        if name and not phrase_supported(name, original_norm):
            # allow if tokens mostly present
            if not _bullet_grounded(name, original_norm, loose=True):
                issues.append(
                    {
                        "severity": "high",
                        "kind": "unsupported_project",
                        "value": name,
                        "action": "dropped_name",
                    }
                )
                name = ""
        techs_ok = []
        for t in proj.get("technologies") or []:
            s = str(t).strip()
            if s and phrase_supported(s, original_norm):
                techs_ok.append(s)
            elif s:
                issues.append(
                    {
                        "severity": "high",
                        "kind": "unsupported_skill",
                        "value": s,
                        "action": "dropped_from_project",
                    }
                )
        bullets_out = []
        for bullet in proj.get("bullets") or []:
            b = str(bullet).strip()
            if not b:
                continue
            if unsupported_metrics(original_text, b):
                issues.append(
                    {
                        "severity": "high",
                        "kind": "invented_metric",
                        "value": b,
                        "action": "dropped",
                    }
                )
                continue
            if not _bullet_grounded(b, original_norm):
                issues.append(
                    {
                        "severity": "high",
                        "kind": "unsupported_claim",
                        "value": b,
                        "action": "dropped",
                    }
                )
                continue
            bullets_out.append(b)
        if name or bullets_out:
            cleaned["projects"].append(
                {"name": name or "Project", "technologies": techs_ok, "bullets": bullets_out}
            )

    # Education
    for edu in raw.get("education") or []:
        school = str(edu.get("school") or "")
        degree = str(edu.get("degree") or "")
        dates = str(edu.get("dates") or "")
        for label, val in (("school", school), ("degree", degree), ("dates", dates)):
            if val and not phrase_supported(val, original_norm):
                issues.append(
                    {
                        "severity": "high",
                        "kind": "unsupported_entity",
                        "field": label,
                        "value": val,
                        "action": "reverted",
                    }
                )
                if label == "school":
                    school = ""
                elif label == "degree":
                    degree = ""
                else:
                    dates = ""
        details = []
        for d in edu.get("details") or []:
            ds = str(d).strip()
            if ds and _bullet_grounded(ds, original_norm, loose=True):
                if not unsupported_metrics(original_text, ds):
                    details.append(ds)
        if school or degree or details:
            cleaned["education"].append(
                {
                    "school": school,
                    "degree": degree,
                    "dates": dates,
                    "details": details,
                }
            )

    # Other sections (validated + merge duplicates by heading)
    from app.resume.schema import merge_other_sections

    others_raw: list[dict[str, Any]] = []
    for sec in raw.get("other_sections") or []:
        heading = str(sec.get("heading") or "Additional")
        if "summary" in heading.lower():
            continue
        items = []
        for it in sec.get("items") or []:
            s = str(it).strip()
            if s and _bullet_grounded(s, original_norm, loose=True) and not unsupported_metrics(
                original_text, s
            ):
                items.append(s)
        if items:
            others_raw.append({"heading": heading, "items": items})
    cleaned["other_sections"] = merge_other_sections(others_raw)

    # Match panel
    panel = cleaned.get("match_panel") or {}
    strong = [_norm(x) for x in panel.get("strong_matches") or [] if x]
    missing = [_norm(x) for x in panel.get("missing") or [] if x]
    emphasized = [str(x) for x in panel.get("emphasized") or [] if x]
    gaps = [str(x) for x in panel.get("potential_gaps") or [] if x]

    strong_ok = [s for s in strong if phrase_supported(s, original_norm)]
    for s in strong:
        if s not in strong_ok:
            issues.append(
                {
                    "severity": "medium",
                    "kind": "false_match",
                    "value": s,
                    "action": "moved_to_missing",
                }
            )
            if s not in missing:
                missing.append(s)

    for kw in job_kw:
        if kw and not phrase_supported(kw, original_norm) and kw not in missing:
            missing.append(kw)

    cleaned["match_panel"] = {
        "strong_matches": strong_ok[:30],
        "emphasized": emphasized[:20],
        "missing": missing[:40],
        "potential_gaps": gaps[:15],
        "note": "Missing items are gaps — never invent them on the resume.",
    }

    # Changes
    changes_out: list[dict[str, Any]] = []
    for ch in raw.get("changes") or tailored.get("changes") or []:
        if not isinstance(ch, dict):
            continue
        after = str(ch.get("after") or "")
        before = str(ch.get("before") or "")
        if after and (
            unsupported_metrics(original_text, after)
            or not _bullet_grounded(after, original_norm, loose=True)
        ):
            issues.append(
                {
                    "severity": "high",
                    "kind": "rejected_change",
                    "value": after,
                    "action": "dropped",
                }
            )
            continue
        changes_out.append(
            {
                "id": str(ch.get("id") or f"c{len(changes_out)+1}"),
                "type": str(ch.get("type") or "modified"),
                "section": str(ch.get("section") or ""),
                "before": before[:2000],
                "after": after[:2000],
                "reason": str(ch.get("reason") or "Improved wording for the role.")[:500],
            }
        )
    cleaned["changes"] = changes_out

    # Build legacy sections mirror for older UI
    from app.resume.schema import to_legacy_sections

    cleaned["sections"] = to_legacy_sections(cleaned)

    high = sum(1 for i in issues if i.get("severity") == "high")
    has_body = bool(
        cleaned["summary"]
        or cleaned["experience"]
        or cleaned["projects"]
        or cleaned["skill_groups"]
        or cleaned["education"]
    )
    return {
        "ok": has_body and (high < 25),
        "issue_count": len(issues),
        "high_severity": high,
        "issues": issues[:50],
        "tailored": cleaned,
    }


def merge_tailored_onto_original(
    *,
    original: dict[str, Any],
    tailored: dict[str, Any],
) -> dict[str, Any]:
    """Apply AI edits on top of the parsed original resume.

    The original document is the source of truth for structure and facts; the AI
    may only supply better wording for entries that already exist, plus grounded
    additions. Anything the AI omitted is taken from the original, so an
    incomplete or truncated AI response can never delete a section.
    """
    from app.resume.schema import finalize_document, section_heading_key

    base = finalize_document(original)
    ai = finalize_document(tailored)

    out: dict[str, Any] = {}

    # Contact is immutable except the headline, which is a positioning line.
    contact = dict(base.get("contact") or {})
    ai_contact = ai.get("contact") or {}
    for field in ("name", "email", "phone", "location"):
        if not contact.get(field) and ai_contact.get(field):
            contact[field] = ai_contact[field]
    if ai_contact.get("headline"):
        contact["headline"] = ai_contact["headline"]
    if not contact.get("links"):
        contact["links"] = list(ai_contact.get("links") or [])
    out["contact"] = contact

    out["summary"] = _clean_str(ai.get("summary")) or _clean_str(base.get("summary"))

    # Curating skills for the role is expected; losing almost all of them is not.
    base_skills = base.get("skill_groups") or []
    ai_skills = ai.get("skill_groups") or []
    base_count = sum(len(g.get("items") or []) for g in base_skills)
    ai_count = sum(len(g.get("items") or []) for g in ai_skills)
    out["skill_groups"] = ai_skills if ai_count >= max(1, base_count * 0.25) else base_skills

    out["experience"] = _merge_entries(
        base.get("experience") or [],
        ai.get("experience") or [],
        identity=lambda e: f"{e.get('org') or ''} {e.get('title') or ''}",
        apply=_apply_experience,
    )
    out["projects"] = _merge_entries(
        base.get("projects") or [],
        ai.get("projects") or [],
        identity=lambda p: str(p.get("name") or ""),
        apply=_apply_project,
    )
    out["education"] = _merge_entries(
        base.get("education") or [],
        ai.get("education") or [],
        identity=lambda e: f"{e.get('school') or ''} {e.get('degree') or ''}",
        apply=_apply_education,
    )

    # Other sections: originals win (References etc. are factual, not tailorable)
    others: list[dict[str, Any]] = [dict(s) for s in base.get("other_sections") or []]
    have = {section_heading_key(str(s.get("heading") or "")) for s in others}
    for sec in ai.get("other_sections") or []:
        if section_heading_key(str(sec.get("heading") or "")) not in have:
            others.append(dict(sec))
    out["other_sections"] = others

    out["changes"] = ai.get("changes") or []
    out["match_panel"] = ai.get("match_panel") or base.get("match_panel") or {}
    return finalize_document(out)


def _clean_str(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _entity_key(text: str) -> str:
    return re.sub(r"[^a-z0-9 ]", " ", _norm(text)).strip()


def _entries_match(a: str, b: str) -> bool:
    ka, kb = _entity_key(a), _entity_key(b)
    if not ka or not kb:
        return False
    if ka == kb or ka in kb or kb in ka:
        return True
    ta = {t for t in ka.split() if len(t) > 2}
    tb = {t for t in kb.split() if len(t) > 2}
    if not ta or not tb:
        return False
    overlap = len(ta & tb) / min(len(ta), len(tb))
    return overlap >= 0.6


def _merge_entries(
    base_entries: list[dict[str, Any]],
    ai_entries: list[dict[str, Any]],
    *,
    identity,
    apply,
) -> list[dict[str, Any]]:
    """Keep every original entry, upgraded with matching AI wording; append extras."""
    used: set[int] = set()
    out: list[dict[str, Any]] = []
    for entry in base_entries:
        match = None
        for idx, cand in enumerate(ai_entries):
            if idx in used:
                continue
            if _entries_match(identity(entry), identity(cand)):
                match = cand
                used.add(idx)
                break
        out.append(apply(entry, match) if match else dict(entry))
    for idx, cand in enumerate(ai_entries):
        if idx not in used and any(str(v).strip() for v in cand.values() if not isinstance(v, list)):
            out.append(dict(cand))
    return out


def _apply_experience(base: dict[str, Any], ai: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": _clean_str(base.get("title")) or _clean_str(ai.get("title")),
        "org": _clean_str(base.get("org")) or _clean_str(ai.get("org")),
        "location": _clean_str(base.get("location")) or _clean_str(ai.get("location")),
        "dates": _clean_str(base.get("dates")) or _clean_str(ai.get("dates")),
        "bullets": list(ai.get("bullets") or []) or list(base.get("bullets") or []),
    }


def _apply_project(base: dict[str, Any], ai: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": _clean_str(base.get("name")) or _clean_str(ai.get("name")),
        "technologies": list(base.get("technologies") or []) or list(ai.get("technologies") or []),
        "bullets": list(ai.get("bullets") or []) or list(base.get("bullets") or []),
    }


def _apply_education(base: dict[str, Any], ai: dict[str, Any]) -> dict[str, Any]:
    # Education is factual: keep the original values, allow AI only to fill blanks.
    return {
        "school": _clean_str(base.get("school")) or _clean_str(ai.get("school")),
        "degree": _clean_str(base.get("degree")) or _clean_str(ai.get("degree")),
        "dates": _clean_str(base.get("dates")) or _clean_str(ai.get("dates")),
        "details": list(base.get("details") or []) or list(ai.get("details") or []),
    }


def content_integrity_failures(
    *,
    original: dict[str, Any],
    final: dict[str, Any],
) -> list[str]:
    """Hard checks comparing the tailored document against the original resume."""
    from app.resume.schema import assert_section_uniqueness, section_heading_key

    failures: list[str] = []

    if not _clean_str((final.get("contact") or {}).get("name")) and _clean_str(
        (original.get("contact") or {}).get("name")
    ):
        failures.append("missing_name")
    for field in ("email", "phone"):
        if _clean_str((original.get("contact") or {}).get(field)) and not _clean_str(
            (final.get("contact") or {}).get(field)
        ):
            failures.append(f"missing_contact:{field}")

    if _clean_str(original.get("summary")) and not _clean_str(final.get("summary")):
        failures.append("missing_summary")
    if (original.get("skill_groups") or []) and not (final.get("skill_groups") or []):
        failures.append("missing_skills")

    for field in ("experience", "projects", "education"):
        base_n = len(original.get(field) or [])
        final_n = len(final.get(field) or [])
        if final_n < base_n:
            failures.append(f"lost_{field}:{base_n}->{final_n}")

    base_keys = {
        section_heading_key(str(s.get("heading") or ""))
        for s in original.get("other_sections") or []
    }
    final_keys = {
        section_heading_key(str(s.get("heading") or ""))
        for s in final.get("other_sections") or []
    }
    for key in sorted(base_keys - final_keys):
        failures.append(f"lost_section:{key}")
    if "references" in final_keys and "references" not in base_keys:
        failures.append("invented_references")

    if not any(
        [
            _clean_str(final.get("summary")),
            final.get("experience"),
            final.get("projects"),
            final.get("education"),
            final.get("skill_groups"),
        ]
    ):
        failures.append("empty_document")

    failures.extend(assert_section_uniqueness(final))
    return failures


def repair_against_original(
    *,
    original: dict[str, Any],
    final: dict[str, Any],
) -> dict[str, Any]:
    """Restore anything the tailoring pipeline dropped, using the original as truth."""
    return merge_tailored_onto_original(original=original, tailored=final)


def _headline_allowed(headline: str, original_norm: str) -> bool:
    h = _norm(headline)
    banned = ("principal", "staff engineer", "director", "vp ", "vice president", "head of")
    if any(b in h for b in banned) and not phrase_supported(headline, original_norm):
        return False
    if "senior" in h and "senior" not in original_norm:
        return False
    # must at least look like an eng title and engineer/developer in resume
    if any(w in original_norm for w in ("engineer", "developer", "software", "programmer")):
        if any(w in h for w in ("engineer", "developer", "scientist", "intern", "designer")):
            return True
    return phrase_supported(headline, original_norm)


def _bullet_grounded(text: str, original_norm: str, *, loose: bool = False) -> bool:
    tokens = [
        t
        for t in re.findall(r"[a-z0-9+#.]{3,}", _norm(text))
        if t
        not in {
            "with",
            "using",
            "from",
            "that",
            "this",
            "were",
            "have",
            "been",
            "their",
            "about",
            "into",
            "over",
            "through",
            "strong",
            "experience",
            "skilled",
            "worked",
            "developed",
            "built",
            "managed",
            "created",
            "implemented",
            "improved",
            "responsible",
            "including",
            "systems",
            "application",
            "applications",
            "software",
            "services",
            "platform",
            "projects",
            "project",
            "team",
            "teams",
            "business",
            "requirements",
            "user",
            "users",
            "data",
            "based",
            "engineering",
            "knowledge",
            "platform",
        }
    ]
    if not tokens:
        return True
    hits = sum(1 for t in tokens if t in original_norm)
    ratio = hits / max(len(tokens), 1)
    return ratio >= (0.55 if loose else 0.65)


def _pick_summary_from_original(original: str) -> str:
    lines = [ln.strip() for ln in original.splitlines() if ln.strip()]
    for ln in lines[:12]:
        if len(ln) > 40 and not re.match(
            r"^(experience|education|skills|projects|technical)\b", ln, re.I
        ):
            return ln[:600]
    return (lines[0] if lines else "")[:600]


def local_match_panel(original: str, job_text: str, job_keywords: list[str]) -> dict[str, Any]:
    orig = original_phrase_index(original)
    strong: list[str] = []
    missing: list[str] = []
    for kw in job_keywords:
        k = _norm(kw)
        if not k:
            continue
        if phrase_supported(k, orig):
            if k not in strong:
                strong.append(k)
        else:
            if k not in missing:
                missing.append(k)
    from app.pipeline.enrich import extract_skills

    for s in extract_skills(job_text):
        k = _norm(s)
        if phrase_supported(k, orig):
            if k not in strong:
                strong.append(k)
        else:
            if k not in missing:
                missing.append(k)
    return {
        "strong_matches": strong[:30],
        "emphasized": [],
        "missing": missing[:40],
        "potential_gaps": missing[:8],
        "note": "Missing items are gaps — never invent them on the resume.",
    }
