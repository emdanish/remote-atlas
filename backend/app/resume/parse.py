"""Deterministic resume parser: original resume text → canonical structured IR.

This is the source of truth for tailoring. It never calls an AI provider, so a
provider outage can degrade wording but can never destroy the user's content.

Handles the layouts real resumes produce after PDF/DOCX extraction:
- ALL CAPS or Title Case section headings
- wrapped bullet text without bullet glyphs (common in PDF extraction)
- "Category: item, item" skill lines
- "Title  MM/YYYY - Present" + org line experience blocks
- "Project Name | Tech, Tech" project blocks
- custom/unknown sections, which are always preserved
"""

from __future__ import annotations

import re
from typing import Any

from app.resume.schema import empty_document, heading_kind, section_heading_key

_BULLET_RE = re.compile(r"^[\u2022\u25cf\u25aa\-\*\u2013\u2014]+\s*")
_DATE_RANGE_RE = re.compile(
    r"(?i)("
    r"(?:\d{1,2}[/.-]\d{4}|\d{4}|"
    r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+\d{4})"
    r"\s*(?:[-–—]|to)\s*"
    r"(?:present|current|now|\d{1,2}[/.-]\d{4}|\d{4}|"
    r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+\d{4})"
    r")"
)
_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
_PHONE_RE = re.compile(r"(?:\+?\d[\d\s().-]{7,}\d)")
_LINK_RE = re.compile(
    r"(?i)\b((?:https?://)?(?:www\.)?"
    r"(?:linkedin\.com|github\.com|gitlab\.com|behance\.net|dribbble\.com|medium\.com)"
    r"/[\w\-./%]+|[\w-]+\.(?:dev|io|me|com|app|net|org)(?:/[\w\-./%]*)?)"
)

# Headings we recognise verbatim; anything else ALL CAPS is treated as a custom section
_KNOWN_HEADING_WORDS = {
    "summary",
    "professional summary",
    "career summary",
    "profile",
    "objective",
    "about",
    "about me",
    "skills",
    "technical skills",
    "core competencies",
    "technologies",
    "tech stack",
    "tools",
    "experience",
    "professional experience",
    "work experience",
    "employment",
    "employment history",
    "work history",
    "projects",
    "selected projects",
    "personal projects",
    "key projects",
    "portfolio",
    "education",
    "academic background",
    "academics",
    "references",
    "certifications",
    "certificates",
    "licenses",
    "awards",
    "honors",
    "achievements",
    "publications",
    "languages",
    "interests",
    "hobbies",
    "volunteer experience",
    "volunteering",
    "activities",
    "additional information",
    "open source",
    "research",
    "leadership",
}


def parse_resume_text(text: str) -> dict[str, Any]:
    """Parse extracted resume text into the canonical document IR."""
    from app.resume.extract import restore_resume_structure

    # Heal PDFs that lost newlines (and any legacy rows already stored that way)
    text = restore_resume_structure(text or "")
    doc = empty_document()
    lines = [ln.rstrip() for ln in text.splitlines()]
    lines = [ln for ln in lines if ln.strip()]
    if not lines:
        return doc

    header_lines, blocks = _split_sections(lines)
    doc["contact"] = _parse_contact(header_lines)

    for heading, body in blocks:
        kind = heading_kind(heading)
        if kind == "summary":
            summary = " ".join(body).strip()
            if summary and not doc["summary"]:
                doc["summary"] = summary
        elif kind == "skills":
            doc["skill_groups"].extend(_parse_skills(body))
        elif kind == "experience":
            doc["experience"].extend(_parse_experience(body))
        elif kind == "projects":
            doc["projects"].extend(_parse_projects(body))
        elif kind == "education":
            doc["education"].extend(_parse_education(body))
        else:
            items = _lines_to_items(body)
            if items:
                doc["other_sections"].append({"heading": heading, "items": items})

    # A resume with no recognisable headings still must not be lost
    if not any(
        [
            doc["summary"],
            doc["skill_groups"],
            doc["experience"],
            doc["projects"],
            doc["education"],
            doc["other_sections"],
        ]
    ):
        body = [ln for ln in lines[1:] if ln.strip()]
        items = _lines_to_items(body)
        if items:
            doc["other_sections"].append({"heading": "Additional Information", "items": items})

    return doc


