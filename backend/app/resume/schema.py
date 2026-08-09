"""Canonical structured resume IR used by validation, quality, and PDF."""

from __future__ import annotations

import re
from typing import Any


SUMMARY_HEADINGS = {
    "summary",
    "professional summary",
    "profile",
    "objective",
    "about",
    "about me",
    "career summary",
    "personal summary",
}

SKILL_HEADINGS = {
    "skills",
    "technical skills",
    "technologies",
    "tech stack",
    "core competencies",
    "technical competencies",
    "tools",
}

EXPERIENCE_HEADINGS = {
    "experience",
    "professional experience",
    "work experience",
    "work history",
    "employment",
    "employment history",
}

PROJECT_HEADINGS = {
    "projects",
    "personal projects",
    "selected projects",
    "key projects",
    "portfolio",
}

EDUCATION_HEADINGS = {
    "education",
    "academic background",
    "academics",
}

META_TEXT_RE = re.compile(
    r"(?i)\b("
    r"tailored\s+for|generated\s+for|optimized\s+for|prepared\s+for|"
    r"generated\s+by\s+ai|optimized\s+using\s+ai|ai[- ]generated|"
    r"powered\s+by\s+remote\s+atlas|created\s+with\s+remote\s+atlas|"
    r"job\s+match\s+score|ats\s+score"
    r")\b"
)


def _clean(s: Any) -> str:
    return re.sub(r"\s+", " ", str(s or "")).strip()


def _bullets(items: Any) -> list[str]:
    out: list[str] = []
    if not items:
        return out
    for it in items:
        t = _clean(it)
        if not t:
            continue
        t = re.sub(r"^[\u2022\-\*\u2013\u2014]+\s*", "", t)
        if t and t not in out:
            out.append(t)
    return out


def heading_kind(heading: str) -> str:
    """Map a heading to a core section kind, or "other" for custom sections.

    Only recognised core headings return a core kind. Unknown headings stay
    "other" so custom sections survive the pipeline intact.
    """
    key = section_heading_key(heading)
    return key if key in CORE_SECTION_KEYS else "other"


def section_heading_key(heading: str) -> str:
    """Normalize section titles so near-duplicates map to one logical section key.

    Examples that all map to the same key:
    - References / REFERENCES / professional references → references
    - Professional Summary / Summary / PROFILE → summary
    - Technical Skills / Skills → skills
    - Professional Experience / Work Experience → experience
    """
    h = _clean(heading).lower()
    h = re.sub(r"[^\w\s&+/]", " ", h)
    h = re.sub(r"\s+", " ", h).strip()
    aliases = {
        # core
        "summary": "summary",
        "professional summary": "summary",
        "profile": "summary",
        "objective": "summary",
        "about": "summary",
        "about me": "summary",
        "career summary": "summary",
        "personal summary": "summary",
        "skills": "skills",
        "technical skills": "skills",
        "technologies": "skills",
        "tech stack": "skills",
        "core competencies": "skills",
        "technical competencies": "skills",
        "tools": "skills",
        "experience": "experience",
        "professional experience": "experience",
        "work experience": "experience",
        "work history": "experience",
        "employment": "experience",
        "employment history": "experience",
        "projects": "projects",
        "personal projects": "projects",
        "selected projects": "projects",
        "key projects": "projects",
        "portfolio": "projects",
        "education": "education",
        "academic background": "education",
        "academics": "education",
        # other
        "reference": "references",
        "references": "references",
        "professional references": "references",
        "referees": "references",
        "certification": "certifications",
        "certifications": "certifications",
        "certificates": "certifications",
        "license": "licenses",
        "licenses": "licenses",
        "licences": "licenses",
        "award": "awards",
        "awards": "awards",
        "honors": "awards",
        "honours": "awards",
        "achievements": "awards",
        "languages": "languages",
        "language": "languages",
        "interests": "interests",
        "hobbies": "interests",
        "publications": "publications",
        "publication": "publications",
        "volunteer": "volunteering",
        "volunteering": "volunteering",
        "volunteer experience": "volunteering",
        "activities": "activities",
        "extracurricular": "activities",
        "additional information": "additional",
        "additional": "additional",
        "miscellaneous": "additional",
    }
    if h in aliases:
        return aliases[h]
    if h.endswith("s") and h[:-1] in aliases:
        return aliases[h[:-1]]
    if not h.endswith("s") and f"{h}s" in aliases:
        return aliases[f"{h}s"]
    # Tolerate a leading qualifier ("professional references") but never map an
    # unrelated custom heading ("leadership experience") onto a core section:
    # collapsing those would delete legitimate user content.
    words = h.split()
    if len(words) > 1 and words[0] in {"professional", "personal", "other", "my"}:
        tail = " ".join(words[1:])
        if tail in aliases:
            return aliases[tail]
    return h or "additional"


