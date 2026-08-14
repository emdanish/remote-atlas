from __future__ import annotations

"""Deterministic query intent hints — no LLM."""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class IntentHints:
    career_stage: Optional[str] = None
    workplace: Optional[str] = None
    pakistan_friendly: bool = False
    skills: list[str] = field(default_factory=list)
    cleaned_q: str = ""


_STAGE_MAP = (
    (("internship", "intern", "trainee", "apprentice"), "internship"),
    (("new grad", "newgrad", "fresh graduate", "junior", "entry level", "entry-level", "fresher"), "junior"),
    (("mid-level", "mid level", "intermediate"), "mid"),
    (("senior", "staff ", "principal", "lead "), "senior"),
)

_SKILL_ALIASES = (
    ("react", "react"),
    ("flutter", "flutter"),
    ("python", "python"),
    ("typescript", "typescript"),
    ("javascript", "javascript"),
    ("node.js", "node.js"),
    ("nodejs", "node.js"),
    ("golang", "go"),
    (" go ", "go"),
    ("django", "python"),
    ("fastapi", "python"),
    ("kubernetes", "devops"),
    ("aws", "cloud"),
    ("machine learning", "ai/ml"),
    (" ml ", "ai/ml"),
    ("ai engineer", "ai/ml"),
)


def parse_intent(
    q: Optional[str],
    *,
    workplace: Optional[str] = None,
    career_stage: Optional[str] = None,
    pakistan_friendly: bool = False,
    skills: Optional[list[str]] = None,
) -> IntentHints:
    text = (q or "").strip()
    lower = f" {text.lower()} "
    hints = IntentHints(
        workplace=workplace,
        career_stage=career_stage,
        pakistan_friendly=pakistan_friendly,
        skills=list(skills or []),
        cleaned_q=text,
    )

    if not workplace and any(w in lower for w in (" remote", "remotely", "wfh", "work from home")):
        hints.workplace = "remote"

    if not career_stage:
        for needles, stage in _STAGE_MAP:
            if any(n in lower for n in needles):
                hints.career_stage = stage
                break

    if any(w in lower for w in ("pakistan", "lahore", "karachi", "islamabad", "pk ")):
        hints.pakistan_friendly = True

    found = set(s.lower() for s in hints.skills)
    for needle, skill in _SKILL_ALIASES:
        if needle in lower and skill not in found:
            found.add(skill)
    hints.skills = sorted(found)
    return hints
