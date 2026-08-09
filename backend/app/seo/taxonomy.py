"""Programmatic SEO taxonomy helpers: slugs, quality gates, known intents.

Indexable landings only when inventory is meaningful (people-first, not thin pages).
Maps to clean URLs like /remote-javascript-jobs and /companies/acme.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Optional

# Minimum fresh+active jobs for an indexable landing page.
MIN_SKILL_JOBS = 12
MIN_COMPANY_JOBS = 5
MIN_LOCATION_JOBS = 8

# Curated skills with clear search demand (Remote OK–style skill landings).
# Only these can become /remote-{slug}-jobs pages even if DB has junk tags.
SEO_SKILL_MAP: dict[str, str] = {
    "javascript": "JavaScript",
    "typescript": "TypeScript",
    "python": "Python",
    "react": "React",
    "next-js": "Next.js",
    "node-js": "Node.js",
    "java": "Java",
    "go": "Go",
    "rust": "Rust",
    "php": "PHP",
    "ruby": "Ruby",
    "kotlin": "Kotlin",
    "swift": "Swift",
    "sql": "SQL",
    "postgresql": "PostgreSQL",
    "mongodb": "MongoDB",
    "mysql": "MySQL",
    "redis": "Redis",
    "graphql": "GraphQL",
    "docker": "Docker",
    "kubernetes": "Kubernetes",
    "aws": "AWS",
    "azure": "Azure",
    "gcp": "GCP",
    "fastapi": "FastAPI",
    "django": "Django",
    "flask": "Flask",
    "vue": "Vue",
    "angular": "Angular",
    "svelte": "Svelte",
    "express": "Express",
    "terraform": "Terraform",
    "linux": "Linux",
    "tailwind-css": "Tailwind CSS",
    "pytorch": "PyTorch",
    "tensorflow": "TensorFlow",
    "langchain": "LangChain",
}

# Map DB tags (lowercase) → SEO skill slug
TAG_TO_SKILL_SLUG: dict[str, str] = {
    "javascript": "javascript",
    "js": "javascript",
    "typescript": "typescript",
    "ts": "typescript",
    "python": "python",
    "react": "react",
    "react.js": "react",
    "reactjs": "react",
    "next.js": "next-js",
    "nextjs": "next-js",
    "node.js": "node-js",
    "nodejs": "node-js",
    "java": "java",
    "go": "go",
    "golang": "go",
    "rust": "rust",
    "php": "php",
    "ruby": "ruby",
    "kotlin": "kotlin",
    "swift": "swift",
    "sql": "sql",
    "postgresql": "postgresql",
    "postgres": "postgresql",
    "mongodb": "mongodb",
    "mysql": "mysql",
    "redis": "redis",
    "graphql": "graphql",
    "docker": "docker",
    "kubernetes": "kubernetes",
    "k8s": "kubernetes",
    "aws": "aws",
    "azure": "azure",
    "gcp": "gcp",
    "fastapi": "fastapi",
    "django": "django",
    "flask": "flask",
    "vue": "vue",
    "vue.js": "vue",
    "angular": "angular",
    "svelte": "svelte",
    "express": "express",
    "express.js": "express",
    "terraform": "terraform",
    "linux": "linux",
    "tailwind": "tailwind-css",
    "tailwind css": "tailwind-css",
    "pytorch": "pytorch",
    "tensorflow": "tensorflow",
    "langchain": "langchain",
}

# Country landings: slug → (label, matching SQL fragments for location_raw / flags)
SEO_COUNTRIES: dict[str, dict] = {
    "pakistan": {
        "label": "Pakistan",
        "patterns": ["pakistan", "pk", "lahore", "karachi", "islamabad"],
        "use_pakistan_friendly": True,
    },
    "united-states": {
        "label": "United States",
        "patterns": ["united states", "usa", "u.s.", " us ", "america"],
        "use_pakistan_friendly": False,
    },
    "united-kingdom": {
        "label": "United Kingdom",
        "patterns": ["united kingdom", "uk", "england", "london", "scotland"],
        "use_pakistan_friendly": False,
    },
    "canada": {
        "label": "Canada",
        "patterns": ["canada", "toronto", "vancouver", "montreal"],
        "use_pakistan_friendly": False,
    },
    "germany": {
        "label": "Germany",
        "patterns": ["germany", "berlin", "munich", "deutschland"],
        "use_pakistan_friendly": False,
    },
    "india": {
        "label": "India",
        "patterns": ["india", "bangalore", "bengaluru", "mumbai", "hyderabad", "delhi"],
        "use_pakistan_friendly": False,
    },
    "worldwide": {
        "label": "Worldwide",
        "patterns": ["worldwide", "anywhere", "global", "remote worldwide", "international"],
        "use_pakistan_friendly": False,
    },
}

SEO_CITIES: dict[str, dict] = {
    "islamabad": {
        "label": "Islamabad",
        "patterns": ["islamabad"],
        "country_slug": "pakistan",
    },
    "lahore": {
        "label": "Lahore",
        "patterns": ["lahore"],
        "country_slug": "pakistan",
    },
    "karachi": {
        "label": "Karachi",
        "patterns": ["karachi"],
        "country_slug": "pakistan",
    },
    "london": {
        "label": "London",
        "patterns": ["london"],
        "country_slug": "united-kingdom",
    },
    "toronto": {
        "label": "Toronto",
        "patterns": ["toronto"],
        "country_slug": "canada",
    },
    "berlin": {
        "label": "Berlin",
        "patterns": ["berlin"],
        "country_slug": "germany",
    },
}


def slugify_company(name: str) -> str:
    text = unicodedata.normalize("NFKD", name or "")
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = re.sub(r"-{2,}", "-", text).strip("-")
    return text[:80] or "company"


def skill_href(slug: str) -> str:
    return f"/remote-{slug}-jobs"


def company_href(slug: str) -> str:
    return f"/companies/{slug}"


def location_href(slug: str, *, city: bool = False) -> str:
    if city:
        return f"/remote-jobs/city/{slug}"
    return f"/remote-jobs/{slug}"


def skill_label(slug: str) -> Optional[str]:
    return SEO_SKILL_MAP.get(slug)


def parse_skill_slug_from_path(slug: str) -> Optional[str]:
    """Accept either javascript or javascript-jobs residue."""
    s = (slug or "").strip().lower()
    if s.endswith("-jobs"):
        s = s[: -len("-jobs")]
    if s in SEO_SKILL_MAP:
        return s
    return None


def normalize_title_key(title: str) -> str:
    t = re.sub(r"\s+", " ", (title or "").strip())
    # Strip common remote noise for grouping suggestions only
    t = re.sub(
        r"\s*[-|–—]\s*(remote|hybrid|wfh|work from home).*$",
        "",
        t,
        flags=re.I,
    )
    t = re.sub(r"\s*\((remote|hybrid)\)\s*$", "", t, flags=re.I)
    return t.strip()[:100]