# Core keys rendered from structured IR fields (never also as other_sections)
CORE_SECTION_KEYS = frozenset(
    {"summary", "skills", "experience", "projects", "education"}
)


# Canonical display labels for merged other-sections
_SECTION_DISPLAY = {
    "references": "References",
    "certifications": "Certifications",
    "licenses": "Licenses",
    "awards": "Awards",
    "languages": "Languages",
    "interests": "Interests",
    "publications": "Publications",
    "volunteering": "Volunteering",
    "activities": "Activities",
    "additional": "Additional",
}

# Must never reappear as other_sections after structured fields exist
_CORE_SECTION_KEYS = set(CORE_SECTION_KEYS) | {
    "professional summary",
    "profile",
    "objective",
    "technical skills",
    "technologies",
    "tech stack",
    "professional experience",
    "work experience",
    "work history",
    "employment",
    "personal projects",
    "selected projects",
    "academic background",
}


def empty_document() -> dict[str, Any]:
    return {
        "contact": {
            "name": "",
            "headline": "",
            "email": "",
            "phone": "",
            "location": "",
            "links": [],
        },
        "summary": "",
        "skill_groups": [],
        "experience": [],
        "projects": [],
        "education": [],
        "other_sections": [],
        "changes": [],
        "match_panel": {},
    }