def _is_heading(line: str, *, allow_unknown: bool) -> bool:
    s = line.strip()
    if not s or len(s) > 64:
        return False
    if s.endswith((".", ",", ";", ":")) and section_heading_key(s.rstrip(":")) not in {
        "references",
        "skills",
        "summary",
        "experience",
        "projects",
        "education",
    }:
        return False
    core = s.rstrip(":").strip()
    low = re.sub(r"\s+", " ", core.lower())
    if low in _KNOWN_HEADING_WORDS:
        return True
    if _DATE_RANGE_RE.search(core) or _EMAIL_RE.search(core):
        return False
    if allow_unknown:
        letters = [c for c in core if c.isalpha()]
        if letters and all(c.isupper() for c in letters) and len(core.split()) <= 6:
            return True
    return False


def _split_sections(lines: list[str]) -> tuple[list[str], list[tuple[str, list[str]]]]:
    """Return (header lines before the first heading, [(heading, body lines)])."""
    first_known = None
    for idx, ln in enumerate(lines):
        if idx == 0:
            continue  # line 0 is the candidate name, never a heading
        if _is_heading(ln, allow_unknown=False):
            first_known = idx
            break

    if first_known is None:
        return lines[: min(len(lines), 5)], []

    header = lines[:first_known]
    blocks: list[tuple[str, list[str]]] = []
    heading = lines[first_known].rstrip(":").strip()
    body: list[str] = []
    for ln in lines[first_known + 1 :]:
        if _is_heading(ln, allow_unknown=True):
            blocks.append((heading, body))
            heading = ln.rstrip(":").strip()
            body = []
            continue
        body.append(ln)
    blocks.append((heading, body))
    return header, blocks


