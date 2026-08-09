"""Document quality and professional PDF checks for resume tailoring."""

from app.resume.pdf import (
    assert_pdf_heading_integrity,
    build_resume_pdf,
    count_pdf_section_headings,
    extract_pdf_text,
    pdf_page_count,
    prepare_document_for_export,
)
from app.resume.quality import run_quality_gate
from app.resume.schema import (
    assert_section_uniqueness,
    finalize_document,
    merge_other_sections,
    section_heading_key,
)
from app.resume.skills import build_skill_groups
from app.resume.validate import validate_tailored_payload


SAMPLE_ORIGINAL = """
Muhammad Danish
Full-Stack Software Engineer
danish@example.com | github.com/danish | LinkedIn
Karachi, Pakistan

PROFESSIONAL SUMMARY
Software engineer building web products with TypeScript, React, Next.js, Python, and FastAPI.
Experience with PostgreSQL, Docker, and AI integrations using embeddings and RAG patterns.

TECHNICAL SKILLS
TypeScript, JavaScript, Python, SQL, React, Next.js, Tailwind CSS, Node.js, FastAPI,
PostgreSQL, pgvector, Docker, Git, GitHub, MongoDB, Redis

PROJECTS
Variorum
FastAPI, Next.js, TypeScript, PostgreSQL, pgvector
- Built an AI-powered engineering knowledge platform for software teams.
- Implemented hybrid semantic and keyword search using pgvector and PostgreSQL full-text search.
- Architected provider-agnostic multi-LLM layer with automatic failover across providers.

FYP Idea Generator
Next.js, React, Mistral AI
- Built a research-grounded idea generation platform for students.
- Used retrieval-augmented generation for verifiable recommendations.

Remote Atlas
Next.js, FastAPI, PostgreSQL
- Built a remote job discovery product with hybrid search and resume tooling.

EDUCATION
Air University, Aerospace & Aviation Campus Kamra
BS Computer Science · 2022–2026

REFERENCES
Available upon request
"""


def _base_doc(**overrides):
    doc = {
        "contact": {
            "name": "Muhammad Danish",
            "headline": "Full-Stack Software Engineer",
            "email": "danish@example.com",
        },
        "summary": "Software engineer building web products with TypeScript and FastAPI.",
        "skill_groups": [
            {"category": "Languages", "items": ["TypeScript", "Python"]},
            {"category": "Backend & APIs", "items": ["FastAPI", "Node.js"]},
        ],
        "projects": [
            {
                "name": "Variorum",
                "technologies": ["FastAPI", "Next.js", "PostgreSQL"],
                "bullets": [
                    "Built an AI-powered engineering knowledge platform for software teams.",
                    "Implemented hybrid semantic and keyword search using pgvector.",
                ],
            },
            {
                "name": "FYP Idea Generator",
                "technologies": ["Next.js", "React"],
                "bullets": ["Built a research-grounded idea generation platform for students."],
            },
            {
                "name": "Remote Atlas",
                "technologies": ["Next.js", "FastAPI"],
                "bullets": ["Built a remote job discovery product with hybrid search."],
            },
        ],
        "education": [
            {
                "school": "Air University, Aerospace & Aviation Campus Kamra",
                "degree": "BS Computer Science",
                "dates": "2022–2026",
                "details": [],
            }
        ],
        "other_sections": [],
    }
    doc.update(overrides)
    return doc


def test_dedupe_summary_sections():
    raw = {
        "summary": "Engineer with TypeScript and Python experience.",
        "contact": {"name": "Muhammad Danish", "headline": "Software Engineer"},
        "sections": [
            {
                "heading": "Professional Summary",
                "blocks": [
                    {
                        "type": "paragraph",
                        "text": "Engineer with TypeScript and Python experience.",
                    }
                ],
            },
            {
                "heading": "Summary",
                "blocks": [
                    {
                        "type": "paragraph",
                        "text": "Engineer with TypeScript and Python experience.",
                    }
                ],
            },
        ],
        "skill_groups": [{"category": "Languages", "items": ["TypeScript", "Python"]}],
        "projects": [
            {
                "name": "Variorum",
                "technologies": ["FastAPI", "Next.js"],
                "bullets": ["Built an AI-powered engineering knowledge platform for software teams."],
            }
        ],
    }
    original = SAMPLE_ORIGINAL + " Engineer with TypeScript and Python experience."
    result = validate_tailored_payload(original_text=original, tailored=raw)
    doc = result["tailored"]
    q = run_quality_gate(document=doc, original_text=original)
    final = q["document"]
    assert final.get("summary")
    assert not any("summary" in (s.get("heading") or "").lower() for s in final.get("other_sections") or [])
    pdf = build_resume_pdf(tailored=final)
    text = extract_pdf_text(pdf).lower()
    assert text.count("professional summary") == 1
    assert "summary" in text


