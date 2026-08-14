from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from app.pipeline.seniority import (
    classify_job,
    infer_career_stage,
)
from app.pipeline.description import (
    html_to_text,
    looks_like_encoded_html,
    looks_like_html,
    normalize_job_description_fields,
)

# Tracking / session params that create false-unique apply URLs
_STRIP_QUERY_KEYS = frozenset(
    {
        "utm_source",
        "utm_medium",
        "utm_campaign",
        "utm_term",
        "utm_content",
        "utm_id",
        "gh_src",
        "gh_jid",
        "source",
        "ref",
        "referrer",
        "fbclid",
        "gclid",
        "mc_cid",
        "mc_eid",
        "si",
        "s",
        "trk",
    }
)

_WS_RE = re.compile(r"\s+")


@dataclass
class NormalizedJob:
    source: str
    external_id: str
    title: str
    company_name: str
    company_url: Optional[str] = None
    career_page_url: Optional[str] = None
    apply_url: Optional[str] = None
    description_text: Optional[str] = None
    description_html: Optional[str] = None
    location_raw: Optional[str] = None
    workplace_type: str = "unknown"
    employment_type: Optional[str] = None
    career_stage: str = "unknown"
    years_required_min: Optional[int] = None
    junior_eligible: bool = False
    seniority_signals: Optional[dict] = None
    skills: list[str] = field(default_factory=list)
    tech_tags: list[str] = field(default_factory=list)
    posted_at: Optional[datetime] = None
    company_id: Optional[int] = None
    source_level: Optional[str] = None


# Re-export description helpers for collectors
__all__ = [
    "NormalizedJob",
    "html_to_text",
    "normalize_url",
    "canonical_apply_url",
    "parse_datetime",
    "infer_workplace_type",
    "infer_career_stage",
    "classify_job",
    "apply_classification",
    "fingerprint",
    "apply_url_is_usable",
    "normalize_job_description_fields",
    "looks_like_html",
    "looks_like_encoded_html",
]


def normalize_url(url: Optional[str]) -> Optional[str]:
    if not url:
        return None
    url = url.strip()
    parsed = urlparse(url)
    if not parsed.scheme:
        return url
    clean = parsed._replace(fragment="", query=parsed.query)
    return urlunparse(clean)


def canonical_apply_url(url: Optional[str]) -> Optional[str]:
    """Stable apply URL for cross-source soft-dedup (host + path, strip tracking)."""
    if not url:
        return None
    text = url.strip()
    if not text:
        return None
    parsed = urlparse(text)
    if not parsed.scheme:
        text = "https://" + text
        parsed = urlparse(text)
    host = (parsed.hostname or "").lower().removeprefix("www.")
    if not host:
        return normalize_url(url)
    path = parsed.path or ""
    if path != "/" and path.endswith("/"):
        path = path[:-1]
    # Drop common query noise while keeping meaningful job IDs in path
    pairs = [
        (k, v)
        for k, v in parse_qsl(parsed.query, keep_blank_values=False)
        if k.lower() not in _STRIP_QUERY_KEYS
    ]
    query = urlencode(sorted(pairs)) if pairs else ""
    return urlunparse(("https", host, path, "", query, ""))


def parse_datetime(value: object) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    if isinstance(value, (int, float)):
        # RemoteOK uses epoch seconds
        ts = float(value)
        if ts > 1e12:
            ts /= 1000.0
        return datetime.fromtimestamp(ts, tz=timezone.utc)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            dt = datetime.fromisoformat(text)
        except ValueError:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    return None


def infer_workplace_type(
    location: Optional[str] = None,
    explicit: Optional[str] = None,
    description: Optional[str] = None,
) -> str:
    def _as_str(value: object) -> Optional[str]:
        if value is None:
            return None
        if isinstance(value, str):
            return value
        if isinstance(value, dict):
            for key in ("name", "label", "id", "type"):
                if isinstance(value.get(key), str) and value.get(key):
                    return value[key]
            return None
        return str(value)

    blob = " ".join(
        filter(None, [_as_str(explicit), _as_str(location), _as_str(description)])
    ).lower()
    if not blob:
        return "unknown"
    if re.search(r"\bhybrid\b", blob):
        return "hybrid"
    if re.search(r"\b(on[\s-]?site|in[\s-]?office|office[\s-]?based)\b", blob):
        return "onsite"
    if re.search(r"\b(remote|work from home|wfh|distributed|anywhere)\b", blob):
        return "remote"
    return "unknown"


def infer_career_stage(
    title: str,
    description: Optional[str] = None,
    *,
    source_level: Optional[str] = None,
    employment_type: Optional[str] = None,
) -> str:
    return classify_job(
        title,
        description,
        source_level=source_level,
        employment_type=employment_type,
    ).career_stage


def apply_classification(
    job: NormalizedJob,
    *,
    source_level: Optional[str] = None,
) -> NormalizedJob:
    """Fill career_stage, years, junior_eligible, signals on a NormalizedJob."""
    result = classify_job(
        job.title,
        job.description_text,
        source_level=source_level,
        employment_type=job.employment_type,
    )
    job.career_stage = result.career_stage
    job.years_required_min = result.years_required_min
    job.junior_eligible = result.junior_eligible
    job.seniority_signals = result.signals
    if result.employment_type:
        job.employment_type = result.employment_type
    return job


def fingerprint(title: str, company: str, career_stage: str | None = None) -> str:
    t = _WS_RE.sub(" ", (title or "").strip().lower())
    c = _WS_RE.sub(" ", (company or "").strip().lower())
    stage = _WS_RE.sub(" ", (career_stage or "unknown").strip().lower())
    return f"{t}|{c}|{stage}"


def apply_url_is_usable(url: Optional[str]) -> bool:
    """Reject internal API hosts that should never be user-facing apply destinations."""
    if not (url or "").strip():
        return False
    parsed = urlparse(url.strip())
    host = (parsed.hostname or "").lower()
    if not host:
        return False
    # API surfaces that are not application pages
    if host in {
        "api.smartrecruiters.com",
        "boards-api.greenhouse.io",
        "api.lever.co",
        "api.ashbyhq.com",
    }:
        return False
    if host.startswith("api.") and "greenhouse" in host:
        return False
    return parsed.scheme in {"http", "https"}