def _parse_contact(header: list[str]) -> dict[str, Any]:
    contact = {
        "name": "",
        "headline": "",
        "email": "",
        "phone": "",
        "location": "",
        "links": [],
    }
    if not header:
        return contact

    # Flattened PDF extracts often collapse the whole header to one line.
    header = _expand_header_lines(header)
    blob = "\n".join(header)

    email_m = _EMAIL_RE.search(blob)
    if email_m:
        contact["email"] = email_m.group(0)

    without_email = _EMAIL_RE.sub(" ", blob)
    phone_m = _PHONE_RE.search(without_email)
    if phone_m:
        candidate = phone_m.group(0).strip()
        if sum(ch.isdigit() for ch in candidate) >= 8:
            contact["phone"] = candidate

    links: list[str] = []
    for m in _LINK_RE.finditer(without_email):
        link = m.group(1).strip().rstrip("/.,")
        if "@" in link:
            continue
        if "/" not in link and not re.search(r"\.(dev|io|me|com|app|net|org)\b", link, re.I):
            continue
        if link.lower() not in {x.lower() for x in links}:
            links.append(link)
    contact["links"] = links[:8]

    contact["name"] = _titleize_name(_extract_name_head(header[0].strip()))
    remainder_first = header[0].strip()
    # Peel known name forms off the first line (flattened headers)
    for variant in {
        contact["name"],
        contact["name"].upper(),
        _extract_name_head(header[0]),
    }:
        if variant and remainder_first.lower().startswith(variant.lower()):
            remainder_first = remainder_first[len(variant) :].strip(" |,-–—")
            break

    # Prefer classic multi-line header layout when present
    detail_lines = []
    if remainder_first and remainder_first.lower() != contact["name"].lower():
        detail_lines.append(remainder_first)
    detail_lines.extend([ln.strip() for ln in header[1:] if ln.strip()])
    if detail_lines:
        headline_line = ""
        for s in detail_lines:
            scrubbed = _EMAIL_RE.sub(" ", s)
            if contact["phone"]:
                scrubbed = scrubbed.replace(contact["phone"], " ")
            for link in links:
                scrubbed = re.sub(re.escape(link), " ", scrubbed, flags=re.I)
            scrubbed = re.sub(r"\s+", " ", scrubbed).strip(" |")
            if not scrubbed:
                continue
            if _EMAIL_RE.search(s) or _PHONE_RE.search(s) or _LINK_RE.search(s):
                # contact-y line — may still hold location before phone
                parts = [p.strip() for p in s.split("|") if p.strip()]
                for part in parts:
                    if _EMAIL_RE.search(part) or _LINK_RE.search(part):
                        continue
                    if sum(c.isdigit() for c in part) >= 5:
                        continue
                    if 2 <= len(part) <= 48 and len(part.split()) <= 5 and not contact["location"]:
                        contact["location"] = part
                continue
            if not contact["headline"]:
                contact["headline"] = scrubbed[:160]
                headline_line = s
        if not contact["location"]:
            for s in detail_lines:
                if s == headline_line:
                    continue
                for part in [p.strip() for p in s.split("|") if p.strip()]:
                    if _EMAIL_RE.search(part) or _LINK_RE.search(part):
                        continue
                    if sum(c.isdigit() for c in part) >= 5:
                        continue
                    if 2 <= len(part) <= 48 and len(part.split()) <= 5:
                        contact["location"] = part
                        break
                if contact["location"]:
                    break
        contact = _normalize_contact_location(contact)
        return contact

    # Single-line collapsed header fallback
    cleaned = without_email
    if contact["phone"]:
        cleaned = cleaned.replace(contact["phone"], " ")
    for link in links:
        cleaned = re.sub(re.escape(link), " ", cleaned, flags=re.I)
    # name already extracted; strip it
    if contact["name"]:
        cleaned = re.sub(re.escape(contact["name"]), " ", cleaned, flags=re.I)
        cleaned = re.sub(
            re.escape(contact["name"].upper()), " ", cleaned, flags=re.I
        )
    parts = [p.strip() for p in re.split(r"[\n|]+", cleaned) if p.strip() and re.search(r"[A-Za-z]", p)]
    # Drop residual name head fragments
    filtered: list[str] = []
    for p in parts:
        if _titleize_name(_extract_name_head(p)).lower() == contact["name"].lower() and len(p.split()) <= 4:
            continue
        filtered.append(p)

    location_i = None
    for i, p in enumerate(filtered):
        low = p.lower()
        if any(
            w in low
            for w in (
                "pakistan",
                "india",
                "united states",
                "usa",
                "uk",
                "remote",
                "lahore",
                "karachi",
                "islamabad",
            )
        ) or ("," in p and len(p.split()) <= 5 and len(p) <= 48):
            contact["location"] = p
            location_i = i
            break
    headline_parts = [p for i, p in enumerate(filtered) if i != location_i]
    if headline_parts:
        contact["headline"] = " | ".join(headline_parts)[:160]
    return _normalize_contact_location(contact)


_LOCATION_HINTS = (
    "pakistan",
    "india",
    "united states",
    "usa",
    "uk",
    "united kingdom",
    "canada",
    "remote",
    "lahore",
    "karachi",
    "islamabad",
    "london",
    "new york",
    "san francisco",
    "berlin",
    "toronto",
)


def _is_pure_location(text: str) -> bool:
    t = (text or "").strip()
    if not t or len(t) > 48 or len(t.split()) > 5:
        return False
    low = t.lower()
    if any(h == low or h in low.split(",")[0].strip() for h in _LOCATION_HINTS):
        return True
    if any(low == h or low.endswith(h) for h in _LOCATION_HINTS):
        return True
    # "City, Country"
    if "," in t and len(t.split()) <= 5 and not re.search(r"(?i)api|llm|react|python|engineer", t):
        return True
    return False


