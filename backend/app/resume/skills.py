"""Deterministic skill grouping + job relevance ranking (no invention)."""

from __future__ import annotations

import re
from typing import Any

# Taxonomies map lowercase skill → category. Unmapped skills go to "Additional Skills".
CATEGORY_MAP: dict[str, str] = {
    # Languages
    "python": "Languages",
    "javascript": "Languages",
    "typescript": "Languages",
    "java": "Languages",
    "go": "Languages",
    "golang": "Languages",
    "rust": "Languages",
    "c++": "Languages",
    "c#": "Languages",
    "ruby": "Languages",
    "php": "Languages",
    "swift": "Languages",
    "kotlin": "Languages",
    "scala": "Languages",
    "r": "Languages",
    "sql": "Languages",
    "bash": "Languages",
    "shell": "Languages",
    "html": "Languages",
    "css": "Languages",
    "dart": "Languages",
    # Frontend
    "react": "Frontend",
    "react.js": "Frontend",
    "reactjs": "Frontend",
    "next.js": "Frontend",
    "nextjs": "Frontend",
    "vue": "Frontend",
    "vue.js": "Frontend",
    "angular": "Frontend",
    "svelte": "Frontend",
    "tailwind": "Frontend",
    "tailwind css": "Frontend",
    "redux": "Frontend",
    "vite": "Frontend",
    "webpack": "Frontend",
    "jquery": "Frontend",
    "bootstrap": "Frontend",
    "sass": "Frontend",
    "scss": "Frontend",
    # Backend
    "node": "Backend & APIs",
    "node.js": "Backend & APIs",
    "nodejs": "Backend & APIs",
    "express": "Backend & APIs",
    "express.js": "Backend & APIs",
    "fastapi": "Backend & APIs",
    "django": "Backend & APIs",
    "flask": "Backend & APIs",
    "spring": "Backend & APIs",
    "spring boot": "Backend & APIs",
    "rails": "Backend & APIs",
    "rest": "Backend & APIs",
    "rest api": "Backend & APIs",
    "rest apis": "Backend & APIs",
    "graphql": "Backend & APIs",
    "grpc": "Backend & APIs",
    "fastapi": "Backend & APIs",
    "nestjs": "Backend & APIs",
    "asp.net": "Backend & APIs",
    ".net": "Backend & APIs",
    # AI
    "ai": "AI & LLM",
    "ml": "AI & LLM",
    "machine learning": "AI & LLM",
    "deep learning": "AI & LLM",
    "llm": "AI & LLM",
    "llms": "AI & LLM",
    "gpt": "AI & LLM",
    "openai": "AI & LLM",
    "gemini": "AI & LLM",
    "deepseek": "AI & LLM",
    "claude": "AI & LLM",
    "rag": "AI & LLM",
    "embeddings": "AI & LLM",
    "langchain": "AI & LLM",
    "vector": "AI & LLM",
    "pgvector": "AI & LLM",
    "prompt engineering": "AI & LLM",
    "nlp": "AI & LLM",
    "computer vision": "AI & LLM",
    "pytorch": "AI & LLM",
    "tensorflow": "AI & LLM",
    "huggingface": "AI & LLM",
    # Data / DB
    "postgresql": "Databases",
    "postgres": "Databases",
    "mysql": "Databases",
    "mongodb": "Databases",
    "redis": "Databases",
    "sqlite": "Databases",
    "elasticsearch": "Databases",
    "dynamodb": "Databases",
    "cassandra": "Databases",
    "supabase": "Databases",
    # Cloud / DevOps
    "docker": "DevOps & Cloud",
    "kubernetes": "DevOps & Cloud",
    "k8s": "DevOps & Cloud",
    "aws": "DevOps & Cloud",
    "gcp": "DevOps & Cloud",
    "azure": "DevOps & Cloud",
    "terraform": "DevOps & Cloud",
    "ci/cd": "DevOps & Cloud",
    "github actions": "DevOps & Cloud",
    "jenkins": "DevOps & Cloud",
    "vercel": "DevOps & Cloud",
    "nginx": "DevOps & Cloud",
    "linux": "DevOps & Cloud",
    "git": "DevOps & Cloud",
    "github": "DevOps & Cloud",
    "gitlab": "DevOps & Cloud",
    # Mobile
    "flutter": "Mobile",
    "react native": "Mobile",
    "ios": "Mobile",
    "android": "Mobile",
    # Testing
    "pytest": "Testing",
    "jest": "Testing",
    "cypress": "Testing",
    "playwright": "Testing",
    "selenium": "Testing",
    "unit testing": "Testing",
}


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").lower().strip())