def test_no_tailored_for_in_pdf():
    doc = _base_doc()
    q = run_quality_gate(document=doc, original_text=SAMPLE_ORIGINAL)
    pdf = build_resume_pdf(
        tailored=q["document"],
        job_title="Software Engineer - Public Sector",
        company="Unstructured Technologies",
    )
    text = extract_pdf_text(pdf)
    low = text.lower()
    assert "tailored for" not in low
    assert "generated by" not in low
    assert "job match" not in low
    pages = pdf_page_count(pdf)
    assert 1 <= pages <= 2
    assert "PROFESSIONAL SUMMARY" in text.upper() or "professional summary" in low
    assert "TECHNICAL SKILLS" in text.upper() or "technical skills" in low
    assert "Variorum" in text
    assert "FYP Idea Generator" in text
    assert "Air University" in text
    assert "Languages" in text or "languages" in low
    assert "TypeScript" in text or "typescript" in low


def test_skill_filter_does_not_add_unsupported():
    groups = build_skill_groups(
        candidate_skills=["TypeScript", "Python", "Kubernetes", "React"],
        original_text=SAMPLE_ORIGINAL,
        job_keywords=["python", "kubernetes", "react"],
        job_text="Need Python Kubernetes React",
    )
    flat = [i.lower() for g in groups for i in g["items"]]
    assert "python" in flat
    assert "react" in flat
    assert "kubernetes" not in flat


def test_quality_strips_meta_from_summary():
    raw = {
        "summary": "Tailored for Software Engineer. Engineer with React experience.",
        "contact": {"name": "Muhammad Danish"},
        "skill_groups": [{"category": "Frontend", "items": ["React"]}],
    }
    q = run_quality_gate(document=raw, original_text=SAMPLE_ORIGINAL)
    assert "tailored for" not in q["document"]["summary"].lower()


def test_single_references_section_input():
    """Test 1: one References section stays one."""
    raw = _base_doc(
        other_sections=[{"heading": "References", "items": ["Available upon request"]}],
    )
    doc = finalize_document(raw)
    refs = [s for s in doc["other_sections"] if section_heading_key(s["heading"]) == "references"]
    assert len(refs) == 1
    pdf = build_resume_pdf(tailored=doc)
    assert count_pdf_section_headings(extract_pdf_text(pdf)).get("references") == 1


def test_identical_duplicate_references_merge():
    """Test 2: two identical References → one."""
    raw = _base_doc(
        other_sections=[
            {"heading": "References", "items": ["Available upon request"]},
            {"heading": "References", "items": ["Available upon request"]},
        ],
    )
    doc = finalize_document(raw)
    refs = [s for s in doc["other_sections"] if section_heading_key(s["heading"]) == "references"]
    assert len(refs) == 1
    assert assert_section_uniqueness(doc) == []
    pdf = build_resume_pdf(tailored=doc)
    text = extract_pdf_text(pdf)
    assert sum(1 for ln in text.splitlines() if ln.strip().upper() == "REFERENCES") == 1
    assert assert_pdf_heading_integrity(text) == []


def test_case_variants_references_merge():
    """Test 3: References vs REFERENCES map to one key."""
    raw = _base_doc(
        other_sections=[
            {"heading": "References", "items": ["Available upon request"]},
            {"heading": "REFERENCES", "items": ["Available upon request"]},
            {"heading": "Reference", "items": ["Available upon request"]},
        ],
        sections=[
            {
                "heading": "References",
                "blocks": [{"type": "paragraph", "text": "Available upon request"}],
            }
        ],
    )
    assert section_heading_key("REFERENCES") == section_heading_key("References ")
    doc = finalize_document(raw)
    refs = [s for s in doc["other_sections"] if section_heading_key(s["heading"]) == "references"]
    assert len(refs) == 1
    pdf = build_resume_pdf(tailored=doc)
    assert count_pdf_section_headings(extract_pdf_text(pdf)).get("references") == 1


def test_merge_distinct_reference_entries():
    """Test 4: different reference people merged into one section without line dups."""
    raw = _base_doc(
        other_sections=[
            {
                "heading": "References",
                "items": ["John Doe — jane@example.com"],
            },
            {
                "heading": "REFERENCES",
                "items": [
                    "John Doe — jane@example.com",
                    "Bob Smith — bob@example.com",
                ],
            },
        ],
    )
    merged = merge_other_sections(raw["other_sections"])
    assert len(merged) == 1
    items = merged[0]["items"]
    assert len(items) == 2
    assert any("Bob" in i for i in items)
    assert sum(1 for i in items if "John" in i) == 1


def test_duplicate_certifications_detected_and_merged():
    """Test 5: non-References section dups also merge."""
    raw = _base_doc(
        other_sections=[
            {"heading": "Certifications", "items": ["AWS SAA"]},
            {"heading": "CERTIFICATIONS", "items": ["AWS SAA", "CKA"]},
        ],
    )
    doc = finalize_document(raw)
    certs = [
        s for s in doc["other_sections"] if section_heading_key(s["heading"]) == "certifications"
    ]
    assert len(certs) == 1
    assert sorted(certs[0]["items"]) == sorted(["AWS SAA", "CKA"])
    pdf = build_resume_pdf(tailored=doc)
    assert count_pdf_section_headings(extract_pdf_text(pdf)).get("certifications") == 1