def _normalize_contact_location(contact: dict[str, Any]) -> dict[str, Any]:
    """Peel a trailing location token out of the headline when headers are flattened."""
    if contact.get("location") or not contact.get("headline"):
        return contact
    headline = contact["headline"]
    parts = [p.strip() for p in headline.split("|") if p.strip()]
    if len(parts) >= 2 and _is_pure_location(parts[-1]):
        contact["location"] = parts[-1]
        contact["headline"] = " | ".join(parts[:-1])[:160]
        return contact
    m = re.search(
        r"(?i)(?:^|[\s|,])("
        + "|".join(re.escape(h) for h in _LOCATION_HINTS)
        + r")\s*$",
        headline,
    )
    if m and m.start() > 8:
        contact["location"] = m.group(1).strip()
        contact["headline"] = headline[: m.start()].strip(" |,-–—")[:160]
    return contact


def _expand_header_lines(header: list[str]) -> list[str]:
    """Split a collapsed header blob on contact chromes when newlines were lost."""
    out: list[str] = []
    for ln in header:
        s = ln.strip()
        if not s:
            continue
        if "\n" in s or len(s) < 120:
            out.append(s)
            continue
        # Long single line: cut email / phone onto their own lines so detail logic works
        s = _EMAIL_RE.sub(lambda m: f"\n{m.group(0)}\n", s)
        s = _PHONE_RE.sub(lambda m: f"\n{m.group(0)}\n", s)
        # Location-like country before phone tends to sit after a pipe
        parts = [p.strip() for p in s.splitlines() if p.strip()]
        out.extend(parts if parts else [ln.strip()])
    return out or header


def _extract_name_head(raw: str) -> str:
    """Keep 'MUHAMMAD DANISH' from 'MUHAMMAD DANISH Full-Stack Developer…'."""
    s = re.sub(r"\s+", " ", (raw or "").strip())
    if not s:
        return s
    words = s.split()
    name_words: list[str] = []
    stop = {
        "full-stack",
        "fullstack",
        "software",
        "developer",
        "engineer",
        "senior",
        "junior",
        "lead",
        "student",
        "intern",
        "ai-powered",
        "applications",
        "claude",
        "llm",
    }
    for w in words:
        low = w.lower().strip(",.|")
        if low in stop or (name_words and ("|" in w or "@" in w or any(ch.isdigit() for ch in w))):
            break
        if not re.search(r"[A-Za-z]", w):
            break
        name_words.append(w)
        if len(name_words) >= 4:
            break
    return " ".join(name_words) if name_words else s.split("|")[0].strip()


def _titleize_name(raw: str) -> str:
    name = re.sub(r"\s+", " ", raw).strip()
    # Guard: never return an entire paragraph as a "name"
    if len(name) > 80 or name.count(" ") > 6:
        name = _extract_name_head(name)
    letters = [c for c in name if c.isalpha()]
    if letters and all(c.isupper() for c in letters):
        return " ".join(w.capitalize() for w in name.split())
    return name


def _join_wrapped(parts: list[str]) -> str:
    """Join wrapped lines, healing words broken across a line break ("multi-\\nstep")."""
    text = ""
    for part in parts:
        chunk = part.strip()
        if not chunk:
            continue
        if not text:
            text = chunk
            continue
        if text.endswith("-") and chunk[:1].islower():
            text += chunk
        else:
            text = f"{text} {chunk}"
    return re.sub(r"\s+", " ", text).strip()


def _lines_to_items(lines: list[str]) -> list[str]:
    """Group wrapped lines into logical items/bullets."""
    out: list[str] = []
    buf: list[str] = []

    def flush() -> None:
        nonlocal buf
        if buf:
            text = _join_wrapped(buf)
            if text:
                out.append(text)
        buf = []

    for raw in lines:
        s = raw.strip()
        if not s:
            continue
        if _BULLET_RE.match(s):
            flush()
            buf = [_BULLET_RE.sub("", s).strip()]
            if s.endswith((".", "!", "?")):
                flush()
            continue
        buf.append(s)
        if s.endswith((".", "!", "?")):
            flush()
    flush()
    return out