def categorize_skill(skill: str) -> str:
    n = _norm(skill)
    if n in CATEGORY_MAP:
        return CATEGORY_MAP[n]
    # partial keys
    for key, cat in CATEGORY_MAP.items():
        if len(key) >= 3 and (key in n or n in key):
            return cat
    return "Additional Skills"


def skill_relevance(skill: str, job_keywords: list[str], job_text: str) -> float:
    """Higher = more relevant to JD. Never invents — ranking only."""
    n = _norm(skill)
    score = 0.3  # base keep-weight for supported skills
    jn = _norm(job_text)
    kws = {_norm(k) for k in job_keywords if k}
    if n in kws or n in jn:
        score += 3.0
    for kw in kws:
        if len(kw) >= 3 and (kw in n or n in kw):
            score += 1.5
            break
    if any(t in jn for t in n.split() if len(t) >= 4):
        score += 0.5
    # common core stack slight boost if language/framework words
    if categorize_skill(skill) in {"Languages", "Backend & APIs", "Frontend", "AI & LLM"}:
        score += 0.15
    return score


_ACRONYM_DISPLAY = {
    "ai/ml": "AI/ML",
    "ci/cd": "CI/CD",
    "rest api": "REST API",
    "rest apis": "REST APIs",
    "api": "API",
    "apis": "APIs",
    "sql": "SQL",
    "html": "HTML",
    "css": "CSS",
    "aws": "AWS",
    "gcp": "GCP",
    "llm": "LLM",
    "rag": "RAG",
    "nlp": "NLP",
}


def _collapse_variants(items: list[str]) -> list[str]:
    """Drop "JavaScript" when "JavaScript (ES6+)" is also present."""
    bases: dict[str, int] = {}
    out: list[str] = []
    for item in items:
        base = _norm(re.sub(r"\s*[(\[].*$", "", item))
        if not base:
            continue
        if base in bases:
            idx = bases[base]
            if len(item) > len(out[idx]):
                out[idx] = item
            continue
        bases[base] = len(out)
        out.append(item)
    return out


def _display_skill(key: str, variants: list[str], original_text: str) -> str:
    """Pick the casing the resume itself uses, so skills never render lowercased."""
    if key in _ACRONYM_DISPLAY:
        return _ACRONYM_DISPLAY[key]
    match = re.search(rf"(?<![\w+#.]){re.escape(key)}(?![\w+#.])", original_text, re.I)
    if match:
        found = match.group(0)
        if any(c.isupper() for c in found):
            return found
    for v in variants:
        if any(c.isupper() for c in v):
            return v
    return variants[0]


