"""The tailored resume must never lose the user's content.

Covers the regression where an AI/provider failure produced a near-empty resume:
the deterministic parser is the source of truth and AI output is merged onto it.
"""

import io

from app.resume.extract import extract_text
from app.resume.parse import parse_resume_text
from app.resume.pdf import (
    assert_pdf_heading_integrity,
    build_resume_pdf,
    count_pdf_section_headings,
    extract_pdf_text,
    pdf_page_count,
)
from app.resume.quality import run_quality_gate
from app.resume.schema import finalize_document, section_heading_key
from app.resume.validate import (
    content_integrity_failures,
    merge_tailored_onto_original,
    repair_against_original,
    validate_tailored_payload,
)

# Mirrors real PDF extraction: headings on their own line, no blank lines,
# bullets wrapped across lines without bullet glyphs.
REAL_RESUME = """MUHAMMAD DANISH
Full-Stack Developer | AI-Powered Applications | Claude API, LLM Integrations, RAG
Pakistan | +92 345 5636030 | muhammadd03@gmail.com
linkedin.com/in/emdanish | github.com/emdanish | emdanish.dev
PROFESSIONAL SUMMARY
Full-stack developer building AI-powered web applications with React, Next.js, TypeScript, Node.js, and Python
(FastAPI). Hands-on across the modern LLM stack: prompt engineering, retrieval-augmented generation (RAG),
embeddings, and streaming responses.
TECHNICAL SKILLS
Languages: TypeScript, JavaScript (ES6+), Python, Java, SQL, HTML, CSS
Frontend: React, Next.js (App Router, SSR), Tailwind CSS, Vite, React Router
Backend and APIs: Node.js, Express.js, FastAPI, SQLAlchemy, Alembic, REST API design, GraphQL, WebSockets
Databases and Vector Search: PostgreSQL, pgvector, full-text search (tsvector), Supabase, MongoDB
DevOps and Practices: Git, GitHub, Docker, CI/CD, Vercel, pytest, Agile / Scrum
PROFESSIONAL EXPERIENCE
Junior Software Engineer 02/2026 - Present
Arken Systems
Core engineer on Recruitimate, an AI-native hiring platform: own features end to end across a Next.js and
TypeScript frontend and a FastAPI backend on a multi-tenant PostgreSQL architecture.
Implemented retrieval-augmented generation (RAG) for resume screening with an embedding-based retrieve-then-
rerank pipeline on PostgreSQL with pgvector.
Frontend Engineer 02/2025 - 06/2026
RemoteFlow
Built responsive, reusable UI components in Next.js, React, and TypeScript for a scalable AI-powered job
automation platform, following a server-first architecture.
Full Stack Developer 06/2025 - 09/2025
Baccalytics
Built a multi-tenant EdTech web platform for IB schools, teachers, and students using Next.js and Supabase.
Junior Software Developer 05/2024 - 12/2024
Alabtaal Developers
Developed a records management and performance reporting solution using Java Spring Boot.
SELECTED PROJECTS
Variorum | FastAPI, Next.js 15, React 19, TypeScript, PostgreSQL, pgvector, tree-sitter, Multi-LLM (Gemini,
DeepSeek, Perplexity), RAG, GitHub Apps
Founder and lead engineer of Variorum, an AI-powered engineering knowledge platform that gives software teams
a living memory of their codebase.
FYP Idea Generator | Next.js, React, Mistral AI, CORE Research API, Supabase, Tailwind CSS
Research-grounded idea engine for final year students, retrieving peer-reviewed literature through the CORE
Research API.
Radiant Thought | React, TypeScript, Supabase, Gemini API, Tailwind CSS
AI journaling application with Supabase authentication and Gemini-powered entry titles and reflective insights.
EDUCATION
BS Computer Science (BSCS) 09/2022 - 06/2026
Air University, Aerospace and Aviation Campus Kamra | CGPA: 3.59 | Graduated June 2026
Relevant Coursework: Artificial Intelligence, Data Structures and Algorithms, Database Management Systems.
REFERENCES
Available upon request.
"""


def _baseline():
    return finalize_document(parse_resume_text(REAL_RESUME))