def normalize_document(raw: dict[str, Any] | None) -> dict[str, Any]:
    """
    Normalize AI/legacy section payloads into a single canonical document.

    Accepts:
    - new fields: skill_groups, experience, projects, education, headline
    - legacy: sections[] with job/paragraph/project blocks
    """
    raw = raw if isinstance(raw, dict) else {}
    doc = empty_document()

    contact = raw.get("contact") if isinstance(raw.get("contact"), dict) else {}
    doc["contact"] = {
        "name": _clean(contact.get("name") or raw.get("name")),
        "headline": _clean(contact.get("headline") or raw.get("headline") or raw.get("title")),
        "email": _clean(contact.get("email")),
        "phone": _clean(contact.get("phone")),
        "location": _clean(contact.get("location")),
        "links": [
            _clean(x)
            for x in (contact.get("links") or [])
            if _clean(x)
        ][:8],
    }

    summary = _clean(raw.get("summary"))
    if summary:
        doc["summary"] = _trim_summary(summary)

    # Skill groups (new)
    for g in raw.get("skill_groups") or raw.get("skills") or []:
        if isinstance(g, dict):
            cat = _clean(g.get("category") or g.get("name") or "Skills")
            items = [
                _clean(x)
                for x in (g.get("items") or g.get("skills") or g.get("technologies") or [])
                if _clean(x)
            ]
            if items:
                doc["skill_groups"].append({"category": cat, "items": items})
        elif isinstance(g, str) and _clean(g):
            # flat skill string → Collect later
            doc["skill_groups"].append({"category": "Skills", "items": [_clean(g)]})

    # Experience (new)
    for role in raw.get("experience") or raw.get("roles") or []:
        if not isinstance(role, dict):
            continue
        entry = {
            "title": _clean(role.get("title") or role.get("role")),
            "org": _clean(role.get("org") or role.get("company") or role.get("employer")),
            "location": _clean(role.get("location")),
            "dates": _clean(role.get("dates") or role.get("date")),
            "bullets": _bullets(role.get("bullets") or role.get("highlights")),
        }
        if any(entry.values()):
            doc["experience"].append(entry)

    # Projects (new)
    for proj in raw.get("projects") or []:
        if not isinstance(proj, dict):
            continue
        techs = [
            _clean(x)
            for x in (proj.get("technologies") or proj.get("tech") or proj.get("stack") or [])
            if _clean(x)
        ]
        entry = {
            "name": _clean(proj.get("name") or proj.get("title")),
            "technologies": techs,
            "bullets": _bullets(proj.get("bullets") or proj.get("highlights")),
        }
        # paragraph fallback
        if not entry["bullets"] and proj.get("description"):
            entry["bullets"] = _bullets([proj.get("description")])
        if entry["name"] or entry["bullets"]:
            doc["projects"].append(entry)

    # Education (new)
    for edu in raw.get("education") or []:
        if not isinstance(edu, dict):
            continue
        entry = {
            "school": _clean(edu.get("school") or edu.get("institution") or edu.get("org")),
            "degree": _clean(edu.get("degree") or edu.get("title") or edu.get("program")),
            "dates": _clean(edu.get("dates") or edu.get("date") or edu.get("years")),
            "details": _bullets(edu.get("details") or edu.get("bullets")),
        }
        if any([entry["school"], entry["degree"], entry["dates"], entry["details"]]):
            doc["education"].append(entry)

    # Legacy sections[] — only fill gaps (structured fields take precedence)
    has_exp = bool(doc["experience"])
    has_proj = bool(doc["projects"])
    has_edu = bool(doc["education"])
    has_skills = bool(doc["skill_groups"])

    for sec in raw.get("sections") or []:
        if not isinstance(sec, dict):
            continue
        kind = heading_kind(str(sec.get("heading") or ""))
        blocks = sec.get("blocks") or []
        if kind == "summary":
            for b in blocks:
                if not isinstance(b, dict):
                    continue
                text = _clean(b.get("text") or " ".join(_bullets(b.get("bullets"))))
                if text:
                    if not doc["summary"]:
                        doc["summary"] = _trim_summary(text)
            continue
        if kind == "skills":
            if not has_skills:
                _consume_skills_blocks(doc, blocks)
            continue
        if kind == "experience":
            if has_exp:
                continue
            for b in blocks:
                if not isinstance(b, dict):
                    continue
                if b.get("type") in ("job", "experience", "role") or b.get("title") or b.get("org"):
                    entry = {
                        "title": _clean(b.get("title")),
                        "org": _clean(b.get("org") or b.get("company")),
                        "location": _clean(b.get("location")),
                        "dates": _clean(b.get("dates")),
                        "bullets": _bullets(b.get("bullets")),
                    }
                    if not entry["bullets"] and b.get("text"):
                        entry["bullets"] = _split_paragraph_to_bullets(str(b.get("text")))
                    if any(entry.values()):
                        doc["experience"].append(entry)
                elif b.get("text"):
                    bullets = _split_paragraph_to_bullets(str(b.get("text")))
                    if bullets:
                        doc["experience"].append(
                            {
                                "title": "",
                                "org": "",
                                "location": "",
                                "dates": "",
                                "bullets": bullets,
                            }
                        )
            continue
        if kind == "projects":
            if has_proj:
                continue
            for b in blocks:
                if not isinstance(b, dict):
                    continue
                if b.get("type") == "project" or b.get("name"):
                    techs = [
                        _clean(x)
                        for x in (b.get("technologies") or b.get("tech") or [])
                        if _clean(x)
                    ]
                    entry = {
                        "name": _clean(b.get("name") or b.get("title")),
                        "technologies": techs,
                        "bullets": _bullets(b.get("bullets")),
                    }
                    if not entry["bullets"] and b.get("text"):
                        entry["bullets"] = _split_paragraph_to_bullets(str(b.get("text")))
                    if not entry["name"] and entry["bullets"]:
                        entry["name"] = entry["bullets"][0][:80]
                        entry["bullets"] = entry["bullets"][1:]
                    if entry["name"] or entry["bullets"]:
                        doc["projects"].append(entry)
                elif b.get("type") == "job":
                    entry = {
                        "name": _clean(b.get("title") or b.get("org")),
                        "technologies": [],
                        "bullets": _bullets(b.get("bullets")),
                    }
                    if entry["name"] or entry["bullets"]:
                        doc["projects"].append(entry)
                elif b.get("text"):
                    name, tech, bullets = _parse_project_blob(str(b.get("text")))
                    doc["projects"].append(
                        {"name": name, "technologies": tech, "bullets": bullets}
                    )
            continue
        if kind == "education":
            if has_edu:
                continue
            for b in blocks:
                if not isinstance(b, dict):
                    continue
                if b.get("type") in ("education", "job") or b.get("school") or b.get("degree"):
                    entry = {
                        "school": _clean(b.get("school") or b.get("org")),
                        "degree": _clean(b.get("degree") or b.get("title")),
                        "dates": _clean(b.get("dates")),
                        "details": _bullets(b.get("bullets") or b.get("details")),
                    }
                    if not entry["details"] and b.get("text"):
                        entry["details"] = _split_paragraph_to_bullets(str(b.get("text")))
                    if any([entry["school"], entry["degree"], entry["dates"], entry["details"]]):
                        doc["education"].append(entry)
                elif b.get("text"):
                    school, degree, dates, details = _parse_education_blob(str(b.get("text")))
                    doc["education"].append(
                        {
                            "school": school,
                            "degree": degree,
                            "dates": dates,
                            "details": details,
                        }
                    )
            continue
        # other
        items: list[str] = []
        for b in blocks:
            if not isinstance(b, dict):
                continue
            if b.get("bullets"):
                items.extend(_bullets(b.get("bullets")))
            elif b.get("text"):
                items.append(_clean(b.get("text")))
        if items:
            doc["other_sections"].append(
                {"heading": _clean(sec.get("heading") or "Additional"), "items": items}
            )

    for o in raw.get("other_sections") or []:
        if isinstance(o, dict) and o.get("items"):
            doc["other_sections"].append(
                {
                    "heading": _clean(o.get("heading") or "Additional"),
                    "items": _bullets(o.get("items")),
                }
            )

    doc["changes"] = raw.get("changes") if isinstance(raw.get("changes"), list) else []
    doc["match_panel"] = raw.get("match_panel") if isinstance(raw.get("match_panel"), dict) else {}

    # Dedupe skill groups categories + all other section headings
    doc["skill_groups"] = _merge_skill_groups(doc["skill_groups"])
    doc["other_sections"] = merge_other_sections(doc.get("other_sections") or [])
    # Never keep a stale multi-source sections mirror that reintroduces dups on re-normalize
    doc.pop("sections", None)
    return doc


