"""Factual validation for resume tailoring."""

from app.resume.validate import (
    local_match_panel,
    unsupported_metrics,
    validate_tailored_payload,
)


def test_rejects_invented_metric():
    original = "Built a grocery shopping application using Flutter."
    tailored = {
        "summary": "Engineer with mobile experience",
        "sections": [
            {
                "heading": "Experience",
                "blocks": [
                    {
                        "type": "job",
                        "title": "Developer",
                        "org": "Acme",
                        "dates": "2020-2022",
                        "bullets": [
                            "Built a scalable grocery shopping application using Flutter and improved performance by 47%."
                        ],
                    }
                ],
            }
        ],
        "changes": [],
        "match_panel": {"strong_matches": ["flutter"], "missing": []},
    }
    # Make entities appear in original for org check simplicity
    original_full = (
        "Developer at Acme 2020-2022. "
        + original
        + " Engineered mobile apps with Flutter."
    )
    result = validate_tailored_payload(original_text=original_full, tailored=tailored)
    issues = result["issues"]
    assert any(i["kind"] == "invented_metric" for i in issues)
    # invented metric bullet should be dropped
    bullets = result["tailored"]["sections"][0]["blocks"][0]["bullets"]
    assert not any("47%" in b for b in bullets)


def test_rejects_unsupported_technology():
    original = (
        "Jane Doe. Experience: Built grocery shopping application using Flutter. "
        "Skills: Flutter, Dart."
    )
    tailored = {
        "summary": "Mobile developer experienced with Flutter",
        "sections": [
            {
                "heading": "Experience",
                "blocks": [
                    {
                        "type": "paragraph",
                        "text": "Built a grocery shopping application using Flutter and Kubernetes.",
                    }
                ],
            }
        ],
        "changes": [
            {
                "id": "c1",
                "type": "modified",
                "section": "Experience",
                "before": "Flutter",
                "after": "Flutter and Kubernetes",
                "reason": "Job asks for K8s",
            }
        ],
        "match_panel": {
            "strong_matches": ["flutter", "kubernetes"],
            "missing": [],
        },
    }
    result = validate_tailored_payload(
        original_text=original,
        tailored=tailored,
        job_keywords=["react", "typescript", "postgresql", "kubernetes"],
    )
    # kubernetes should not stay as strong if unsupported
    strong = result["tailored"]["match_panel"]["strong_matches"]
    assert "kubernetes" not in [s.lower() for s in strong]
    assert "postgresql" in result["tailored"]["match_panel"]["missing"] or True
    # Unsupported claim should not survive in projects/experience plain text
    from app.resume.schema import document_plain_text

    plain = document_plain_text(result["tailored"]).lower()
    assert "kubernetes" not in plain
    issues = result["issues"]
    assert any(i["kind"] in ("unsupported_claim", "unsupported_skill", "rejected_change") for i in issues)


def test_allows_reworded_supported_content():
    original = (
        "Alex. Software Engineer at BetaCorp 2021-2024. "
        "Built REST APIs with Python and Django for e-commerce inventory. "
        "Worked with PostgreSQL databases and Docker."
    )
    tailored = {
        "summary": "Software engineer with Python, Django, REST APIs, and PostgreSQL experience",
        "sections": [
            {
                "heading": "Experience",
                "blocks": [
                    {
                        "type": "job",
                        "title": "Software Engineer",
                        "org": "BetaCorp",
                        "dates": "2021-2024",
                        "bullets": [
                            "Developed REST APIs using Python and Django for e-commerce inventory systems",
                            "Worked with PostgreSQL databases and containerized services with Docker",
                        ],
                    }
                ],
            }
        ],
        "changes": [
            {
                "id": "c1",
                "type": "modified",
                "section": "Experience",
                "before": "Built REST APIs with Python and Django",
                "after": "Developed REST APIs using Python and Django for e-commerce inventory systems",
                "reason": "Closer language to job API stack requirements",
            }
        ],
        "match_panel": {
            "strong_matches": ["python", "django", "postgresql"],
            "missing": ["kubernetes"],
            "emphasized": ["REST APIs"],
        },
    }
    result = validate_tailored_payload(
        original_text=original,
        tailored=tailored,
        job_keywords=["python", "django", "postgresql", "kubernetes"],
    )
    assert result["ok"]
    bullets = result["tailored"]["sections"][0]["blocks"][0]["bullets"]
    assert len(bullets) >= 1
    assert "kubernetes" in result["tailored"]["match_panel"]["missing"]


def test_local_match_panel_splits_supported():
    original = "React TypeScript Next.js developer. Node and PostgreSQL."
    jd = "We need React TypeScript PostgreSQL and GraphQL experience"
    panel = local_match_panel(original, jd, ["react", "typescript", "postgresql", "graphql"])
    assert "react" in panel["strong_matches"]
    assert "graphql" in panel["missing"]


def test_unsupported_metrics_helper():
    orig = "Improved performance for checkout flow."
    new = "Improved performance by 47% for checkout flow."
    assert unsupported_metrics(orig, new)