def test_parser_recovers_every_section_without_ai():
    doc = _baseline()
    assert doc["contact"]["name"] == "Muhammad Danish"
    assert doc["contact"]["email"] == "muhammadd03@gmail.com"
    assert doc["contact"]["phone"].endswith("5636030")
    assert doc["contact"]["location"] == "Pakistan"
    assert "linkedin.com/in/emdanish" in doc["contact"]["links"]
    assert "gmail.com" not in doc["contact"]["links"]

    assert len(doc["summary"]) > 100
    assert len(doc["skill_groups"]) == 5
    assert len(doc["experience"]) == 4
    assert [e["org"] for e in doc["experience"]] == [
        "Arken Systems",
        "RemoteFlow",
        "Baccalytics",
        "Alabtaal Developers",
    ]
    assert all(e["dates"] for e in doc["experience"])
    assert all(e["bullets"] for e in doc["experience"])

    assert [p["name"] for p in doc["projects"]] == [
        "Variorum",
        "FYP Idea Generator",
        "Radiant Thought",
    ]
    assert all(p["technologies"] for p in doc["projects"])
    # a parenthesised tech list wrapped across two lines stays one entry
    assert "Multi-LLM (Gemini, DeepSeek, Perplexity)" in doc["projects"][0]["technologies"]

    assert len(doc["education"]) == 1
    assert "Air University" in doc["education"][0]["school"]
    assert "BS Computer Science" in doc["education"][0]["degree"]
    assert any("CGPA" in d for d in doc["education"][0]["details"])

    assert [section_heading_key(s["heading"]) for s in doc["other_sections"]] == ["references"]


def test_flattened_zero_newline_resume_still_parses_all_sections():
    """Regression: some PDF extracts collapse the whole CV to one line."""
    flat = " ".join(ln.strip() for ln in REAL_RESUME.splitlines() if ln.strip())
    assert "\n" not in flat
    doc = finalize_document(parse_resume_text(flat))
    assert doc["contact"]["name"] == "Muhammad Danish"
    assert doc["contact"]["email"] == "muhammadd03@gmail.com"
    assert doc["contact"]["location"] == "Pakistan"
    assert len(doc["summary"]) > 100
    assert len(doc["skill_groups"]) == 5
    assert len(doc["experience"]) == 4
    assert [e["org"] for e in doc["experience"]] == [
        "Arken Systems",
        "RemoteFlow",
        "Baccalytics",
        "Alabtaal Developers",
    ]
    assert [p["name"] for p in doc["projects"]] == [
        "Variorum",
        "FYP Idea Generator",
        "Radiant Thought",
    ]
    assert "Air University" in doc["education"][0]["school"]
    assert [section_heading_key(s["heading"]) for s in doc["other_sections"]] == ["references"]
    # Prose "experience" must not create a false experience section that blanked content
    assert not _document_empty(doc)


def _document_empty(doc: dict) -> bool:
    return not any(
        [
            doc.get("summary"),
            doc.get("experience"),
            doc.get("projects"),
            doc.get("education"),
            doc.get("skill_groups"),
            doc.get("other_sections"),
        ]
    )


def test_remote_atlas_project_name_is_not_scrubbed_as_meta():
    from app.resume.quality import assert_export_safe, run_quality_gate

    doc = finalize_document(
        {
            "contact": {"name": "Muhammad Danish", "headline": "Software Engineer"},
            "summary": "Builder of tools for remote job search.",
            "skill_groups": [{"category": "Skills", "items": ["Python", "TypeScript"]}],
            "experience": [],
            "projects": [
                {
                    "name": "Remote Atlas Companion",
                    "technologies": ["Next.js", "FastAPI"],
                    "bullets": ["Job-search companion with resume tailoring."],
                }
            ],
            "education": [],
            "other_sections": [],
            "match_panel": {},
            "changes": [],
        }
    )
    quality = run_quality_gate(document=doc, original_text="Remote Atlas Companion project")
    cleaned = quality["document"]
    assert cleaned["projects"][0]["name"] == "Remote Atlas Companion"
    assert not assert_export_safe(cleaned)


