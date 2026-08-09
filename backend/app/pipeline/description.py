"""Canonical job description normalization.

Collectors may deliver:
  - real HTML
  - entity-encoded HTML (&lt;p&gt;...)
  - plain text
  - hybrid (Markdown links + HTML)
  - platform editor garbage (Google Sheets data-* attrs, c-link classes, inline styles)

Remote Atlas stores:
  description_html → safe semantic HTML (or None)
  description_text → plain readable text

Frontend still sanitizes on render as defense-in-depth.
This module must NOT invent content — only normalize formatting.
"""

from __future__ import annotations

import html
import re
from typing import Optional
from urllib.parse import urlparse

from bs4 import BeautifulSoup, Comment, Tag


_WS_RE = re.compile(r"\s+")
_MD_LINK_RE = re.compile(
    r"\[([^\]]+)\]\((https?://[^\s)]+|mailto:[^\s)]+)\)",
    re.IGNORECASE,
)
# Outer entity-encoded markup (not normal text entities like &amp;)
_ENCODED_TAG_RE = re.compile(
    r"&lt;\s*/?\s*(?:p|div|br|ul|ol|li|h[1-6]|span|strong|em|b|i|a|section|article|table|tr|td|th)(?:\s|&gt;|/)",
    re.IGNORECASE,
)
_ALLOWED_TAGS = frozenset(
    {
        "p",
        "br",
        "hr",
        "h2",
        "h3",
        "h4",
        "strong",
        "b",
        "em",
        "i",
        "u",
        "ul",
        "ol",
        "li",
        "blockquote",
        "a",
        "span",
        "div",
        "section",
        "pre",
        "code",
    }
)
_DROP_TAGS = frozenset(
    {
        "script",
        "style",
        "iframe",
        "object",
        "embed",
        "form",
        "input",
        "button",
        "svg",
        "noscript",
        "meta",
        "link",
        "head",
        "title",
    }
)
_UNWRAP_TAGS = frozenset(
    {
        "font",
        "center",
        "article",
        "main",
        "body",
        "html",
        "table",
        "tbody",
        "thead",
        "tfoot",
        "tr",
        "td",
        "th",
        "colgroup",
        "col",
    }
)
# Editor / ATS presentation junk attributes
_DROP_ATTR_PREFIXES = ("data-sheets", "data-stringify", "data-sk", "data-pm", "data-")
_ALLOW_ATTRS = {
    "a": frozenset({"href", "title", "name"}),
    "code": frozenset({"class"}),
    "pre": frozenset({"class"}),
}


def looks_like_encoded_html(value: str) -> bool:
    if not value:
        return False
    if "<" in value and _TAG_OPEN_RE.search(value):
        # already real tags — not outer-encoded
        return False
    return bool(_ENCODED_TAG_RE.search(value))


_TAG_OPEN_RE = re.compile(r"<\s*/?\s*[a-zA-Z][a-zA-Z0-9]*\b")


def looks_like_html(value: str) -> bool:
    if not value:
        return False
    if looks_like_encoded_html(value):
        return True
    return bool(_TAG_OPEN_RE.search(value))


def _decode_entity_html(value: str, max_rounds: int = 3) -> str:
    """Decode entity-encoded markup carefully (stop before over-unescaping)."""
    out = value
    for _ in range(max_rounds):
        if not looks_like_encoded_html(out):
            break
        nxt = html.unescape(out)
        if nxt == out:
            break
        out = nxt
    return out


def _markdown_links_to_html(text: str) -> str:
    def repl(m: re.Match[str]) -> str:
        label = html.escape(m.group(1).strip() or m.group(2))
        href = m.group(2).strip()
        if not _safe_href(href):
            return label
        return f'<a href="{html.escape(href, quote=True)}">{label}</a>'

    return _MD_LINK_RE.sub(repl, text)


def _safe_href(href: str) -> bool:
    if not href or not href.strip():
        return False
    h = href.strip()
    low = h.lower()
    if low.startswith(("javascript:", "data:", "vbscript:")):
        return False
    if low.startswith(("http://", "https://", "mailto:")):
        return True
    # Relative paths — rare in job posts; allow path-like only
    if h.startswith("/") and not h.startswith("//"):
        return True
    return False


def _absolute_href(href: str) -> Optional[str]:
    h = (href or "").strip()
    if not h or not _safe_href(h):
        return None
    # Normalize protocol-relative
    if h.startswith("//"):
        h = "https:" + h
    parsed = urlparse(h)
    if parsed.scheme and parsed.scheme.lower() not in {"http", "https", "mailto"}:
        return None
    return h


def _promote_heading_tags(soup: BeautifulSoup) -> None:
    for tag in soup.find_all(["h1", "h5", "h6"]):
        tag.name = "h2" if tag.name == "h1" else "h3"


def _strip_comments(soup: BeautifulSoup) -> None:
    for c in soup.find_all(string=lambda t: isinstance(t, Comment)):
        c.extract()


