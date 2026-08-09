"""Source provenance classes for ranking and UI — deterministic, no ML."""

from __future__ import annotations

# Prefer official ATS boards over third-party aggregators when rankings tie.
ATS_SOURCES = frozenset(
    {
        "greenhouse",
        "lever",
        "ashby",
        "smartrecruiters",
        "recruitee",
        "workable",
        "personio",
        "teamtailor",
        "breezy",
        "workday",
        "bamboohr",
    }
)

CURATED_BOARD_SOURCES = frozenset(
    {
        "weworkremotely",
        "remotive",
        "remoteok",
        "jobicy",
        "himalayas",
        "arbeitnow",
        "remotejobsorg",
    }
)

AGGREGATOR_SOURCES = frozenset({"themuse"})

# Soft-dedup preference order (lower index wins when titles collide).
PREFERRED_SOURCES_ORDER: tuple[str, ...] = (
    "greenhouse",
    "lever",
    "ashby",
    "smartrecruiters",
    "recruitee",
    "workable",
    "personio",
    "teamtailor",
    "breezy",
    "workday",
    "bamboohr",
    "weworkremotely",
    "remotive",
    "remoteok",
    "jobicy",
    "himalayas",
    "arbeitnow",
    "remotejobsorg",
    "themuse",
)


def source_kind(source: str) -> str:
    s = (source or "").lower()
    if s in ATS_SOURCES:
        return "ats"
    if s in CURATED_BOARD_SOURCES:
        return "curated_board"
    return "aggregator"


def source_trust_rank(source: str) -> int:
    """Lower is better for ordering in SQL CASE expressions."""
    s = (source or "").lower()
    kind = source_kind(s)
    if kind == "ats":
        return 0
    if kind == "curated_board":
        return 1
    return 2


def source_kind_label(source: str) -> str:
    kind = source_kind(source)
    return {
        "ats": "Official ATS board",
        "curated_board": "Curated job board",
        "aggregator": "Job aggregator",
    }[kind]
