"""Canonical tech vs capability tagging for resumes and matching.

Technologies = languages, frameworks, tools, platforms.
Skills (soft/capability) = methods, domains, collaboration — not the full tech list.
Matching uses the *union* of both, with generous partial/description hits.
"""

from __future__ import annotations

import re
from typing import Iterable

# Hard technologies (incl. versions stripped later)
KNOWN_TECHNOLOGIES: set[str] = {
    "python",
    "javascript",
    "typescript",
    "java",
    "kotlin",
    "swift",
    "go",
    "golang",
    "rust",
    "c++",
    "c#",
    "php",
    "ruby",
    "scala",
    "sql",
    "html",
    "css",
    "react",
    "react.js",
    "reactjs",
    "next.js",
    "nextjs",
    "node.js",
    "nodejs",
    "vue",
    "vue.js",
    "angular",
    "svelte",
    "express",
    "express.js",
    "fastapi",
    "django",
    "flask",
    "spring",
    "spring boot",
    "nest.js",
    "nestjs",
    "graphql",
    "rest",
    "rest api",
    "postgresql",
    "postgres",
    "mysql",
    "mongodb",
    "redis",
    "sqlite",
    "supabase",
    "prisma",
    "sqlalchemy",
    "alembic",
    "docker",
    "docker-compose",
    "kubernetes",
    "k8s",
    "aws",
    "azure",
    "gcp",
    "terraform",
    "git",
    "github",
    "gitlab",
    "ci/cd",
    "pytest",
    "jest",
    "vite",
    "webpack",
    "tailwind",
    "tailwind css",
    "framer motion",
    "recharts",
    "livekit",
    "uvicorn",
    "pydantic",
    "jwt",
    "oauth",
    "websockets",
    "websocket",
    "pgvector",
    "tree-sitter",
    "vercel",
    "nginx",
    "linux",
    "bash",
    "numpy",
    "pandas",
    "pytorch",
    "tensorflow",
    "scikit-learn",
    "openai",
    "anthropic",
    "langchain",
    "huggingface",
    "gemini",
    "google gemini api",
    "google gemini",
    "deepseek",
    "deepseek api",
    "perplexity",
    "perplexity api",
    "mistral",
    "mistral ai",
    "claude",
    "anthropic claude api",
    "assemblyai",
    "mcp",
    "ruff",
    "mypy",
    "hmac",
    "hmac webhooks",
    "github apps",
    "react router",
}

# Capability / soft / process — belong in skills, not technologies
KNOWN_CAPABILITIES: set[str] = {
    "agile",
    "scrum",
    "agile collaboration",
    "collaboration",
    "communication",
    "technical communication",
    "leadership",
    "mentoring",
    "problem solving",
    "system design",
    "api design",
    "product thinking",
    "devops",
    "cloud",
    "cloud-native development",
    "full-stack development",
    "full stack",
    "frontend",
    "backend",
    "ai/ml",
    "ai application development",
    "machine learning",
    "llm integration",
    "prompt engineering",
    "rag design",
    "retrieval augmented generation",
    "semantic search",
    "tool use and function calling",
    "multi-step workflow orchestration",
    "end-to-end delivery",
    "performance optimization",
    "production deployment",
    "responsible ai",
    "system prompt design",
    "oauth",
    "testing",
    "unit testing",
    "integration testing",
}

# Aliases for matching (profile label → job text variants)
SKILL_ALIASES: dict[str, tuple[str, ...]] = {
    "react": ("react", "react.js", "reactjs", "react native"),
    "next.js": ("next.js", "nextjs", "next js"),
    "node.js": ("node.js", "nodejs", "node js"),
    "postgresql": ("postgresql", "postgres", "psql"),
    "typescript": ("typescript", "ts"),
    "javascript": ("javascript", "js", "es6"),
    "python": ("python", "py", "django", "flask", "fastapi"),
    "docker": ("docker", "container", "containers"),
    "fastapi": ("fastapi", "fast api"),
    "ai/ml": ("machine learning", "deep learning", "llm", "ml ", " ai ", "nlp"),
    "tailwind css": ("tailwind", "tailwindcss"),
    "graphql": ("graphql", "graph ql"),
    "ci/cd": ("ci/cd", "cicd", "continuous integration", "github actions"),
}


