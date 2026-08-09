"""Professional ATS-safe resume PDF generation from structured document IR.

Design choices (2025/2026 ATS best practice research):
- Single-column linear text stream (parsers depend on emission order)
- Standard fonts only (Helvetica via ReportLab)
- Body 10pt, name 16–17pt, section 11pt bold
- Margins ~0.65" (within 0.5–1" band)
- Standard headings: Professional Summary, Technical Skills, etc.
- No "Tailored for", branding, tables, multi-column, icons
- Contact in body (not PDF header/footer)
"""

from __future__ import annotations

import io
import re
from typing import Any

from app.resume.schema import (
    assert_section_uniqueness,
    finalize_document,
    merge_other_sections,
    section_heading_key,
)


def build_resume_pdf(
    *,
    tailored: dict[str, Any],
    job_title: str = "",  # kept for API compat — never rendered
    company: str = "",  # kept for API compat — never rendered
) -> bytes:
    _ = job_title, company  # explicitly unused — must never appear in PDF
    doc = prepare_document_for_export(tailored)
    failures = assert_section_uniqueness(doc)
    if failures:
        # One hard repair pass, then refuse silent doubles
        doc = prepare_document_for_export(doc)
        failures = assert_section_uniqueness(doc)
        if failures:
            raise ValueError(f"Resume section integrity failed: {', '.join(failures)}")
    pdf_bytes = _render(doc)
    text = extract_pdf_text(pdf_bytes)
    heading_failures = assert_pdf_heading_integrity(text)
    if heading_failures:
        # Re-finalize and repaint once — never ship a PDF with double headings
        doc = prepare_document_for_export(tailored)
        pdf_bytes = _render(doc)
        text = extract_pdf_text(pdf_bytes)
        heading_failures = assert_pdf_heading_integrity(text)
        if heading_failures:
            raise ValueError(
                f"PDF heading integrity failed: {', '.join(heading_failures)}"
            )
    return pdf_bytes


def prepare_document_for_export(tailored: dict[str, Any]) -> dict[str, Any]:
    """Final, deterministic structure before PDF paint (no duplicate sections)."""
    doc = finalize_document(tailored)
    doc.pop("sections", None)

    # Pull References (and similar) buried in free text out into other_sections once
    doc = _harvest_scattered_other_sections(doc)
    doc["other_sections"] = merge_other_sections(doc.get("other_sections") or [])
    # Strip references-like blobs still living inside bullets / details after harvest
    doc = _strip_scattered_section_content(doc)

    doc["other_sections"] = merge_other_sections(doc.get("other_sections") or [])
    doc["projects"] = _unique_named(doc.get("projects") or [], key="name")
    doc["experience"] = _unique_named(doc.get("experience") or [], key="org", alt="title")
    doc["education"] = _unique_named(doc.get("education") or [], key="school", alt="degree")
    # Canonical once more so harvest cannot leave duplicates
    doc["other_sections"] = merge_other_sections(doc.get("other_sections") or [])
    return doc


# Standalone section headers as painted by _section_header (ALL CAPS, own line)
_PDF_SECTION_HEADER_RE = re.compile(
    r"(?im)^(PROFESSIONAL SUMMARY|TECHNICAL SKILLS|PROFESSIONAL EXPERIENCE|"
    r"EXPERIENCE|PROJECTS|EDUCATION|REFERENCES|CERTIFICATIONS|LICENSES|"
    r"AWARDS|LANGUAGES|PUBLICATIONS|VOLUNTEERING|ACTIVITIES|ADDITIONAL|"
    r"INTERESTS)\s*$"
)


def assert_pdf_heading_integrity(text: str) -> list[str]:
    """Detect duplicate logical section headings in extracted PDF text."""
    counts: dict[str, int] = {}
    for m in _PDF_SECTION_HEADER_RE.finditer(text or ""):
        key = section_heading_key(m.group(1))
        counts[key] = counts.get(key, 0) + 1
    return [f"duplicate_pdf_heading:{k}" for k, n in counts.items() if n > 1]


