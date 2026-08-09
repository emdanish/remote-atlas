from __future__ import annotations

import re
from typing import Iterable

# Canonical skill/tag -> alias patterns (matched case-insensitively as whole tokens / phrases)
SKILL_LEXICON: dict[str, list[str]] = {
    "python": [r"\bpython\b", r"\bdjango\b", r"\bflask\b", r"\bfastapi\b"],
    "javascript": [r"\bjavascript\b", r"\bjs\b"],
    "typescript": [r"\btypescript\b", r"\bts\b"],
    "react": [r"\breact(?:\.?js)?\b", r"\breact native\b"],
    "next.js": [r"\bnext\.?js\b"],
    "node.js": [r"\bnode\.?js\b", r"\bnodejs\b"],
    "java": [r"\bjava\b", r"\bspring boot\b"],
    "kotlin": [r"\bkotlin\b"],
    "swift": [r"\bswift\b"],
    "flutter": [r"\bflutter\b", r"\bdart\b"],
    "go": [r"\bgolang\b", r"\bgo(?:lang)?\b"],
    "rust": [r"\brust\b"],
    "c++": [r"\bc\+\+\b"],
    "c#": [r"\bc#\b", r"\b\.net\b"],
    "php": [r"\bphp\b", r"\blaravel\b"],
    "ruby": [r"\bruby\b", r"\brails\b"],
    "ai/ml": [
        r"\bmachine learning\b",
        r"\bdeep learning\b",
        r"\bartificial intelligence\b",
        r"\b\bai\b",
        r"\bml\b",
        r"\bllm\b",
        r"\bnlp\b",
        r"\bpytorch\b",
        r"\btensorflow\b",
    ],
    "devops": [r"\bdevops\b", r"\bci/?cd\b", r"\bkubernetes\b", r"\bk8s\b", r"\bdocker\b"],
    "cloud": [r"\baws\b", r"\bazure\b", r"\bgcp\b", r"\bgoogle cloud\b", r"\bcloud\b"],
    "postgresql": [r"\bpostgres(?:ql)?\b"],
    "mongodb": [r"\bmongo(?:db)?\b"],
    "redis": [r"\bredis\b"],
    "graphql": [r"\bgraphql\b"],
    "vue": [r"\bvue(?:\.?js)?\b"],
    "angular": [r"\bangular\b"],
    "android": [r"\bandroid\b"],
    "ios": [r"\bios\b"],
    "sql": [r"\bsql\b"],
    "terraform": [r"\bterraform\b"],
}

_PK_CITIES = {
    "islamabad": "Islamabad",
    "rawalpindi": "Rawalpindi",
    "lahore": "Lahore",
    "karachi": "Karachi",
    "peshawar": "Peshawar",
    "faisalabad": "Faisalabad",
    "multan": "Multan",
    "hyderabad": "Hyderabad",
}

_PK_FRIENDLY = re.compile(
    r"\b(pakistan|pk|worldwide|anywhere|timezone.?flexible|work from anywhere|"
    r"remote[\s-]first|candidates in apac|based in apac|all countries|"
    r"south asia|mena|emea|global(?:ly)?|location.?independent|"
    r"open to remote|remote worldwide|work remotely from|"
    r"lahore|karachi|islamabad|rawalpindi)\b",
    re.I,
)


def extract_skills(text: str, existing: Iterable[str] | None = None) -> list[str]:
    found: set[str] = set()
    if existing:
        found.update(s.strip().lower() for s in existing if s and s.strip())
    blob = text or ""
    for skill, patterns in SKILL_LEXICON.items():
        for pattern in patterns:
            if re.search(pattern, blob, flags=re.I):
                found.add(skill)
                break
    return sorted(found)


def detect_pakistan_city(location: str | None) -> str | None:
    if not location:
        return None
    lower = location.lower()
    for key, label in _PK_CITIES.items():
        if key in lower:
            return label
    return None


def is_pakistan_friendly_remote(workplace_type: str, location: str | None, description: str | None) -> bool:
    if workplace_type != "remote":
        return False
    blob = f"{location or ''} {description or ''}"
    if detect_pakistan_city(location):
        return True
    return bool(_PK_FRIENDLY.search(blob))


def enrich_job_fields(
    title: str,
    description: str | None,
    location: str | None,
    existing_skills: list[str] | None = None,
    existing_tags: list[str] | None = None,
) -> dict:
    blob = f"{title}\n{description or ''}\n{location or ''}"
    skills = extract_skills(blob, existing_skills)
    tags = extract_skills(blob, existing_tags)
    # Prefer intersection-ish: keep both lists similar for MVP
    return {
        "skills": skills,
        "tech_tags": tags,
        "pk_city": detect_pakistan_city(location),
    }