def normalize_tag(value: str) -> str:
    s = re.sub(r"\s+", " ", (value or "").strip().lower())
    s = s.strip(" ,;|/·•")
    # light canonicalization
    aliases = {
        "reactjs": "react",
        "react.js": "react",
        "nextjs": "next.js",
        "nodejs": "node.js",
        "postgres": "postgresql",
        "tailwindcss": "tailwind css",
        "fast api": "fastapi",
        "js": "javascript",
        "ts": "typescript",
        "golang": "go",
        "k8s": "kubernetes",
    }
    return aliases.get(s, s)


def _looks_like_technology(tag: str) -> bool:
    t = normalize_tag(tag)
    if not t or len(t) < 2:
        return False
    if t in KNOWN_TECHNOLOGIES:
        return True
    if t in KNOWN_CAPABILITIES:
        return False
    # Heuristics for tools / languages not in the fixed set
    if any(x in t for x in (".js", ".ts", "api", "sql", "db", "cloud", "lang", "stack")):
        # "llm integration" is capability, "gemini api" is tech
        if any(
            w in t
            for w in (
                "integration",
                "orchestration",
                "development",
                "deployment",
                "communication",
                "collaboration",
                "engineering",
                "design",
                "optimization",
            )
        ) and t not in KNOWN_TECHNOLOGIES:
            return False
    if re.match(r"^[a-z][a-z0-9+.#-]{0,32}$", t) and " " not in t:
        # short token like "vite", "ruff" — treat as tech unless soft
        soft_tokens = {"agile", "scrum", "leadership", "mentoring", "collaboration"}
        return t not in soft_tokens
    # multi-word: if it ends in api / sdk / lib-like → tech
    if t.endswith(" api") or t.endswith(" sdk") or t.endswith(" cli"):
        return True
    return t in KNOWN_TECHNOLOGIES


def _looks_like_capability(tag: str) -> bool:
    t = normalize_tag(tag)
    if t in KNOWN_CAPABILITIES:
        return True
    if t in KNOWN_TECHNOLOGIES:
        return False
    soft_bits = (
        "collaboration",
        "communication",
        "leadership",
        "mentoring",
        "development",
        "design",
        "orchestration",
        "optimization",
        "deployment",
        "engineering",
        "delivery",
        "prompt",
        "responsible",
        "agile",
        "scrum",
        "workflow",
    )
    return any(b in t for b in soft_bits)


def partition_skills_and_technologies(
    *groups: Iterable[str],
) -> tuple[list[str], list[str]]:
    """
    Return (skills/capabilities, technologies).

    Items that look like tech go only into technologies.
    Soft / process terms go only into skills.
    Ambiguous mid terms may appear in both categories only when AI labeled them soft
    — here we keep tech exclusive, capabilities exclusive, leftovers → technologies
    if they look tool-like else skills.
    """
    raw: list[str] = []
    for group in groups:
        for item in group or []:
            n = normalize_tag(str(item))
            if n and len(n) >= 2:
                raw.append(n)
    # stable unique
    seen: set[str] = set()
    ordered: list[str] = []
    for item in raw:
        if item not in seen:
            seen.add(item)
            ordered.append(item)

    technologies: list[str] = []
    skills: list[str] = []
    for item in ordered:
        tech = _looks_like_technology(item)
        cap = _looks_like_capability(item)
        if tech and not cap:
            technologies.append(item)
        elif cap and not tech:
            skills.append(item)
        elif tech and cap:
            # e.g. oauth — prefer technologies for tool tokens, skills for phrases
            if " " in item:
                skills.append(item)
            else:
                technologies.append(item)
        else:
            # unknown multiword → capability; single token → tech
            if " " in item:
                skills.append(item)
            else:
                technologies.append(item)

    # Cap list sizes for profile UX
    technologies = technologies[:48]
    skills = skills[:40]
    # Never mirror the entire tech list into skills
    tech_set = set(technologies)
    skills = [s for s in skills if s not in tech_set][:40]
    if not skills and technologies:
        # Provide high-level stack buckets instead of cloning tech list
        skills = _infer_capability_buckets(technologies)
    return skills, technologies