def count_pdf_section_headings(text: str) -> dict[str, int]:
    """Count canonical section headings in PDF extract (for tests/verification)."""
    counts: dict[str, int] = {}
    for m in _PDF_SECTION_HEADER_RE.finditer(text or ""):
        key = section_heading_key(m.group(1))
        counts[key] = counts.get(key, 0) + 1
    return counts


_SCATTER_SECTION_RE = re.compile(
    r"(?im)^\s*(references?|professional references|certifications?|certificates?)\s*$"
)
_REFERENCES_SOLO_RE = re.compile(
    r"(?i)^\s*references?(?:\s*[:\-–—])?\s*available\s+upon\s+request\.?\s*$"
)


def _harvest_scattered_other_sections(doc: dict[str, Any]) -> dict[str, Any]:
    """
    When References (etc.) appear as free-text blobs inside experience/project/
    education blocks (common with weak parsers), collect once into other_sections
    and remove the embedded heading+copy so the PDF cannot print two REFERENCES.
    """
    bucket: dict[str, list[str]] = {}

    def absorb(found: dict[str, list[str]]) -> None:
        for k, items in found.items():
            bucket.setdefault(k, []).extend(x for x in items if x)

    def take_lines(text: str) -> tuple[str, dict[str, list[str]]]:
        if not text:
            return "", {}
        lines = text.splitlines() if "\n" in text else [text]
        kept, found = _consume_line_stream(lines)
        return "\n".join(kept).strip(), found

    def take_item_list(items: list[str]) -> tuple[list[str], dict[str, list[str]]]:
        kept, found = _consume_line_stream([str(x) for x in items if str(x).strip()])
        return kept, found

    def _consume_line_stream(lines: list[str]) -> tuple[list[str], dict[str, list[str]]]:
        kept: list[str] = []
        found: dict[str, list[str]] = {}
        current_key: str | None = None
        buffer: list[str] = []

        def flush() -> None:
            nonlocal current_key, buffer
            if current_key and buffer:
                found.setdefault(current_key, []).extend(
                    ln.strip() for ln in buffer if ln.strip()
                )
            elif current_key and not buffer:
                # bare "References" heading with no following lines
                if current_key == "references":
                    found.setdefault("references", []).append("Available upon request")
            current_key = None
            buffer = []

        for ln in lines:
            stripped = ln.strip()
            if not stripped:
                continue
            if _REFERENCES_SOLO_RE.match(stripped):
                flush()
                found.setdefault("references", []).append("Available upon request")
                continue
            m = _SCATTER_SECTION_RE.match(stripped)
            if m:
                flush()
                current_key = section_heading_key(m.group(1))
                continue
            if current_key:
                if re.match(
                    r"(?i)^(experience|education|projects?|skills|technical skills|"
                    r"professional summary|summary)\s*$",
                    stripped,
                ):
                    flush()
                    kept.append(stripped)
                    continue
                buffer.append(stripped)
                continue
            kept.append(stripped)
        flush()
        return kept, found

    s2, f = take_lines(str(doc.get("summary") or ""))
    doc["summary"] = s2
    absorb(f)

    for e in doc.get("experience") or []:
        bullets2, f = take_item_list(list(e.get("bullets") or []))
        absorb(f)
        e["bullets"] = bullets2

    proj_out = []
    for p in doc.get("projects") or []:
        name = str(p.get("name") or "")
        if section_heading_key(name) == "references":
            absorb({"references": list(p.get("bullets") or []) or ["Available upon request"]})
            continue
        bullets2, f = take_item_list(list(p.get("bullets") or []))
        absorb(f)
        p["bullets"] = bullets2
        if p.get("name") or p.get("bullets"):
            proj_out.append(p)
    doc["projects"] = proj_out

    for e in doc.get("education") or []:
        school = str(e.get("school") or "")
        if section_heading_key(school) == "references" or _REFERENCES_SOLO_RE.match(school):
            absorb(
                {
                    "references": list(e.get("details") or [])
                    or ["Available upon request"]
                }
            )
            e["school"] = ""
            e["details"] = []
            continue
        details2, f = take_item_list(list(e.get("details") or []))
        absorb(f)
        e["details"] = details2

    others = list(doc.get("other_sections") or [])
    for key, items in bucket.items():
        heading = {
            "references": "References",
            "certifications": "Certifications",
        }.get(key, key.title())
        others.append({"heading": heading, "items": items or ["Available upon request"]})
    doc["other_sections"] = others
    return doc


