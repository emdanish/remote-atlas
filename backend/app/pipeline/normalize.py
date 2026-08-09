from __future__ import annotations

import html
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from bs4 import BeautifulSoup

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
    skills: list[str] = field(default_factory=list)
    tech_tags: list[str] = field(default_factory=list)
    posted_at: Optional[datetime] = None
    company_id: Optional[int] = None


_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def html_to_text(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    decoded = html.unescape(value)
    soup = BeautifulSoup(decoded, "lxml")
    text = soup.get_text(separator=" ", strip=True)
    text = _WS_RE.sub(" ", text).strip()
    return text or None


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


def infer_career_stage(title: str, description: Optional[str] = None) -> str:
    # Prefer title signal; avoid scanning huge descriptions for noisy words like "associate".
    title_l = title.lower()
    blob = f"{title} {(description or '')[:800]}".lower()

    if re.search(r"\b(intern|internship|trainee)\b", title_l):
        return "internship"
    if re.search(r"\b(staff|principal|distinguished|fellow)\b", title_l):
        return "senior"
    if re.search(r"\b(senior|sr\.?|lead|manager|director|head of)\b", title_l):
        return "senior"
    if re.search(
        r"\b(new grad|new graduate|university grad|campus hire|entry[\s-]?level|"
        r"junior|fresher|fresh graduate|associate (software|engineer|developer))\b",
        title_l,
    ):
        return "junior"
    if re.search(r"\b(mid[\s-]?level|intermediate)\b", title_l):
        return "mid"
    # Fallback: internship keywords anywhere in short blob
    if re.search(r"\b(intern|internship)\b", blob):
        return "internship"
    return "unknown"


def fingerprint(title: str, company: str) -> str:
    t = _WS_RE.sub(" ", (title or "").strip().lower())
    c = _WS_RE.sub(" ", (company or "").strip().lower())
    return f"{t}|{c}"


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