def _absorb_core_other_sections(doc: dict[str, Any]) -> dict[str, Any]:
    """Fold core-keyed other_sections into their structured field.

    A section such as "Summary" arriving as an other_section would otherwise be
    dropped by the renderer (its key is already rendered). Content is moved into
    the matching core field instead, so one logical section renders exactly once
    and nothing the user wrote is lost.
    """
    keep: list[dict[str, Any]] = []
    for sec in doc.get("other_sections") or []:
        heading = _clean(sec.get("heading"))
        key = section_heading_key(heading)
        items = [i for i in (sec.get("items") or []) if _clean(i)]
        if key not in CORE_SECTION_KEYS or not items:
            keep.append(sec)
            continue

        body = " ".join(_clean(i) for i in items)
        existing = document_plain_text(
            {k: v for k, v in doc.items() if k != "other_sections"}
        ).lower()
        if _norm_item(body) and _norm_item(body) in _norm_item(existing):
            continue  # already represented by the structured field

        if key == "summary":
            doc["summary"] = _trim_summary(
                " ".join(x for x in [_clean(doc.get("summary")), body] if x)
            )
        elif key == "skills":
            doc["skill_groups"] = _merge_skill_groups(
                [*(doc.get("skill_groups") or []), {"category": heading or "Skills", "items": items}]
            )
        elif key == "experience":
            doc["experience"] = [
                *(doc.get("experience") or []),
                {"title": heading, "org": "", "location": "", "dates": "", "bullets": items},
            ]
        elif key == "projects":
            doc["projects"] = [
                *(doc.get("projects") or []),
                {"name": heading, "technologies": [], "bullets": items},
            ]
        elif key == "education":
            doc["education"] = [
                *(doc.get("education") or []),
                {"school": heading, "degree": "", "dates": "", "details": items},
            ]
    doc["other_sections"] = keep
    return doc