def _strip_scattered_section_content(doc: dict[str, Any]) -> dict[str, Any]:
    """Remove leftover References phrases from body fields when section exists."""
    has_refs = any(
        section_heading_key(str(s.get("heading") or "")) == "references"
        for s in (doc.get("other_sections") or [])
    )
    if not has_refs:
        return doc

    def clean_text(t: str) -> str:
        t = t or ""
        # drop dedicated full sentence
        t = re.sub(
            r"(?i)\breferences?(?:\s+are)?\s+available\s+upon\s+request\.?",
            "",
            t,
        )
        t = re.sub(r"(?im)^\s*references?\s*$", "", t)
        t = re.sub(r"\n{3,}", "\n\n", t).strip(" |\n")
        return t

    doc["summary"] = clean_text(str(doc.get("summary") or ""))
    for e in doc.get("experience") or []:
        e["bullets"] = [clean_text(b) for b in (e.get("bullets") or []) if clean_text(b)]
    for p in doc.get("projects") or []:
        p["bullets"] = [clean_text(b) for b in (p.get("bullets") or []) if clean_text(b)]
    for e in doc.get("education") or []:
        e["details"] = [clean_text(d) for d in (e.get("details") or []) if clean_text(d)]
    return doc


def _unique_named(
    items: list[dict[str, Any]], *, key: str, alt: str = ""
) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for it in items:
        raw = str(it.get(key) or (it.get(alt) if alt else "") or "").strip().lower()
        raw = re.sub(r"\s+", " ", raw)
        if not raw:
            out.append(it)
            continue
        if raw in seen:
            continue
        # substring de-dupe (e.g. Companion vs Remote Atlas Companion)
        if any(raw in s or s in raw for s in seen):
            # keep the longer name already stored
            continue
        seen.add(raw)
        out.append(it)
    return out


