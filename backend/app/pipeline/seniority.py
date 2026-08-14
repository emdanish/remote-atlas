"""Career-stage and junior-eligible classification.

Never relabel unlabeled IC roles as junior. Junior-eligible is a search flag,
not a stored career_stage rewrite.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Optional

# Title intern / trainee — highest precision.
_INTERN_TITLE = re.compile(
    r"\b(intern|internship|trainee|apprentice|co-?op|coop)\b",
    re.I,
)
_SENIOR_TITLE = re.compile(
    r"\b(staff|principal|distinguished|fellow|senior|sr\.?|lead|manager|"
    r"director|head of|vp|vice president)\b",
    re.I,
)
_NEW_GRAD_TITLE = re.compile(
    r"\b(new[\s-]?grad(?:uate)?s?|university grad|campus hire|"
    r"class of 20\d{2}|grad(?:uate)? program|university graduate)\b",
    re.I,
)
_JUNIOR_TITLE = re.compile(
    r"\b(junior|jr\.?|entry[\s-]?level|fresher|fresh graduate|"
    r"early career|associate (?:software|engineer|developer)|"
    r"(?:software |swe |sde )?engineer i\b|swe i\b|sde i\b|"
    r"engineer 1\b|level 1\b)\b",
    re.I,
)
_MID_TITLE = re.compile(r"\b(mid[\s-]?level|intermediate)\b", re.I)

# Years in requirements: "5+ years", "minimum 3 years", "0-2 years", "at least 4 yrs"
_YEARS_RANGE = re.compile(
    r"\b(?:(?:minimum|min(?:imum)?\.?|at least|over|more than)\s+)?"
    r"(\d+)\s*(?:\+|plus)?\s*(?:[-–to]{1,3}\s*(\d+)\s*)?"
    r"(?:years?|yrs?)\b",
    re.I,
)
_ZERO_TWO = re.compile(
    r"\b(0\s*[-–to]{1,3}\s*2|0-2|no (?:prior )?experience|little to no experience)\b",
    re.I,
)

_NO_SPONSOR = re.compile(
    r"\b(no sponsorship|not (?:able|eligible) to sponsor|must be (?:authorized|eligible) to work|"
    r"without sponsorship|us citizen(?:ship)? required|citizenship required)\b",
    re.I,
)
_DEGREE = re.compile(
    r"\b(bachelor'?s(?: degree)? required|degree required|must have a (?:bachelor|master))\b",
    re.I,
)
_UNPAID = re.compile(r"\b(unpaid intern|unpaid internship)\b", re.I)
_EQUIV = re.compile(
    r"\b(or equivalent|bootcamp|self-taught|career changer|"
    r"portfolio in lieu|equivalent experience)\b",
    re.I,
)

_SOURCE_LEVEL_MAP = (
    (("intern", "internship", "trainee", "apprentice"), "internship"),
    (("new grad", "new graduate", "university", "campus", "graduate"), "new_grad"),
    (("entry", "junior", "early career", "associate"), "junior"),
    (("mid", "intermediate"), "mid"),
    (("senior", "staff", "principal", "lead", "director", "manager"), "senior"),
)

JUNIOR_ELIGIBLE_STAGES = frozenset({"internship", "new_grad", "junior"})
SENIOR_STAGES = frozenset({"mid", "senior"})
JUNIOR_PROFILE_LEVELS = frozenset(
    {"internship", "intern", "new_grad", "junior", "entry", "entry-level"}
)
ELIGIBLE_SEARCH_ALIASES = frozenset(
    {
        "junior",
        "entry",
        "entry-level",
        "entry_level",
        "fresh",
        "fresh_graduate",
    }
)


@dataclass
class SeniorityClassification:
    career_stage: str
    years_required_min: Optional[int]
    junior_eligible: bool
    employment_type: Optional[str]
    signals: dict[str, Any] = field(default_factory=dict)


def parse_years_required_min(title: str, description: Optional[str] = None) -> Optional[int]:
    blob = f"{title}\n{(description or '')[:2500]}"
    if _ZERO_TWO.search(blob):
        return 0
    mins: list[int] = []
    for match in _YEARS_RANGE.finditer(blob):
        low = int(match.group(1))
        # Ignore "10 years of the company" style noise over 20
        if low > 15:
            continue
        mins.append(low)
    if not mins:
        return None
    return min(mins)


def _stage_from_source_level(source_level: Optional[str]) -> Optional[str]:
    if not source_level:
        return None
    blob = source_level.lower()
    for needles, stage in _SOURCE_LEVEL_MAP:
        if any(n in blob for n in needles):
            return stage
    return None


def infer_career_stage(
    title: str,
    description: Optional[str] = None,
    *,
    source_level: Optional[str] = None,
    employment_type: Optional[str] = None,
) -> str:
    """Title-first. Never maps unlabeled Software Engineer → junior."""
    title_l = title or ""
    emp = (employment_type or "").lower()
    blob = f"{title_l} {(description or '')[:800]}"

    if _INTERN_TITLE.search(title_l) or "intern" in emp:
        return "internship"
    sourced = _stage_from_source_level(source_level)
    if sourced == "internship":
        return "internship"
    if _SENIOR_TITLE.search(title_l):
        return "senior"
    if _NEW_GRAD_TITLE.search(title_l) or sourced == "new_grad":
        return "new_grad"
    if _JUNIOR_TITLE.search(title_l) or sourced == "junior":
        return "junior"
    if _MID_TITLE.search(title_l) or sourced == "mid":
        return "mid"
    if sourced == "senior":
        return "senior"
    if _INTERN_TITLE.search(blob):
        return "internship"
    return "unknown"


def extract_seniority_signals(
    title: str,
    description: Optional[str] = None,
    *,
    source_level: Optional[str] = None,
) -> dict[str, Any]:
    blob = f"{title}\n{(description or '')[:2500]}"
    flags: dict[str, Any] = {}
    if source_level:
        flags["source_level"] = source_level[:80]
    sponsor = _NO_SPONSOR.search(blob)
    if sponsor:
        flags["no_sponsorship"] = True
        flags["no_sponsorship_snippet"] = sponsor.group(0)[:120]
    degree = _DEGREE.search(blob)
    if degree:
        flags["degree_required"] = True
        flags["degree_snippet"] = degree.group(0)[:120]
    unpaid = _UNPAID.search(blob)
    if unpaid:
        flags["unpaid"] = True
        flags["unpaid_snippet"] = unpaid.group(0)[:120]
    equiv = _EQUIV.search(blob)
    if equiv:
        flags["equivalent_ok"] = True
        flags["equivalent_snippet"] = equiv.group(0)[:120]
    return flags


def compute_junior_eligible(
    *,
    career_stage: str,
    years_required_min: Optional[int],
    title: str,
) -> bool:
    stage = (career_stage or "unknown").lower()
    if stage in SENIOR_STAGES:
        return False
    if years_required_min is not None and years_required_min >= 3:
        return False
    if _SENIOR_TITLE.search(title or "") and stage not in JUNIOR_ELIGIBLE_STAGES:
        return False
    if stage in JUNIOR_ELIGIBLE_STAGES:
        return True
    # unknown IC: eligible only if not senior-coded and years are null or ≤2
    if stage == "unknown":
        return years_required_min is None or years_required_min <= 2
    return False


def classify_job(
    title: str,
    description: Optional[str] = None,
    *,
    source_level: Optional[str] = None,
    employment_type: Optional[str] = None,
) -> SeniorityClassification:
    emp = employment_type
    stage = infer_career_stage(
        title,
        description,
        source_level=source_level,
        employment_type=emp,
    )
    if stage == "internship" and not (emp or "").lower():
        emp = "internship"
    years = parse_years_required_min(title, description)
    signals = extract_seniority_signals(title, description, source_level=source_level)
    eligible = compute_junior_eligible(
        career_stage=stage,
        years_required_min=years,
        title=title,
    )
    if stage in {"junior", "new_grad"} and years is not None and years >= 4:
        eligible = False
        signals["title_jd_contradiction"] = True
        signals["contradiction"] = (
            f"Title looks {stage} but JD asks {years}+ years"
        )
    signals["junior_eligible"] = eligible
    return SeniorityClassification(
        career_stage=stage,
        years_required_min=years,
        junior_eligible=eligible,
        employment_type=emp,
        signals=signals,
    )


def seniority_query(
    career_stage: Optional[str] = None,
    *,
    junior_eligible: bool = False,
) -> tuple[bool, Optional[str]]:
    """Map search params to (filter_junior_eligible_flag, exact_career_stage).

    `career_stage=junior` is the eligible *set*, not exact junior. Internship
    and new_grad stay exact. Never rewrite unknown rows.
    """
    stage = (career_stage or "").strip().lower().replace(" ", "_")
    if stage in {"internship", "intern"}:
        return False, "internship"
    if junior_eligible or stage in ELIGIBLE_SEARCH_ALIASES:
        return True, None
    if stage in {"new_grad", "new-grad", "newgrad"}:
        return False, "new_grad"
    if stage:
        return False, stage
    return False, None


def exclude_for_junior_profile(job: Any, level: Optional[str]) -> bool:
    """Hide senior/staff and 3+ year IC roles from junior/intern/new-grad matches."""
    if (level or "").lower() not in JUNIOR_PROFILE_LEVELS:
        return False
    stage = (getattr(job, "career_stage", None) or "unknown").lower()
    if stage in SENIOR_STAGES:
        return True
    years = getattr(job, "years_required_min", None)
    if years is not None and years >= 3:
        return True
    if getattr(job, "junior_eligible", True) is False and stage not in JUNIOR_ELIGIBLE_STAGES:
        return True
    return False