def _clean_tree(soup: BeautifulSoup) -> None:
    _strip_comments(soup)
    _promote_heading_tags(soup)

    for tag in list(soup.find_all(True)):
        if not isinstance(tag, Tag):
            continue
        name = (tag.name or "").lower()
        if name in _DROP_TAGS:
            tag.decompose()
            continue
        if name in _UNWRAP_TAGS:
            tag.unwrap()
            continue
        if name not in _ALLOWED_TAGS:
            # Keep text, drop unknown wrapper
            tag.unwrap()
            continue

        # Attribute allowlist
        allowed = _ALLOW_ATTRS.get(name, frozenset())
        for attr in list(tag.attrs.keys()):
            al = attr.lower()
            if any(al.startswith(p) for p in _DROP_ATTR_PREFIXES):
                del tag.attrs[attr]
                continue
            if al in {"style", "class", "id", "onclick", "onerror", "onload"} and name not in {
                "code",
                "pre",
            }:
                if al == "class" and name in {"code", "pre"}:
                    continue
                del tag.attrs[attr]
                continue
            if attr not in allowed and al not in allowed:
                del tag.attrs[attr]

        if name == "a":
            href = tag.attrs.get("href")
            safe = _absolute_href(str(href) if href else "")
            if not safe:
                tag.unwrap()
            else:
                tag.attrs["href"] = safe
                tag.attrs["rel"] = "noopener noreferrer nofollow"
                tag.attrs["target"] = "_blank"


def _collapse_duplicate_adjacent_blocks(soup: BeautifulSoup) -> None:
    """Remove adjacent block siblings with identical normalized text (source paste dupes)."""
    body = soup.body if soup.body else soup
    children = [c for c in list(body.children) if isinstance(c, Tag)]
    prev_norm: Optional[str] = None
    for child in children:
        text = _WS_RE.sub(" ", child.get_text(" ", strip=True)).lower()
        if not text:
            continue
        if prev_norm and text == prev_norm and len(text) > 80:
            child.decompose()
            continue
        prev_norm = text


def _wrap_plain_paragraphs(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not text:
        return ""
    # Convert markdown links first
    text = _markdown_links_to_html(text)
    parts = re.split(r"\n{2,}", text)
    blocks: list[str] = []
    for part in parts:
        p = part.strip()
        if not p:
            continue
        # Keep list-like lines as <ul>
        lines = [ln.strip() for ln in p.split("\n") if ln.strip()]
        if len(lines) >= 2 and all(re.match(r"^([-*•]|\d+\.)\s+", ln) for ln in lines):
            items = []
            for ln in lines:
                item = re.sub(r"^([-*•]|\d+\.)\s+", "", ln)
                items.append(f"<li>{item}</li>")
            blocks.append(f"<ul>{''.join(items)}</ul>")
        else:
            # Single newlines → <br>
            inner = "<br/>".join(lines)
            blocks.append(f"<p>{inner}</p>")
    return "".join(blocks)


def html_to_text(value: Optional[str]) -> Optional[str]:
    """Extract plain text (also used by collectors/search)."""
    if not value:
        return None
    decoded = html.unescape(value)
    soup = BeautifulSoup(decoded, "lxml")
    text = soup.get_text(separator=" ", strip=True)
    text = _WS_RE.sub(" ", text).strip()
    return text or None


def canonicalize_description(
    html_value: Optional[str] = None,
    text_value: Optional[str] = None,
) -> tuple[Optional[str], Optional[str]]:
    """Return (description_html, description_text) as a Remote Atlas canonical pair.

    Prefer HTML field when present; fall back to text. Never concatenates both.
    """
    raw_html = (html_value or "").strip() or None
    raw_text = (text_value or "").strip() or None

    source = raw_html or raw_text
    if not source:
        return None, None

    # Prefer structured HTML path
    if raw_html and looks_like_html(raw_html):
        body = _decode_entity_html(raw_html)
        body = _markdown_links_to_html(body)
        soup = BeautifulSoup(body, "lxml")
        _clean_tree(soup)
        _collapse_duplicate_adjacent_blocks(soup)
        root = soup.body if soup.body else soup
        cleaned = root.decode_contents() if hasattr(root, "decode_contents") else str(root)
        cleaned = cleaned.strip()
        # Drop empty wrappers
        if cleaned and not BeautifulSoup(cleaned, "lxml").get_text(strip=True):
            cleaned = ""
        text = html_to_text(cleaned) or html_to_text(raw_html) or raw_text
        return (cleaned or None), (text or None)

    # Plain text (or HTML-looking text with no real structure)
    plain_source = raw_text or raw_html or ""
    # If plain looks entity-encoded HTML, re-enter HTML path once
    if looks_like_encoded_html(plain_source) or (looks_like_html(plain_source) and "<" in plain_source):
        return canonicalize_description(html_value=plain_source, text_value=None)

    # Markdown links + paragraphs
    as_html = _wrap_plain_paragraphs(plain_source)
    text = html_to_text(as_html) or _WS_RE.sub(" ", plain_source).strip() or None
    return (as_html or None), text


def normalize_job_description_fields(
    description_html: Optional[str],
    description_text: Optional[str],
) -> tuple[Optional[str], Optional[str]]:
    """Public entry used by upsert/backfill."""
    html_out, text_out = canonicalize_description(description_html, description_text)
    # Cap extreme sizes (DB safety — ~250KB HTML / ~120KB text)
    if html_out and len(html_out) > 250_000:
        html_out = html_out[:250_000]
    if text_out and len(text_out) > 120_000:
        text_out = text_out[:120_000]
    return html_out, text_out
