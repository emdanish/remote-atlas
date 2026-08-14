"""Cookie CSRF-ish origin check for mutating cookie-authenticated requests."""

from __future__ import annotations

from urllib.parse import urlparse


def origin_from_referer(referer: str | None) -> str:
    if not referer:
        return ""
    parsed = urlparse(referer)
    if parsed.scheme and parsed.netloc:
        return f"{parsed.scheme}://{parsed.netloc}".rstrip("/")
    return ""


def cookie_mutation_allowed(
    *,
    origin: str | None,
    referer: str | None,
    allowed: set[str],
) -> bool:
    """Require Origin, or Referer origin, to match CORS allowlist."""
    allowed_n = {v.rstrip("/") for v in allowed}
    check = (origin or "").rstrip("/") or origin_from_referer(referer)
    if not check:
        return False
    return check in allowed_n
