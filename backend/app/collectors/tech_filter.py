"""Shared technical-title filter for collectors."""

from __future__ import annotations


def looks_technical(title: str, departments: object = None) -> bool:
    t = title.lower()
    exclude = (
        "account executive",
        "sales ",
        " salesperson",
        "recruiter",
        "talent acquisition",
        "customer success",
        "account manager",
        "business development",
        "marketing",
        "content writer",
        "legal counsel",
        "attorney",
    )
    if any(x in t for x in exclude):
        return False
    tech_words = (
        "engineer",
        "developer",
        "software",
        "sre",
        "devops",
        "backend",
        "frontend",
        "full stack",
        "fullstack",
        "data scientist",
        "data engineer",
        "machine learning",
        "ml engineer",
        "ai engineer",
        "android",
        "ios",
        "mobile",
        "platform",
        "infrastructure",
        "security engineer",
        "qa",
        "quality assurance",
        "intern",
        "apprentice",
        "researcher",
        "scientist",
        "flutter",
        "react",
        "python",
        "golang",
        "typescript",
    )
    if any(w in t for w in tech_words):
        return True
    if isinstance(departments, list):
        for d in departments:
            name = (d.get("name") if isinstance(d, dict) else str(d)).lower()
            if any(w in name for w in ("engineer", "engineering", "software", "data", "security", "it")):
                if any(w in t for w in ("engineer", "developer", "scientist", "analyst", "architect", "intern")):
                    return True
    return False


def looks_technical_category(categories: object) -> bool:
    if not categories:
        return False
    joined = " ".join(str(c).lower() for c in categories)
    tokens = (
        "engineer",
        "software",
        "developer",
        "devops",
        "data",
        "machine-learning",
        "machine learning",
        "ai ",
        "backend",
        "frontend",
        "full-stack",
        "fullstack",
        "qa",
        "security",
        "sre",
        "mobile",
        "android",
        "ios",
        "programming",
        "tech",
    )
    return any(t in joined for t in tokens)


def looks_like_software_role(title: str, description: str | None) -> bool:
    """Reject physical/facilities engineering false positives after detail fetch."""
    title_lower = title.lower()
    explicit = (
        "software",
        "developer",
        "devops",
        "sre",
        "backend",
        "frontend",
        "full stack",
        "data engineer",
        "data scientist",
        "machine learning",
        "ai engineer",
        "security engineer",
        "qa engineer",
        "quality assurance",
        "mobile engineer",
        "android",
        "ios",
    )
    if any(value in title_lower for value in explicit):
        return True
    blob = f"{title}\n{(description or '')[:5000]}".lower()
    software_signals = (
        "software development",
        "programming language",
        "source code",
        "code review",
        "web application",
        "cloud platform",
        "rest api",
        "microservices",
        "javascript",
        "typescript",
        "python",
        "golang",
        "kubernetes",
        "database",
    )
    physical_signals = (
        "mechanical engineering",
        "electrical engineering",
        "plumbing",
        "building maintenance",
        "construction site",
        "hotel engineering",
        "manufacturing equipment",
    )
    positives = sum(value in blob for value in software_signals)
    negatives = sum(value in blob for value in physical_signals)
    return positives > 0 and positives >= negatives