def _infer_capability_buckets(technologies: list[str]) -> list[str]:
    t = set(technologies)
    out: list[str] = []
    if t & {"react", "next.js", "vue", "angular", "typescript", "javascript", "html", "css"}:
        out.append("frontend development")
    if t & {"python", "fastapi", "django", "flask", "node.js", "express.js", "java", "go"}:
        out.append("backend development")
    if {"react", "python"} <= t or {"next.js", "fastapi"} <= t or ("typescript" in t and "python" in t):
        out.append("full-stack development")
    if t & {"docker", "kubernetes", "ci/cd", "aws", "azure", "gcp", "terraform"}:
        out.append("devops")
    if t & {
        "ai/ml",
        "pytorch",
        "tensorflow",
        "pgvector",
        "langchain",
        "openai",
        "gemini",
        "claude",
    } or any("llm" in x or "gemini" in x or "claude" in x for x in t):
        out.append("ai application development")
    if t & {"postgresql", "mysql", "mongodb", "sql", "redis", "supabase"}:
        out.append("data modeling")
    if not out:
        out = ["software development"]
    return out[:8]


def profile_skill_universe(skills: Iterable[str] | None, technologies: Iterable[str] | None) -> set[str]:
    """Union used for matching (not for UI profile fields)."""
    out: set[str] = set()
    for item in list(skills or []) + list(technologies or []):
        n = normalize_tag(str(item))
        if n:
            out.add(n)
            for alias, variants in SKILL_ALIASES.items():
                if n == alias or n in variants:
                    out.add(alias)
                    out.update(variants)
    return out


def job_skill_universe(job) -> set[str]:
    tags = list(getattr(job, "skills", None) or []) + list(getattr(job, "tech_tags", None) or [])
    out = {normalize_tag(str(s)) for s in tags if s}
    # expand aliases
    expanded = set(out)
    for s in out:
        for alias, variants in SKILL_ALIASES.items():
            if s == alias or s in variants:
                expanded.add(alias)
                expanded.update(variants)
    return {x for x in expanded if x}


def generous_skill_overlap(
    profile_skills: set[str],
    job,
) -> tuple[list[str], list[str]]:
    """
    Matched + sample missing.

    Matches against structured tags and free-text title/description generously.
    """
    job_tags = job_skill_universe(job)
    title = (getattr(job, "title", None) or "").lower()
    desc = (getattr(job, "description_text", None) or "")[:4000].lower()
    blob = f" {title} {desc} "

    matched: list[str] = []
    for skill in sorted(profile_skills):
        if not skill or len(skill) < 2:
            continue
        if skill in job_tags:
            matched.append(skill)
            continue
        variants = SKILL_ALIASES.get(skill, (skill,))
        hit = False
        for v in variants:
            if not v or len(v) < 2:
                continue
            if v in job_tags or f" {v} " in blob or v in title:
                hit = True
                break
            # phrase without spaces
            if v.replace(".", "").replace("-", "") in blob.replace(".", "").replace("-", ""):
                hit = True
                break
        if hit:
            matched.append(skill)

    # de-dupe keep order
    seen: set[str] = set()
    matched_u: list[str] = []
    for m in matched:
        if m not in seen:
            seen.add(m)
            matched_u.append(m)

    missing = sorted(job_tags - set(matched_u))[:6]
    return matched_u, missing