def _render(data: dict[str, Any]) -> bytes:
    from reportlab.lib.colors import HexColor, black
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer

    ink = HexColor("#1a1a1a")
    muted = HexColor("#333333")
    rule = HexColor("#222222")

    buf = io.BytesIO()
    margin = 0.65 * inch
    pdf = SimpleDocTemplate(
        buf,
        pagesize=letter,
        leftMargin=margin,
        rightMargin=margin,
        topMargin=0.55 * inch,
        bottomMargin=0.55 * inch,
        title=(data.get("contact") or {}).get("name") or "Resume",
        author="",
        subject="",
    )

    styles = {
        "name": ParagraphStyle(
            "RA_Name",
            fontName="Helvetica-Bold",
            fontSize=16.5,
            leading=20,
            textColor=ink,
            alignment=TA_CENTER,
            spaceAfter=2,
        ),
        "headline": ParagraphStyle(
            "RA_Headline",
            fontName="Helvetica",
            fontSize=11,
            leading=14,
            textColor=muted,
            alignment=TA_CENTER,
            spaceAfter=3,
        ),
        "contact": ParagraphStyle(
            "RA_Contact",
            fontName="Helvetica",
            fontSize=9,
            leading=12,
            textColor=muted,
            alignment=TA_CENTER,
            spaceAfter=8,
        ),
        "section": ParagraphStyle(
            "RA_Section",
            fontName="Helvetica-Bold",
            fontSize=10.5,
            leading=13,
            textColor=ink,
            spaceBefore=10,
            spaceAfter=3,
            alignment=TA_LEFT,
        ),
        "body": ParagraphStyle(
            "RA_Body",
            fontName="Helvetica",
            fontSize=10,
            leading=13,
            textColor=ink,
            spaceAfter=4,
            alignment=TA_LEFT,
        ),
        "entry_title": ParagraphStyle(
            "RA_EntryTitle",
            fontName="Helvetica-Bold",
            fontSize=10.5,
            leading=13,
            textColor=ink,
            spaceBefore=6,
            spaceAfter=1,
        ),
        "entry_meta": ParagraphStyle(
            "RA_EntryMeta",
            fontName="Helvetica-Oblique",
            fontSize=9.5,
            leading=12,
            textColor=muted,
            spaceAfter=2,
        ),
        "bullet": ParagraphStyle(
            "RA_Bullet",
            fontName="Helvetica",
            fontSize=10,
            leading=12.5,
            textColor=ink,
            leftIndent=12,
            firstLineIndent=0,
            spaceBefore=0.5,
            spaceAfter=0.5,
        ),
        "skill_line": ParagraphStyle(
            "RA_SkillLine",
            fontName="Helvetica",
            fontSize=10,
            leading=13,
            textColor=ink,
            spaceBefore=1,
            spaceAfter=1,
        ),
    }

    story: list[Any] = []
    contact = data.get("contact") or {}
    name = (contact.get("name") or "Resume").strip() or "Resume"
    story.append(Paragraph(_esc(name), styles["name"]))

    headline = (contact.get("headline") or "").strip()
    if headline:
        story.append(Paragraph(_esc(headline), styles["headline"]))

    bits: list[str] = []
    if contact.get("location"):
        bits.append(_esc(str(contact["location"])))
    if contact.get("email"):
        bits.append(_esc(str(contact["email"])))
    if contact.get("phone"):
        bits.append(_esc(str(contact["phone"])))
    for link in contact.get("links") or []:
        bits.append(_link_html(str(link)))
    if bits:
        story.append(Paragraph(" | ".join(bits), styles["contact"]))

    # PROFESSIONAL SUMMARY — exactly one
    summary = (data.get("summary") or "").strip()
    if summary:
        story.extend(_section_header("PROFESSIONAL SUMMARY", styles, rule))
        story.append(Paragraph(_esc(summary), styles["body"]))

    # TECHNICAL SKILLS — categorized lines
    groups = data.get("skill_groups") or []
    if groups:
        story.extend(_section_header("TECHNICAL SKILLS", styles, rule))
        for g in groups:
            cat = _esc(g.get("category") or "Skills")
            items = ", ".join(_esc(x) for x in (g.get("items") or []) if x)
            if items:
                story.append(
                    Paragraph(f"<b>{cat}:</b> {items}", styles["skill_line"])
                )

    # PROFESSIONAL EXPERIENCE
    experience = data.get("experience") or []
    if experience:
        story.extend(_section_header("PROFESSIONAL EXPERIENCE", styles, rule))
        for role in experience:
            org = (role.get("org") or "").strip()
            title = (role.get("title") or "").strip()
            # Prefer Company on bold line, title·location·dates italic
            if org:
                story.append(Paragraph(_esc(org), styles["entry_title"]))
                meta_parts = [title, role.get("location"), role.get("dates")]
                meta = " | ".join(_esc(str(x)) for x in meta_parts if x)
                if meta:
                    story.append(Paragraph(meta, styles["entry_meta"]))
            else:
                head = " | ".join(
                    _esc(str(x))
                    for x in [title, role.get("location"), role.get("dates")]
                    if x
                )
                if head:
                    story.append(Paragraph(head, styles["entry_title"]))
            for b in role.get("bullets") or []:
                story.append(Paragraph(f"- {_esc(str(b))}", styles["bullet"]))

    # PROJECTS — individually separated
    projects = data.get("projects") or []
    if projects:
        story.extend(_section_header("PROJECTS", styles, rule))
        for proj in projects:
            pname = (proj.get("name") or "Project").strip()
            story.append(Paragraph(_esc(pname), styles["entry_title"]))
            techs = [str(t).strip() for t in (proj.get("technologies") or []) if str(t).strip()]
            if techs:
                story.append(
                    Paragraph(_esc(" | ".join(techs)), styles["entry_meta"])
                )
            for b in proj.get("bullets") or []:
                story.append(Paragraph(f"- {_esc(str(b))}", styles["bullet"]))

    # EDUCATION
    education = data.get("education") or []
    if education:
        story.extend(_section_header("EDUCATION", styles, rule))
        for edu in education:
            school = (edu.get("school") or "").strip()
            degree = (edu.get("degree") or "").strip()
            dates = (edu.get("dates") or "").strip()
            if school:
                story.append(Paragraph(_esc(school), styles["entry_title"]))
                meta = " | ".join(_esc(x) for x in [degree, dates] if x)
                if meta:
                    story.append(Paragraph(meta, styles["entry_meta"]))
            else:
                head = " | ".join(_esc(x) for x in [degree, dates] if x)
                if head:
                    story.append(Paragraph(head, styles["entry_title"]))
            for d in edu.get("details") or []:
                story.append(Paragraph(f"- {_esc(str(d))}", styles["bullet"]))

    # Other sections — single rendered heading each (already merged)
    from app.resume.schema import heading_kind, section_heading_key

    rendered_keys: set[str] = set()
    if data.get("summary"):
        rendered_keys.add("summary")
    if data.get("skill_groups"):
        rendered_keys.add("skills")
        rendered_keys.add("technical skills")
    if data.get("experience"):
        rendered_keys.add("experience")
        rendered_keys.add("professional experience")
    if data.get("projects"):
        rendered_keys.add("projects")
    if data.get("education"):
        rendered_keys.add("education")

    # Defensive merge again at paint time
    from app.resume.schema import merge_other_sections

    others = merge_other_sections(data.get("other_sections") or [])
    seen_heading_keys: set[str] = set()
    for sec in others:
        heading_raw = str(sec.get("heading") or "ADDITIONAL").strip()
        key = section_heading_key(heading_raw)
        kind = heading_kind(heading_raw)
        if kind != "other":
            continue
        if key in rendered_keys or key in seen_heading_keys:
            continue
        items: list[str] = []
        for x in sec.get("items") or []:
            s = str(x).strip()
            if not s:
                continue
            if section_heading_key(s) == key and len(s.split()) <= 3:
                continue
            if s.upper() == heading_raw.upper():
                continue
            # strip multi-line items that re-open the same heading
            s = re.sub(rf"(?im)^\s*{re.escape(heading_raw)}\s*$", "", s).strip()
            s = re.sub(r"(?im)^\s*references?\s*$", "", s).strip()
            # Prefer clean "Available upon request" wording
            if key == "references":
                s = re.sub(
                    r"(?i)^\s*references?(?:\s*[:\-–—])?\s*",
                    "",
                    s,
                ).strip()
                if not s or s.lower() in {"available upon request", "available on request"}:
                    s = "Available upon request"
            if not s:
                continue
            items.append(s)
        if not items:
            continue
        seen_heading_keys.add(key)
        rendered_keys.add(key)
        story.extend(_section_header(heading_raw.upper(), styles, rule))
        for it in items:
            cleaned = re.sub(r"^[\u2022\-\*\u2013\u2014]+\s*", "", it).strip()
            if cleaned and cleaned.upper() != heading_raw.upper():
                story.append(Paragraph(f"- {_esc(cleaned)}", styles["bullet"]))

    if not story:
        story.append(Paragraph("Resume", styles["name"]))

    pdf.build(story)
    return buf.getvalue()