def build_skill_groups(
    *,
    candidate_skills: list[str],
    original_text: str,
    job_keywords: list[str] | None = None,
    job_text: str = "",
    max_groups: int = 7,
    max_per_group: int = 10,
    max_total: int = 36,
) -> list[dict[str, Any]]:
    """
    Build categorized skills from ONLY skills already present in original text.
    Rank by JD relevance; drop weak/irrelevant when over budget.
    """
    from app.resume.validate import phrase_supported, original_phrase_index

    orig = original_phrase_index(original_text)
    job_keywords = job_keywords or []

    # Collect every spelling per skill, then render the one the resume actually uses
    variants: dict[str, list[str]] = {}
    order: list[str] = []
    for s in candidate_skills:
        v = re.sub(r"\s+", " ", (s or "").strip())
        if not v:
            continue
        key = _norm(v)
        if len(key) < 2 or not phrase_supported(v, orig):
            continue
        if key not in variants:
            variants[key] = []
            order.append(key)
        variants[key].append(v)

    supported = _collapse_variants(
        [_display_skill(key, variants[key], original_text) for key in order]
    )

    ranked = sorted(
        supported,
        key=lambda s: skill_relevance(s, job_keywords, job_text),
        reverse=True,
    )[:max_total]

    buckets: dict[str, list[str]] = {}
    cat_scores: dict[str, float] = {}
    for s in ranked:
        cat = categorize_skill(s)
        buckets.setdefault(cat, [])
        if len(buckets[cat]) >= max_per_group:
            continue
        buckets[cat].append(s)
        cat_scores[cat] = cat_scores.get(cat, 0) + skill_relevance(s, job_keywords, job_text)

    # Prefer databases category when present (core for eng roles)
    prefer = [
        "Languages",
        "Backend & APIs",
        "Frontend",
        "AI & LLM",
        "Databases",
        "DevOps & Cloud",
        "Mobile",
        "Testing",
        "Additional Skills",
    ]
    ordered_cats = sorted(
        buckets.keys(),
        key=lambda c: (
            prefer.index(c) if c in prefer else 50,
            -cat_scores.get(c, 0),
        ),
    )
    # drop empty; cap groups keeping prefer order
    ordered_cats = [c for c in ordered_cats if buckets.get(c)][:max_groups]
    if "Additional Skills" in buckets and "Additional Skills" not in ordered_cats:
        if len(ordered_cats) >= max_groups:
            ordered_cats[-1] = "Additional Skills"
        else:
            ordered_cats.append("Additional Skills")

    groups = [{"category": c, "items": buckets[c]} for c in ordered_cats if buckets.get(c)]
    return groups[:max_groups]


def derive_headline(
    *,
    contact_headline: str,
    resume_facts: dict[str, Any],
    job_title: str,
    original_text: str,
) -> str:
    """
    Pick a professional title. Prefer original headline; never invent senior titles.
    """
    from app.resume.validate import phrase_supported, original_phrase_index

    orig = original_phrase_index(original_text)
    if contact_headline and phrase_supported(contact_headline, orig):
        return _clip_headline(contact_headline)

    # scan first lines of resume for title under name
    lines = [ln.strip() for ln in original_text.splitlines() if ln.strip()][:8]
    title_re = re.compile(
        r"^(software|full[- ]?stack|frontend|front-end|backend|back-end|data|ml|ai|"
        r"mobile|devops|cloud|security|product|web|platform|systems?)\s+"
        r"(engineer|developer|scientist|architect|intern|specialist|analyst)",
        re.I,
    )
    for ln in lines[1:5]:
        if title_re.search(ln) and len(ln) < 80:
            return _clip_headline(ln)
        if re.match(r"^[A-Za-z][A-Za-z0-9 /|,&+\-]{4,60}$", ln) and any(
            w in ln.lower()
            for w in ("engineer", "developer", "scientist", "intern", "designer")
        ):
            return _clip_headline(ln)

    roles = resume_facts.get("roles") or []
    for r in roles[:2]:
        t = str((r or {}).get("title") or "").strip()
        if t and phrase_supported(t, orig):
            return _clip_headline(t)

    # Soft derive from job target only if very generic and not inflated
    jt = (job_title or "").strip()
    # strip company-specific fluff
    jt = re.sub(r"\s*[-–—].*$", "", jt).strip()
    jt = re.sub(r"\s*\(.*\)$", "", jt).strip()
    senior_tokens = ("senior", "staff", "principal", "lead", "director", "head of", "vp ")
    if jt and not any(s in jt.lower() for s in senior_tokens):
        if any(w in orig for w in ("engineer", "developer", "software", "programmer")):
            jl = jt.lower()
            if len(jt) <= 48 and (
                "intern" in jl or "engineer" in jl or "developer" in jl
            ):
                return _clip_headline(jt)
    if "engineer" in orig or "developer" in orig:
        return "Software Engineer"
    return ""


def _clip_headline(text: str, limit: int = 80) -> str:
    """Trim to the last complete segment/word so headlines never end mid-word."""
    t = re.sub(r"\s+", " ", (text or "").strip())
    if len(t) <= limit:
        return t
    head = t[:limit]
    for sep in ("|", "·", ",", ";"):
        if sep in head:
            trimmed = head.rsplit(sep, 1)[0].strip(" |·,;")
            if len(trimmed) >= limit // 2:
                return trimmed
    return head.rsplit(" ", 1)[0].strip(" |·,;")