def merge_other_sections(sections: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Merge duplicate other-sections by canonical key into exactly one block each.

    Content strategy: union of items; near-duplicate lines kept once (prefer longer).
    Drops pure heading echos. Core sections (summary/skills/etc.) are excluded.
    """
    order: list[str] = []
    buckets: dict[str, dict[str, Any]] = {}

    for sec in sections or []:
        if not isinstance(sec, dict):
            continue
        raw_heading = _clean(sec.get("heading") or "Additional")
        if not raw_heading:
            continue
        key = section_heading_key(raw_heading)
        # Core-keyed sections are folded into structured fields by
        # _absorb_core_other_sections; keep them here so no content is lost.
        display = _SECTION_DISPLAY.get(key) or raw_heading.title()
        items_in = _bullets(sec.get("items") or [])
        items_in = [_strip_heading_echo(it, raw_heading) for it in items_in]
        items_in = [it for it in items_in if it]

        if key not in buckets:
            order.append(key)
            buckets[key] = {"heading": display, "items": [], "_seen": set()}

        seen: set[str] = buckets[key]["_seen"]
        for it in items_in:
            nk = _norm_item(it)
            if not nk:
                continue
            # skip if it's only another heading for references etc.
            if section_heading_key(it) == key and len(it.split()) <= 3:
                continue
            if _is_heading_only_line(it):
                continue
            # drop near-duplicates keep longer phrasing
            drop = False
            for idx, existing in enumerate(list(buckets[key]["items"])):
                if _item_redundant(it, existing):
                    if len(it) > len(existing):
                        old_k = _norm_item(existing)
                        seen.discard(old_k)
                        buckets[key]["items"][idx] = it
                        seen.add(nk)
                    drop = True
                    break
            if drop:
                continue
            if nk in seen:
                continue
            seen.add(nk)
            buckets[key]["items"].append(it)

    out: list[dict[str, Any]] = []
    for key in order:
        b = buckets[key]
        items = b.get("items") or []
        if not items:
            continue
        out.append({"heading": b["heading"], "items": items})
    return out


def logical_section_keys_present(doc: dict[str, Any]) -> list[str]:
    """Ordered list of logical section keys that will render (core + other)."""
    keys: list[str] = []
    if (doc.get("summary") or "").strip():
        keys.append("summary")
    if doc.get("skill_groups"):
        keys.append("skills")
    if doc.get("experience"):
        keys.append("experience")
    if doc.get("projects"):
        keys.append("projects")
    if doc.get("education"):
        keys.append("education")
    for s in doc.get("other_sections") or []:
        k = section_heading_key(str(s.get("heading") or ""))
        if k and k not in CORE_SECTION_KEYS:
            keys.append(k)
    return keys


def find_duplicate_section_keys(doc: dict[str, Any]) -> list[str]:
    """Return logical keys that appear more than once (should always be empty after finalize)."""
    seen: set[str] = set()
    dups: list[str] = []
    for k in logical_section_keys_present(doc):
        if k in seen and k not in dups:
            dups.append(k)
        seen.add(k)
    # Also scan raw other_sections list for duplicate keys before merge awareness
    other_keys: list[str] = []
    for s in doc.get("other_sections") or []:
        other_keys.append(section_heading_key(str(s.get("heading") or "")))
    counts: dict[str, int] = {}
    for k in other_keys:
        counts[k] = counts.get(k, 0) + 1
    for k, n in counts.items():
        if n > 1 and k not in dups:
            dups.append(k)
    return dups


def finalize_document(raw: dict[str, Any] | None) -> dict[str, Any]:
    """
    Single authority: one resume → one canonical section structure.

    - normalize (ingest legacy sections once)
    - merge duplicate other-sections by logical key
    - fold core-keyed other-sections into their structured field (never drop)
    - rebuild a clean unique legacy `sections` mirror for UI only
    """
    doc = normalize_document(raw)
    doc["other_sections"] = merge_other_sections(doc.get("other_sections") or [])
    doc = _absorb_core_other_sections(doc)
    doc["other_sections"] = merge_other_sections(doc.get("other_sections") or [])
    doc["sections"] = to_legacy_sections(doc)
    return doc


def assert_section_uniqueness(doc: dict[str, Any]) -> list[str]:
    """Return hard failures if logical sections are still duplicated."""
    failures: list[str] = []
    for k in find_duplicate_section_keys(doc):
        failures.append(f"duplicate_section:{k}")
    # empty or whitespace headings
    for s in doc.get("other_sections") or []:
        h = _clean(s.get("heading"))
        if not h:
            failures.append("empty_section_heading")
    return failures


def _norm_item(s: str) -> str:
    t = _clean(s).lower()
    t = re.sub(r"^[\u2022\-\*\u2013\u2014]+\s*", "", t)
    t = re.sub(r"[^\w\s]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _strip_heading_echo(item: str, heading: str) -> str:
    """Remove leading 'References:' style echos from item text."""
    it = _clean(item)
    h = _clean(heading)
    if not it:
        return ""
    # entire item is the heading
    if _norm_item(it) == _norm_item(h):
        return ""
    if section_heading_key(it) == section_heading_key(h) and len(it.split()) <= 3:
        return ""
    # "References — available upon request"
    pattern = re.compile(
        rf"^(?:{re.escape(h)}|{re.escape(section_heading_key(h))})\s*[:\-–—|]\s*",
        re.I,
    )
    it2 = pattern.sub("", it).strip()
    return it2 if it2 else it


def _is_heading_only_line(text: str) -> bool:
    t = _clean(text)
    if not t or len(t) > 48:
        return False
    key = section_heading_key(t)
    # Known bare section labels (REFERENCES, EDUCATION, …)
    if key in _SECTION_DISPLAY and len(t.split()) <= 4:
        return True
    if key in CORE_SECTION_KEYS and len(t.split()) <= 4:
        return True
    if heading_kind(t) != "other" and len(t.split()) <= 4 and key in CORE_SECTION_KEYS:
        return True
    # ALL CAPS short *known* labels only — not credentials like "AWS SAA"
    if t.isupper() and len(t.split()) <= 4:
        if key in _SECTION_DISPLAY or key in CORE_SECTION_KEYS:
            return True
        if t.lower() in SUMMARY_HEADINGS | SKILL_HEADINGS | EXPERIENCE_HEADINGS | PROJECT_HEADINGS | EDUCATION_HEADINGS:
            return True
    return False


def _item_redundant(a: str, b: str) -> bool:
    na, nb = _norm_item(a), _norm_item(b)
    if not na or not nb:
        return False
    if na == nb:
        return True
    # nearly same "available upon request" vs "references available upon request"
    if na in nb or nb in na:
        return True
    return False


def _trim_summary(text: str) -> str:
    text = META_TEXT_RE.sub("", text)
    text = re.sub(r"\s+", " ", text).strip(" |·-")
    # Prefer ~3–5 lines ≈ 280–650 chars
    if len(text) > 700:
        # break at sentence
        parts = re.split(r"(?<=[.!?])\s+", text)
        acc = ""
        for p in parts:
            if len(acc) + len(p) + 1 > 650:
                break
            acc = (acc + " " + p).strip()
        text = acc or text[:650]
    return text


def _split_paragraph_to_bullets(text: str) -> list[str]:
    text = text.strip()
    if not text:
        return []
    # already bulleted lines
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    bullets = [
        re.sub(r"^[\u2022\-\*\u2013\u2014]+\s*", "", ln)
        for ln in lines
        if ln.startswith(("•", "-", "*", "–", "—")) or len(lines) > 1 and ln[0].isdigit()
    ]
    if bullets:
        return [b for b in bullets if b]
    # split long paragraph on sentence ends, keep 2–6
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z])", text)
    parts = [p.strip() for p in parts if len(p.strip()) > 20]
    if len(parts) >= 2:
        return parts[:6]
    return [text] if text else []


def _parse_project_blob(text: str) -> tuple[str, list[str], list[str]]:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if not lines:
        return "", [], []
    first = re.sub(r"^[\u2022\-\*]+\s*", "", lines[0])
    name = first
    techs: list[str] = []
    rest = lines[1:]
    # "Name | React, Node" or "Name — React, Node"
    m = re.match(r"^(.+?)\s*[\|–—:]\s*(.+)$", first)
    if m:
        name = m.group(1).strip()
        techs = [_clean(x) for x in re.split(r"[,·|/]", m.group(2)) if _clean(x)]
    bullets = []
    for ln in rest:
        cleaned = re.sub(r"^[\u2022\-\*\u2013\u2014]+\s*", "", ln).strip()
        if cleaned:
            bullets.append(cleaned)
    if not bullets and len(lines) == 1 and not techs:
        bullets = _split_paragraph_to_bullets(text)
        if bullets and bullets[0] == name:
            bullets = bullets[1:]
    return name[:120], techs[:12], bullets[:8]


def _parse_education_blob(text: str) -> tuple[str, str, str, list[str]]:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if not lines:
        return "", "", "", []
    first = lines[0]
    school, degree, dates = first, "", ""
    m = re.match(r"^(.+?)\s*[\|–—,]\s*(.+)$", first)
    if m:
        school = m.group(1).strip()
        rest = m.group(2).strip()
        dm = re.search(r"(\d{4}\s*[\-–—]\s*(?:\d{4}|Present|Current)|(?:19|20)\d{2})", rest, re.I)
        if dm:
            dates = dm.group(1)
            degree = rest.replace(dates, "").strip(" ·|-")
        else:
            degree = rest
    details = [
        re.sub(r"^[\u2022\-\*]+\s*", "", ln).strip()
        for ln in lines[1:]
        if ln.strip()
    ]
    return school[:160], degree[:160], dates[:80], details[:6]


def _consume_skills_blocks(doc: dict[str, Any], blocks: list[Any]) -> None:
    for b in blocks:
        if not isinstance(b, dict):
            continue
        if b.get("type") == "skill_group" or b.get("category"):
            cat = _clean(b.get("category") or "Skills")
            items = [
                _clean(x) for x in (b.get("items") or b.get("skills") or []) if _clean(x)
            ]
            if items:
                doc["skill_groups"].append({"category": cat, "items": items})
            continue
        text = _clean(b.get("text") or "")
        # "Languages: a, b | Frontend: c, d"
        if ":" in text or "：" in text:
            chunks = re.split(r"(?:\|/;|;|\n)", text)
            # better parse Category: items
            for m in re.finditer(
                r"([A-Za-z][A-Za-z0-9 &+/]{1,40})\s*:\s*([^:;|]+(?:\|[^:;]+)*)",
                text,
            ):
                cat = _clean(m.group(1))
                items = [_clean(x) for x in re.split(r"[,·|]", m.group(2)) if _clean(x)]
                if items:
                    doc["skill_groups"].append({"category": cat, "items": items})
            if not doc["skill_groups"] and text:
                items = [_clean(x) for x in re.split(r"[,·|]", text) if _clean(x)]
                if items:
                    doc["skill_groups"].append({"category": "Technical Skills", "items": items})
        elif b.get("bullets"):
            items = _bullets(b.get("bullets"))
            if items:
                doc["skill_groups"].append({"category": "Technical Skills", "items": items})
        elif text:
            items = [_clean(x) for x in re.split(r"[,·|]", text) if _clean(x)]
            if items:
                doc["skill_groups"].append({"category": "Technical Skills", "items": items})


def _merge_skill_groups(groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    order: list[str] = []
    by_cat: dict[str, list[str]] = {}
    labels: dict[str, str] = {}
    for g in groups:
        cat = _clean(g.get("category") or "Skills") or "Skills"
        key = cat.lower()
        if key not in by_cat:
            by_cat[key] = []
            order.append(key)
            labels[key] = cat
        for it in g.get("items") or []:
            v = _clean(it)
            if v and v.lower() not in {x.lower() for x in by_cat[key]}:
                by_cat[key].append(v)
    return [{"category": labels[k], "items": by_cat[k][:16]} for k in order]


def g_cat(key: str, groups: list[dict[str, Any]]) -> str:
    for g in groups:
        if _clean(g.get("category")).lower() == key:
            return _clean(g.get("category"))
    return key.title()


# g_cat kept for callers; primary merge uses labels dict above

def document_plain_text(doc: dict[str, Any]) -> str:
    """Flatten IR for factual checks / ATS text verification."""
    parts: list[str] = []
    c = doc.get("contact") or {}
    if c.get("name"):
        parts.append(str(c["name"]))
    if c.get("headline"):
        parts.append(str(c["headline"]))
    bits = [c.get("email"), c.get("phone"), c.get("location"), *(c.get("links") or [])]
    parts.append(" | ".join(str(x) for x in bits if x))
    if doc.get("summary"):
        parts.append("PROFESSIONAL SUMMARY")
        parts.append(str(doc["summary"]))
    if doc.get("skill_groups"):
        parts.append("TECHNICAL SKILLS")
        for g in doc["skill_groups"]:
            parts.append(f"{g.get('category')}: {', '.join(g.get('items') or [])}")
    if doc.get("experience"):
        parts.append("PROFESSIONAL EXPERIENCE")
        for e in doc["experience"]:
            head = " · ".join(x for x in [e.get("title"), e.get("org"), e.get("dates")] if x)
            parts.append(head)
            parts.extend(e.get("bullets") or [])
    if doc.get("projects"):
        parts.append("PROJECTS")
        for p in doc["projects"]:
            parts.append(str(p.get("name") or ""))
            if p.get("technologies"):
                parts.append(", ".join(p["technologies"]))
            parts.extend(p.get("bullets") or [])
    if doc.get("education"):
        parts.append("EDUCATION")
        for e in doc["education"]:
            parts.append(
                " · ".join(x for x in [e.get("school"), e.get("degree"), e.get("dates")] if x)
            )
            parts.extend(e.get("details") or [])
    for o in doc.get("other_sections") or []:
        parts.append(str(o.get("heading") or ""))
        parts.extend(o.get("items") or [])
    return "\n".join(parts)


def to_legacy_sections(doc: dict[str, Any]) -> list[dict[str, Any]]:
    """Optional section list for older UI consumers."""
    sections: list[dict[str, Any]] = []
    if doc.get("skill_groups"):
        sections.append(
            {
                "heading": "Technical Skills",
                "blocks": [
                    {
                        "type": "skill_group",
                        "category": g["category"],
                        "items": g["items"],
                    }
                    for g in doc["skill_groups"]
                ],
            }
        )
    if doc.get("experience"):
        sections.append(
            {
                "heading": "Professional Experience",
                "blocks": [
                    {
                        "type": "job",
                        "title": e.get("title"),
                        "org": e.get("org"),
                        "location": e.get("location"),
                        "dates": e.get("dates"),
                        "bullets": e.get("bullets") or [],
                    }
                    for e in doc["experience"]
                ],
            }
        )
    if doc.get("projects"):
        sections.append(
            {
                "heading": "Projects",
                "blocks": [
                    {
                        "type": "project",
                        "name": p.get("name"),
                        "technologies": p.get("technologies") or [],
                        "bullets": p.get("bullets") or [],
                    }
                    for p in doc["projects"]
                ],
            }
        )
    if doc.get("education"):
        sections.append(
            {
                "heading": "Education",
                "blocks": [
                    {
                        "type": "education",
                        "school": e.get("school"),
                        "degree": e.get("degree"),
                        "dates": e.get("dates"),
                        "details": e.get("details") or [],
                    }
                    for e in doc["education"]
                ],
            }
        )
    for o in doc.get("other_sections") or []:
        sections.append(
            {
                "heading": o.get("heading") or "Additional",
                "blocks": [{"type": "paragraph", "text": t} for t in (o.get("items") or [])],
            }
        )
    return sections
