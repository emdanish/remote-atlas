"""Deterministic resume quality checks and auto-fixes before PDF export."""

from __future__ import annotations

import re
from typing import Any

from app.resume.schema import (
    META_TEXT_RE,
    assert_section_uniqueness,
    document_plain_text,
    finalize_document,
    merge_other_sections,
    section_heading_key,
)


def run_quality_gate(
    *,
    document: dict[str, Any],
    original_text: str = "",
) -> dict[str, Any]:
    """
    Validate and clean the structured resume.

    Returns: {ok, issues, document, fixed}
    """
    _ = original_text  # reserved for future fidelity scoring
    doc = finalize_document(document)
    issues: list[dict[str, Any]] = []
    fixed: list[str] = []

    # Strip layout meta phrases only — not substrings that may appear as real
    # project/company wording (e.g. a project named "Remote Atlas Companion").
    META_BANS = (
        r"\bTailored\s+for\b[^.|\n]{0,80}",
        r"\bGenerated\s+for\b[^.|\n]{0,80}",
        r"\bAI[- ]generated\b",
        r"\bGenerated\s+by\s+AI\b",
        r"\bJob\s+Match\s+Score\b[^.|\n]{0,40}",
        r"\bATS\s+Score\b[^.|\n]{0,40}",
        r"\bPowered\s+by\s+Remote\s+Atlas\b",
        r"\bCreated\s+with\s+Remote\s+Atlas\b",
    )

    def scrub(s: str) -> str:
        if not s:
            return s
        if META_TEXT_RE.search(s):
            fixed.append("removed_meta_text")
            s = META_TEXT_RE.sub("", s)
            s = re.sub(r"\s+", " ", s).strip(" |·:-")
        for ban in META_BANS:
            if re.search(ban, s, flags=re.I):
                fixed.append("stripped:meta_phrase")
                s = re.sub(ban, "", s, flags=re.I)
                s = re.sub(r"\s+", " ", s).strip(" |·:-")
        return s

    c = doc["contact"]
    for k in ("name", "headline", "email", "phone", "location"):
        c[k] = scrub(str(c.get(k) or ""))
    c["links"] = [scrub(x) for x in (c.get("links") or []) if scrub(x)]
    doc["summary"] = scrub(str(doc.get("summary") or ""))

    # Exactly one summary — already single field; ensure no summary-like other section
    other = []
    for sec in doc.get("other_sections") or []:
        key = section_heading_key(str(sec.get("heading") or ""))
        h = str(sec.get("heading") or "").lower()
        if key == "summary" or "summary" in h or h in {"profile", "objective", "about"}:
            body = " ".join(sec.get("items") or [])
            if body and not doc["summary"]:
                doc["summary"] = scrub(body)[:700]
                fixed.append("moved_other_summary")
            else:
                fixed.append("dropped_duplicate_summary_section")
            issues.append(
                {
                    "severity": "medium",
                    "kind": "duplicate_summary",
                    "value": sec.get("heading"),
                    "action": "deduped",
                }
            )
            continue
        other.append(sec)

    before_n = len(other)
    doc["other_sections"] = merge_other_sections(other)
    # scrub items
    scrubbed_other = []
    for sec in doc["other_sections"]:
        heading = scrub(str(sec.get("heading") or "Additional"))
        items = []
        seen_i: set[str] = set()
        for it in sec.get("items") or []:
            v = scrub(str(it))
            if not v:
                continue
            k = re.sub(r"\s+", " ", v.lower()).strip()
            if k in seen_i:
                continue
            # drop pure heading echos
            if k == heading.lower() or section_heading_key(k) == section_heading_key(heading):
                if len(k.split()) <= 3:
                    fixed.append("dropped_heading_echo_item")
                    continue
            seen_i.add(k)
            items.append(v)
        if items:
            scrubbed_other.append({"heading": heading, "items": items})
    if before_n > len(scrubbed_other):
        fixed.append("merged_duplicate_other_sections")
        issues.append(
            {
                "severity": "medium",
                "kind": "duplicate_section",
                "action": "merged",
                "value": "other_sections",
            }
        )
    doc["other_sections"] = merge_other_sections(scrubbed_other)

    # Summary length
    if doc["summary"]:
        # Prefer 2–5 sentences if giant
        if len(doc["summary"]) > 750:
            doc["summary"] = doc["summary"][:700].rsplit(" ", 1)[0] + "."
            fixed.append("trimmed_summary")
            issues.append(
                {
                    "severity": "low",
                    "kind": "long_summary",
                    "action": "trimmed",
                }
            )

    # Clean skill groups empty
    skill_groups = []
    for g in doc.get("skill_groups") or []:
        items = [scrub(i) for i in (g.get("items") or []) if scrub(i)]
        # dedupe case-insensitive
        seen = set()
        uniq = []
        for it in items:
            k = it.lower()
            if k in seen:
                continue
            seen.add(k)
            uniq.append(it)
        if uniq:
            skill_groups.append({"category": scrub(g.get("category") or "Skills"), "items": uniq})
    doc["skill_groups"] = skill_groups

    # Experience: drop empty, convert paragraphs, scrub
    exp_out = []
    for e in doc.get("experience") or []:
        bullets = []
        for b in e.get("bullets") or []:
            b = scrub(str(b))
            if not b:
                continue
            if len(b) > 420:
                b = b[:400].rsplit(" ", 1)[0] + "."
                fixed.append("trimmed_long_bullet")
            bullets.append(b)
        entry = {
            "title": scrub(e.get("title") or ""),
            "org": scrub(e.get("org") or ""),
            "location": scrub(e.get("location") or ""),
            "dates": scrub(e.get("dates") or ""),
            "bullets": bullets,
        }
        if entry["title"] or entry["org"] or entry["bullets"]:
            exp_out.append(entry)
    doc["experience"] = exp_out

    # Projects: require separation
    proj_out = []
    for p in doc.get("projects") or []:
        name = scrub(p.get("name") or "")
        techs = [scrub(t) for t in (p.get("technologies") or []) if scrub(t)]
        bullets = []
        for b in p.get("bullets") or []:
            b = scrub(str(b))
            if b:
                if len(b) > 420:
                    b = b[:400].rsplit(" ", 1)[0] + "."
                bullets.append(b)
        if name or bullets:
            proj_out.append({"name": name or "Project", "technologies": techs, "bullets": bullets})
    doc["projects"] = proj_out

    # Education
    edu_out = []
    for e in doc.get("education") or []:
        entry = {
            "school": scrub(e.get("school") or ""),
            "degree": scrub(e.get("degree") or ""),
            "dates": scrub(e.get("dates") or ""),
            "details": [scrub(d) for d in (e.get("details") or []) if scrub(d)],
        }
        if entry["school"] or entry["degree"] or entry["details"]:
            edu_out.append(entry)
    doc["education"] = edu_out

    # Final uniqueness pass (invariant)
    doc = finalize_document(doc)
    for fail in assert_section_uniqueness(doc):
        issues.append(
            {
                "severity": "high",
                "kind": "section_uniqueness",
                "value": fail,
                "action": "repaired",
            }
        )
        fixed.append(fail)

    # Full text meta scan
    plain = document_plain_text(doc)
    if META_TEXT_RE.search(plain):
        issues.append(
            {
                "severity": "high",
                "kind": "meta_text_remaining",
                "action": "scrub_pass",
            }
        )
        # one more deep scrub of summary
        doc["summary"] = scrub(doc["summary"])

    # Structure requirements
    if not (doc["contact"].get("name") or doc["summary"] or doc["experience"] or doc["projects"]):
        issues.append({"severity": "high", "kind": "empty_document", "action": "fail"})

    # Empty skills/experience ok for some resumes
    high = sum(1 for i in issues if i.get("severity") == "high")
    empty_fail = any(i.get("kind") == "empty_document" for i in issues)
    ok = not empty_fail and high <= 1

    # Approximate content budget (characters) for ~2 pages
    if len(plain) > 9000:
        # Prefer compress rather than delete projects: shrink bullets
        for p in doc["projects"]:
            p["bullets"] = (p.get("bullets") or [])[:3]
        for e in doc["experience"]:
            e["bullets"] = (e.get("bullets") or [])[:5]
        fixed.append("compressed_for_length")
        issues.append(
            {
                "severity": "low",
                "kind": "length_budget",
                "action": "compressed_bullets",
            }
        )

    return {
        "ok": ok,
        "issues": issues,
        "fixed": list(dict.fromkeys(fixed)),
        "document": doc,
        "plain_text": document_plain_text(doc),
    }


def assert_export_safe(doc: dict[str, Any]) -> list[str]:
    """Return hard failures if any (should not export)."""
    failures: list[str] = []
    plain = document_plain_text(doc)
    # Only ban template/meta chrome — never a candidate project named Remote Atlas
    banned = (
        r"\b[Tt]ailored\s+for\b",
        r"\b[Gg]enerated\s+for\b",
        r"\bAI[- ]generated\b",
        r"\b[Gg]enerated\s+by\s+AI\b",
        r"\b[Jj]ob\s+[Mm]atch\s+[Ss]core\b",
        r"\b[Pp]owered\s+by\s+Remote\s+Atlas\b",
        r"\b[Cc]reated\s+with\s+Remote\s+Atlas\b",
    )
    for pat in banned:
        if re.search(pat, plain):
            failures.append(f"contains_meta:{pat}")
            break
    failures.extend(assert_section_uniqueness(doc))
    return failures