def _section_header(title: str, styles: dict, rule_color) -> list[Any]:
    from reportlab.platypus import HRFlowable, Paragraph

    return [
        Paragraph(_esc(title), styles["section"]),
        HRFlowable(
            width="100%",
            thickness=0.8,
            color=rule_color,
            spaceBefore=0,
            spaceAfter=5,
        ),
    ]


def _esc(s: str) -> str:
    return (
        (s or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _link_html(url: str) -> str:
    raw = (url or "").strip()
    if not raw:
        return ""
    href = raw if re.match(r"^https?://", raw, re.I) else raw
    display = re.sub(r"^https?://(www\.)?", "", raw, flags=re.I).rstrip("/")
    if re.match(r"^https?://", href, re.I) or "linkedin.com" in raw or "github.com" in raw:
        href_full = href if href.startswith("http") else f"https://{href}"
        return f'<link href="{_esc(href_full)}">{_esc(display)}</link>'
    return _esc(display)


def pdf_page_count(pdf_bytes: bytes) -> int:
    try:
        from pypdf import PdfReader

        return len(PdfReader(io.BytesIO(pdf_bytes)).pages)
    except Exception:  # noqa: BLE001
        return 0


def extract_pdf_text(pdf_bytes: bytes) -> str:
    try:
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(pdf_bytes))
        return "\n".join((p.extract_text() or "") for p in reader.pages)
    except Exception:  # noqa: BLE001
        return ""