def _parse_skills(lines: list[str]) -> list[dict[str, Any]]:
    groups: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    loose: list[str] = []
    line_ended_mid_item = False

    for raw in lines:
        s = raw.strip()
        if not s:
            continue
        s = _BULLET_RE.sub("", s).strip()
        m = re.match(r"^([A-Za-z][\w &/+.'-]{1,48}?)\s*[:\u2013\u2014]\s*(.+)$", s)
        if m and len(m.group(1).split()) <= 5:
            current = {
                "category": m.group(1).strip(),
                "items": _split_skill_items(m.group(2)),
            }
            groups.append(current)
            line_ended_mid_item = not s.rstrip().endswith(",")
            continue
        parts = _split_skill_items(s)
        target = current["items"] if current is not None else loose
        # A wrapped line continues the previous item unless that line ended on a comma
        if line_ended_mid_item and target and parts:
            target[-1] = _join_wrapped([target[-1], parts.pop(0)])
        target.extend(parts)
        line_ended_mid_item = not s.rstrip().endswith(",")

    if loose:
        groups.insert(0, {"category": "Skills", "items": loose})

    out: list[dict[str, Any]] = []
    for g in groups:
        items: list[str] = []
        seen: set[str] = set()
        for it in _heal_parens(g["items"]):
            key = it.lower()
            if it and key not in seen:
                seen.add(key)
                items.append(it)
        if items:
            out.append({"category": g["category"], "items": items})
    return out


def _heal_parens(items: list[str]) -> list[str]:
    """Rejoin an item whose parenthesis was split across a line break."""
    out: list[str] = []
    for item in items:
        if out and out[-1].count("(") > out[-1].count(")"):
            joiner = " " if out[-1].endswith(",") else ", "
            out[-1] = f"{out[-1]}{joiner}{item}"
            continue
        out.append(item)
    return [i.strip(" ,") for i in out if i.strip(" ,")]


def _split_skill_items(text: str) -> list[str]:
    # Keep parenthetical groups intact: "JavaScript (ES6+), Python"
    parts: list[str] = []
    depth = 0
    buf = ""
    for ch in text:
        if ch in "([":
            depth += 1
        elif ch in ")]":
            depth = max(0, depth - 1)
        if ch in ",;" and depth == 0:
            parts.append(buf)
            buf = ""
            continue
        buf += ch
    parts.append(buf)
    return [re.sub(r"\s+", " ", p).strip(" .") for p in parts if p.strip(" .")]