def test_wrapped_lines_and_broken_words_are_healed():
    text = """JANE DOE
Backend Engineer
Berlin | jane@example.com
TECHNICAL SKILLS
AI / LLM: prompt engineering, AI agents and multi-
step workflows, guardrails and
responsible AI
PROFESSIONAL EXPERIENCE
Backend Engineer 01/2023 - Present
Acme
Implemented an embedding-based retrieve-then-
rerank pipeline on PostgreSQL with pgvector.
"""
    doc = parse_resume_text(text)
    items = [i for g in doc["skill_groups"] for i in g["items"]]
    assert "AI agents and multi-step workflows" in items
    assert "guardrails and responsible AI" in items
    assert "step workflows" not in items
    assert "retrieve-then-rerank" in doc["experience"][0]["bullets"][0]


def test_truncated_ai_output_cannot_delete_sections():
    """The exact production failure: AI returned only skills."""
    base = _baseline()
    truncated = {"skill_groups": [{"category": "Languages", "items": ["TypeScript", "Python"]}]}

    merged = merge_tailored_onto_original(original=base, tailored=truncated)

    assert merged["summary"]
    assert len(merged["experience"]) == 4
    assert len(merged["projects"]) == 3
    assert len(merged["education"]) == 1
    assert merged["skill_groups"]
    assert [section_heading_key(s["heading"]) for s in merged["other_sections"]] == ["references"]
    assert content_integrity_failures(original=base, final=merged) == []


def test_empty_ai_output_preserves_original_exactly():
    base = _baseline()
    merged = merge_tailored_onto_original(original=base, tailored={})
    assert content_integrity_failures(original=base, final=merged) == []
    assert merged["contact"]["name"] == base["contact"]["name"]
    assert len(merged["experience"]) == len(base["experience"])


def test_ai_wording_is_applied_to_matching_entries():
    base = _baseline()
    tailored = {
        "summary": "Full-stack developer focused on RAG systems with FastAPI and PostgreSQL.",
        "experience": [
            {
                "title": "Junior Software Engineer",
                "org": "Arken Systems",
                "dates": "02/2026 - Present",
                "bullets": ["Delivered retrieval-augmented generation pipelines with pgvector."],
            }
        ],
    }
    merged = merge_tailored_onto_original(original=base, tailored=tailored)

    assert merged["summary"].startswith("Full-stack developer focused on RAG")
    assert len(merged["experience"]) == 4  # other three roles untouched
    arken = next(e for e in merged["experience"] if e["org"] == "Arken Systems")
    assert arken["bullets"] == [
        "Delivered retrieval-augmented generation pipelines with pgvector."
    ]
    assert arken["dates"] == "02/2026 - Present"
    remoteflow = next(e for e in merged["experience"] if e["org"] == "RemoteFlow")
    assert remoteflow["bullets"] == next(
        e for e in base["experience"] if e["org"] == "RemoteFlow"
    )["bullets"]


def test_contact_facts_are_immutable():
    base = _baseline()
    tailored = {
        "contact": {
            "name": "Someone Else",
            "email": "fake@evil.com",
            "phone": "+1 555 0000",
            "location": "Remote",
            "headline": "Backend Engineer | RAG Systems",
        }
    }
    merged = merge_tailored_onto_original(original=base, tailored=tailored)
    assert merged["contact"]["name"] == "Muhammad Danish"
    assert merged["contact"]["email"] == "muhammadd03@gmail.com"
    assert merged["contact"]["phone"].endswith("5636030")
    assert merged["contact"]["location"] == "Pakistan"
    # headline is a positioning line, so tailoring it is allowed
    assert merged["contact"]["headline"] == "Backend Engineer | RAG Systems"


def test_references_are_not_rewritten_by_ai():
    text = REAL_RESUME.replace(
        "REFERENCES\nAvailable upon request.",
        "REFERENCES\nJane Roe, Engineering Manager, Arken Systems, jane@example.com",
    )
    base = finalize_document(parse_resume_text(text))
    tailored = {
        "other_sections": [
            {"heading": "References", "items": ["Bob Fake, CTO, Nowhere Inc, bob@fake.com"]}
        ]
    }
    merged = merge_tailored_onto_original(original=base, tailored=tailored)
    refs = [s for s in merged["other_sections"] if section_heading_key(s["heading"]) == "references"]
    assert len(refs) == 1
    assert any("Jane Roe" in i for i in refs[0]["items"])
    assert not any("Bob Fake" in i for i in refs[0]["items"])