def test_no_references_not_invented():
    """Test 6: resume without References does not invent the section."""
    raw = _base_doc(other_sections=[])
    doc = finalize_document(raw)
    assert not any(
        section_heading_key(s["heading"]) == "references" for s in doc["other_sections"]
    )
    pdf = build_resume_pdf(tailored=doc)
    assert "references" not in count_pdf_section_headings(extract_pdf_text(pdf))


def test_end_to_end_each_section_at_most_once():
    """Test 7: full quality + PDF heading integrity for major sections."""
    summary = "Software engineer building web products with TypeScript and FastAPI."
    raw = _base_doc(
        other_sections=[
            {"heading": "References", "items": ["Available upon request"]},
            {"heading": "REFERENCES", "items": ["Available upon request"]},
            {"heading": "References", "items": ["References available upon request"]},
        ],
        sections=[
            {
                "heading": "Professional Summary",
                "blocks": [{"type": "paragraph", "text": summary}],
            },
            {
                "heading": "References",
                "blocks": [{"type": "paragraph", "text": "Available upon request"}],
            },
        ],
    )
    original = SAMPLE_ORIGINAL + " " + summary + " Available upon request."
    v = validate_tailored_payload(original_text=original, tailored=raw)
    q = run_quality_gate(document=v["tailored"], original_text=original)
    final = finalize_document(q["document"])
    assert assert_section_uniqueness(final) == []
    pdf = build_resume_pdf(tailored=final)
    text = extract_pdf_text(pdf)
    counts = count_pdf_section_headings(text)
    assert assert_pdf_heading_integrity(text) == []
    assert counts.get("summary", 0) <= 1
    assert counts.get("skills", 0) <= 1
    assert counts.get("projects", 0) <= 1
    assert counts.get("education", 0) <= 1
    assert counts.get("references", 0) == 1


def test_no_duplicate_references_when_embedded_in_education_and_other():
    """Real-world case: References lives in original, AI copies into education + other_sections."""
    raw = {
        "contact": {"name": "Muhammad Danish", "headline": "Software Engineer"},
        "summary": "Engineer with TypeScript experience.",
        "skill_groups": [{"category": "Languages", "items": ["TypeScript"]}],
        "education": [
            {
                "school": "Air University",
                "degree": "BS Computer Science",
                "dates": "2022-2026",
                "details": [
                    "References",
                    "Available upon request",
                ],
            }
        ],
        "other_sections": [
            {"heading": "References", "items": ["Available upon request"]},
            {"heading": "REFERENCES", "items": ["References available upon request"]},
        ],
        "sections": [
            {
                "heading": "References",
                "blocks": [
                    {"type": "paragraph", "text": "References\nAvailable upon request."}
                ],
            }
        ],
    }
    doc = prepare_document_for_export(raw)
    refs = [s for s in doc["other_sections"] if "reference" in s["heading"].lower()]
    assert len(refs) == 1
    assert not any(
        "reference" in str(d).lower()
        for e in doc.get("education") or []
        for d in (e.get("details") or [])
    )

    pdf = build_resume_pdf(tailored=raw)
    text = extract_pdf_text(pdf)
    heading_lines = [
        ln.strip() for ln in text.splitlines() if ln.strip().upper() == "REFERENCES"
    ]
    assert len(heading_lines) == 1


def test_stored_dual_other_sections_shape_heals():
    """Reproduce production DB shape: two other_sections References + dual legacy sections."""
    raw = _base_doc(
        other_sections=[
            {"heading": "References", "items": ["Available upon request"]},
            {"heading": "References", "items": ["Available upon request"]},
        ],
        sections=[
            {
                "heading": "Technical Skills",
                "blocks": [
                    {"type": "skill_group", "category": "Languages", "items": ["TypeScript"]}
                ],
            },
            {
                "heading": "References",
                "blocks": [{"type": "paragraph", "text": "Available upon request"}],
            },
            {
                "heading": "References",
                "blocks": [{"type": "paragraph", "text": "Available upon request"}],
            },
        ],
    )
    assert len(raw["other_sections"]) == 2
    healed = finalize_document(raw)
    assert (
        len(
            [
                s
                for s in healed["other_sections"]
                if section_heading_key(s["heading"]) == "references"
            ]
        )
        == 1
    )
    assert (
        sum(
            1
            for s in healed.get("sections") or []
            if section_heading_key(s["heading"]) == "references"
        )
        == 1
    )
    pdf = build_resume_pdf(tailored=raw)
    assert count_pdf_section_headings(extract_pdf_text(pdf)).get("references") == 1