def _parse_experience(lines: list[str]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    body: list[str] = []

    def close() -> None:
        nonlocal current, body
        if current is not None:
            current["bullets"] = _lines_to_items(body)
            entries.append(current)
        current = None
        body = []

    for raw in lines:
        s = raw.strip()
        if not s:
            continue
        started = _experience_header(s)
        if started is not None:
            close()
            current = {
                "title": started["title"],
                "org": started["org"],
                "location": "",
                "dates": started["dates"],
                "bullets": [],
            }
            if started.get("seed"):
                body = [started["seed"]]
            continue
        if current is not None and not current["org"] and not body and _looks_like_org(s):
            current["org"] = s.strip(" |,-–—")
            continue
        if current is None:
            # entry without a date line: first short line becomes the title
            if _looks_like_org(s):
                current = {
                    "title": s.strip(" |,-–—"),
                    "org": "",
                    "location": "",
                    "dates": "",
                    "bullets": [],
                }
                continue
            current = {"title": "", "org": "", "location": "", "dates": "", "bullets": []}
        body.append(s)
    close()
    return [e for e in entries if e["title"] or e["org"] or e["bullets"]]


# Body often begins with an action verb after the employer name on flattened lines.
_BODY_MARKER_RE = re.compile(
    r"(?i)\b("
    r"Built|Developed|Implemented|Created|Led|Managed|Owned|Designed|"
    r"Worked|Delivered|Engineered|Architected|Spearheaded|Launched|"
    r"Responsible|Contributed|Supported|Improved|Enhanced|Maintained|"
    r"Helped|Reduced|Increased|Optimized|Integrated|Migrated|"
    r"Core\s+engineer"
    r")\b"
)


def _split_org_and_body(remainder: str) -> tuple[str, str]:
    rem = (remainder or "").strip()
    if not rem:
        return "", ""
    m = _BODY_MARKER_RE.search(rem)
    if m and 0 < m.start() <= 70:
        org = rem[: m.start()].strip(" |,-–—")
        body = rem[m.start() :].strip()
        if org and 1 <= len(org.split()) <= 6 and not org.endswith("."):
            return org, body
    if m and m.start() == 0:
        return "", rem
    if len(rem) <= 80 and _looks_like_org(rem) and not rem.endswith("."):
        return rem, ""
    return "", rem


def _experience_header(s: str) -> dict[str, str] | None:
    """
    Detect a job header line.

    Supports both clean layouts ('Title  MM/YYYY - Present' + org on next line)
    and flattened streams ('Title dates Org Body…') after PDF newline loss.
    """
    m = _DATE_RANGE_RE.search(s)
    if not m:
        return None
    prefix = s[: m.start()].strip(" |,-–—·\t")
    remainder = s[m.end() :].strip(" |,-–—·\t")
    dates = re.sub(r"\s+", " ", m.group(1)).strip()

    if not prefix and remainder:
        if len(remainder) <= 90 and not remainder.endswith("."):
            return {"title": remainder, "org": "", "dates": dates, "seed": ""}
        return None
    if not prefix or len(prefix) > 90 or len(prefix.split()) > 12:
        return None
    if m.start() > 90:
        return None

    org = ""
    seed = ""
    if remainder:
        if len(s) <= 120 and not remainder.endswith(".") and _looks_like_org(remainder):
            org = remainder
        else:
            org, seed = _split_org_and_body(remainder)

    return {
        "title": re.sub(r"\s+", " ", prefix).strip(),
        "org": org,
        "dates": dates,
        "seed": seed,
    }


def _looks_like_org(s: str) -> bool:
    t = s.strip()
    if not t or len(t) > 80:
        return False
    if t.endswith((".", "!", "?", ",", ";")):
        return False
    return len(t.split()) <= 8


def _parse_projects(lines: list[str]) -> list[dict[str, Any]]:
    # Flattened streams may leave several "Name | Tech…" runs on one line
    expanded: list[str] = []
    for raw in lines:
        expanded.extend(_split_project_stream_line(raw))
    lines = expanded

    entries: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    body: list[str] = []
    expect_tech_continuation = False

    def close() -> None:
        nonlocal current, body
        if current is not None:
            current["bullets"] = _lines_to_items(body)
            entries.append(current)
        current = None
        body = []

    for raw in lines:
        s = raw.strip()
        if not s:
            continue

        if expect_tech_continuation and current is not None and not body:
            current["technologies"].extend(_split_skill_items(s))
            expect_tech_continuation = s.endswith(",")
            continue

        head = _project_header(s)
        if head is not None:
            close()
            name, techs, trailing_comma, seed = head
            current = {"name": name, "technologies": techs, "bullets": []}
            expect_tech_continuation = trailing_comma
            body = [seed] if seed else []
            continue

        if current is None:
            if _looks_like_org(s):
                current = {"name": s, "technologies": [], "bullets": []}
                continue
            current = {"name": "", "technologies": [], "bullets": []}
        body.append(s)
    close()

    out = []
    for e in entries:
        if not e["name"] and e["bullets"]:
            e["name"] = e["bullets"][0][:80]
            e["bullets"] = e["bullets"][1:]
        e["technologies"] = _heal_parens(e["technologies"])
        if e["name"] or e["bullets"]:
            out.append(e)
    return out


def _split_project_stream_line(s: str) -> list[str]:
    """Split 'ProjA | tech. Desc. ProjB | tech Desc' into one line per project when possible."""
    s = (s or "").strip()
    if not s or s.count("|") < 2:
        return [s] if s else []
    # Break before "Name |" that follows sentence end, when Name looks like a project title
    parts = re.split(
        r"(?<=[.!?])\s+(?=[A-Z][A-Za-z0-9 .'/&+-]{1,50}?\s*\|)",
        s,
    )
    return [p.strip() for p in parts if p.strip()]


def _project_header(s: str) -> tuple[str, list[str], bool, str] | None:
    """Detect 'Name | Tech, Tech' or a short standalone project title line."""
    if "|" in s:
        name, _, rest = s.partition("|")
        name = name.strip()
        if name and len(name) <= 80 and not name.endswith("."):
            techs, prose = _split_tech_and_prose(rest)
            trailing = bool(s.rstrip().endswith(",") and not prose)
            return name, techs, trailing, prose
    if len(s) <= 60 and not s.endswith((".", ",", ";")) and len(s.split()) <= 7:
        letters = [c for c in s if c.isalpha()]
        if letters and (s[0].isupper() or all(c.isupper() for c in letters)):
            return s, [], False, ""
    return None


def _split_tech_and_prose(rest: str) -> tuple[list[str], str]:
    """Split tech list text from trailing project description prose when both share a line."""
    rest = (rest or "").strip()
    if not rest:
        return [], ""
    m = re.search(
        r"(?i)(?<=[A-Za-z0-9)\]])\s+(?="
        r"(?:Founder|Lead engineer|Built|Developed|Created|Implemented|Designed|"
        r"Research[- ]grounded|AI journaling|An?\b|The\b|This\b)\b"
        r")",
        rest,
    )
    if m:
        tech_part = rest[: m.start()].strip(" ,;")
        prose = rest[m.start() :].strip()
        return _split_skill_items(tech_part), prose
    return _split_skill_items(rest), ""


def _parse_education(lines: list[str]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    discrete: list[str] = []  # already-separated values (pipe fields)
    free: list[str] = []  # wrapped prose to be regrouped

    def close() -> None:
        nonlocal current, discrete, free
        if current is not None:
            current["details"] = [*discrete, *_lines_to_items(free)]
            entries.append(current)
        current = None
        discrete = []
        free = []

    for raw in lines:
        s = raw.strip()
        if not s:
            continue
        m = _DATE_RANGE_RE.search(s)
        if m and m.start() <= 100:
            close()
            degree = s[: m.start()].strip(" |,-–—")
            remainder = s[m.end() :].strip(" |,-–—")
            current = {
                "school": "",
                "degree": re.sub(r"\s+", " ", degree).strip(),
                "dates": re.sub(r"\s+", " ", m.group(1)).strip(),
                "details": [],
            }
            if remainder:
                if "|" in remainder:
                    parts = [p.strip() for p in remainder.split("|") if p.strip()]
                    current["school"] = parts[0]
                    for part in parts[1:]:
                        # If a pipe cell trails into prose, keep as detail chunks
                        discrete.append(part)
                elif _looks_like_org(remainder) or len(remainder) < 100:
                    current["school"] = remainder
                else:
                    # "University Name, Campus Campus Relevant Coursework: …"
                    school_m = re.match(
                        r"^(.+?(?:University|College|Institute|School|Academy)[^|]*)",
                        remainder,
                        flags=re.I,
                    )
                    if school_m:
                        current["school"] = school_m.group(1).strip(" ,|")
                        tail = remainder[school_m.end() :].strip(" ,|")
                        if tail:
                            free.append(tail)
                    else:
                        free.append(remainder)
            continue
        if current is None:
            current = {"school": "", "degree": "", "dates": "", "details": []}
        if not current["school"] and "|" in s:
            parts = [p.strip() for p in s.split("|") if p.strip()]
            current["school"] = parts[0]
            discrete.extend(parts[1:])
            continue
        if not current["school"] and _looks_like_org(s) and not free:
            current["school"] = s
            continue
        free.append(s)
    close()
    return [e for e in entries if e["school"] or e["degree"] or e["details"]]