def test_custom_sections_survive_the_pipeline():
    text = REAL_RESUME.replace(
        "REFERENCES\nAvailable upon request.",
        "CERTIFICATIONS\nAWS Certified Solutions Architect - Associate.\n"
        "LEADERSHIP EXPERIENCE\nLed the university developer society for two semesters.\n"
        "OPEN SOURCE\nMaintainer of a small TypeScript utility library.\n"
        "REFERENCES\nAvailable upon request.",
    )
    doc = finalize_document(parse_resume_text(text))
    keys = [section_heading_key(s["heading"]) for s in doc["other_sections"]]
    assert "certifications" in keys
    assert "leadership experience" in keys
    assert "open source" in keys
    assert "references" in keys

    q = run_quality_gate(document=doc, original_text=text)
    final = finalize_document(q["document"])
    assert content_integrity_failures(original=doc, final=final) == []

    pdf = build_resume_pdf(tailored=final)
    body = extract_pdf_text(pdf)
    assert "LEADERSHIP EXPERIENCE" in body.upper()
    assert "OPEN SOURCE" in body.upper()
    assert "AWS Certified Solutions Architect" in body
    assert assert_pdf_heading_integrity(body) == []


def test_duplicates_merge_without_deleting_anything():
    """Duplicate headings collapse to one section; no content is discarded."""
    doc = {
        "contact": {"name": "Ann Lee", "email": "ann@example.com", "phone": "+1 555 111 2222"},
        "summary": "Backend engineer with Python and PostgreSQL experience.",
        "skill_groups": [{"category": "Languages", "items": ["Python", "SQL"]}],
        "experience": [
            {
                "title": "Engineer",
                "org": "Acme",
                "dates": "2022 - Present",
                "bullets": ["Built APIs with FastAPI."],
            }
        ],
        "projects": [{"name": "Widget", "technologies": ["Python"], "bullets": ["Built a widget."]}],
        "education": [
            {"school": "State University", "degree": "BS CS", "dates": "2018 - 2022", "details": []}
        ],
        "other_sections": [
            {"heading": "Summary", "items": ["Extra summary line that only exists here."]},
            {"heading": "References", "items": ["Jane Roe - jane@example.com"]},
            {"heading": "REFERENCES", "items": ["Bob Poe - bob@example.com"]},
            {"heading": "Certifications", "items": ["AWS SAA"]},
            {"heading": "Leadership Experience", "items": ["Led the robotics club."]},
            {"heading": "Open Source Projects", "items": ["Maintainer of a CLI tool."]},
        ],
    }
    final = finalize_document(doc)

    keys = [section_heading_key(s["heading"]) for s in final["other_sections"]]
    assert keys.count("references") == 1
    assert "leadership experience" in keys  # custom heading not collapsed into experience
    assert "open source projects" in keys  # nor into projects
    # a core-keyed extra section is folded into the field, not deleted
    assert "Extra summary line that only exists here." in final["summary"]

    body = extract_pdf_text(build_resume_pdf(tailored=final))
    counts = count_pdf_section_headings(body)
    assert counts.get("references") == 1
    assert counts.get("summary") == 1
    assert assert_pdf_heading_integrity(body) == []
    for marker in (
        "Jane Roe",
        "Bob Poe",
        "AWS SAA",
        "Led the robotics club",
        "Maintainer of a CLI tool",
    ):
        assert marker in body, f"content lost while deduplicating: {marker}"


def test_no_references_section_is_never_invented():
    text = REAL_RESUME.replace("REFERENCES\nAvailable upon request.\n", "")
    base = finalize_document(parse_resume_text(text))
    merged = merge_tailored_onto_original(
        original=base,
        tailored={"other_sections": [{"heading": "References", "items": ["Available upon request"]}]},
    )
    assert content_integrity_failures(original=base, final=merged) == ["invented_references"]


def test_integrity_check_detects_section_loss_and_repairs_it():
    base = _baseline()
    damaged = {
        "contact": base["contact"],
        "skill_groups": base["skill_groups"],
        "summary": "",
        "experience": [],
        "projects": [],
        "education": [],
        "other_sections": [],
    }
    failures = content_integrity_failures(original=base, final=finalize_document(damaged))
    assert "missing_summary" in failures
    assert any(f.startswith("lost_experience") for f in failures)
    assert any(f.startswith("lost_projects") for f in failures)
    assert any(f.startswith("lost_education") for f in failures)
    assert "lost_section:references" in failures

    repaired = repair_against_original(original=base, final=damaged)
    assert content_integrity_failures(original=base, final=repaired) == []


def test_hallucinated_employer_is_dropped_but_real_roles_remain():
    base = _baseline()
    hallucinated = {
        "experience": [
            {
                "title": "Engineering Manager",
                "org": "Globex Corporation",
                "dates": "01/2020 - 01/2024",
                "bullets": ["Led a team of 12 engineers and increased revenue by 300%."],
            }
        ]
    }
    validated = validate_tailored_payload(
        original_text=REAL_RESUME, tailored=hallucinated, job_keywords=[]
    )
    merged = merge_tailored_onto_original(original=base, tailored=validated["tailored"])
    orgs = " ".join(e.get("org", "") for e in merged["experience"]).lower()
    body = " ".join(b for e in merged["experience"] for b in e["bullets"]).lower()
    assert "globex" not in orgs
    assert "team of 12" not in body
    assert len(merged["experience"]) == 4


def test_full_document_export_is_complete_and_unique():
    base = _baseline()
    q = run_quality_gate(document=base, original_text=REAL_RESUME)
    final = finalize_document(q["document"])
    assert content_integrity_failures(original=base, final=final) == []

    pdf = build_resume_pdf(tailored=final)
    body = extract_pdf_text(pdf)
    counts = count_pdf_section_headings(body)

    assert pdf_page_count(pdf) <= 2
    assert counts.get("summary") == 1
    assert counts.get("skills") == 1
    assert counts.get("experience") == 1
    assert counts.get("projects") == 1
    assert counts.get("education") == 1
    assert counts.get("references") == 1
    assert assert_pdf_heading_integrity(body) == []

    for marker in (
        "Muhammad Danish",
        "Arken Systems",
        "RemoteFlow",
        "Baccalytics",
        "Alabtaal Developers",
        "Variorum",
        "FYP Idea Generator",
        "Radiant Thought",
        "Air University",
    ):
        assert marker in body, f"missing from exported PDF: {marker}"


def _resume_pdf_bytes(text: str) -> bytes:
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    width, height = letter
    y = height - 50
    for line in text.splitlines():
        if y < 50:
            c.showPage()
            y = height - 50
        c.setFont("Helvetica", 9)
        c.drawString(45, y, line[:110])
        y -= 12
    c.save()
    return buf.getvalue()


def _resume_docx_bytes(text: str) -> bytes:
    from docx import Document

    doc = Document()
    for line in text.splitlines():
        doc.add_paragraph(line)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def test_pdf_upload_round_trip_preserves_sections():
    parsed = parse_resume_text(extract_text(_resume_pdf_bytes(REAL_RESUME), "resume.pdf"))
    doc = finalize_document(parsed)
    assert doc["contact"]["name"] == "Muhammad Danish"
    assert len(doc["experience"]) == 4
    assert len(doc["projects"]) == 3
    assert len(doc["education"]) == 1
    assert [section_heading_key(s["heading"]) for s in doc["other_sections"]] == ["references"]


def test_docx_upload_round_trip_preserves_sections():
    parsed = parse_resume_text(extract_text(_resume_docx_bytes(REAL_RESUME), "resume.docx"))
    doc = finalize_document(parsed)
    assert doc["contact"]["name"] == "Muhammad Danish"
    assert len(doc["experience"]) == 4
    assert len(doc["projects"]) == 3
    assert len(doc["education"]) == 1
    assert [section_heading_key(s["heading"]) for s in doc["other_sections"]] == ["references"]
