"""We Work Remotely public RSS feed — programming/dev categories."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

from app.collectors.base import BaseCollector
from app.collectors.tech_filter import looks_like_software_role, looks_technical
from app.config import get_settings
from app.pipeline.enrich import enrich_job_fields
from app.pipeline.normalize import (
    NormalizedJob,
    html_to_text,
    infer_career_stage,
    infer_workplace_type,
    normalize_url,
    parse_datetime,
)

# Prefer programming-focused category feeds; fall back to main remote-jobs feed
WWR_FEEDS = (
    "https://weworkremotely.com/categories/remote-programming-jobs.rss",
    "https://weworkremotely.com/categories/remote-devops-sysadmin-jobs.rss",
    "https://weworkremotely.com/categories/remote-full-stack-programming-jobs.rss",
    "https://weworkremotely.com/categories/remote-front-end-programming-jobs.rss",
    "https://weworkremotely.com/categories/remote-back-end-programming-jobs.rss",
)

_TITLE_SPLIT = re.compile(r"\s*:\s*", re.U)


def parse_wwr_title(title: str) -> tuple[str, str]:
    """WWR titles are usually 'Company: Role'."""
    text = (title or "").strip()
    if not text:
        return "", ""
    parts = _TITLE_SPLIT.split(text, maxsplit=1)
    if len(parts) == 2 and parts[0].strip() and parts[1].strip():
        return parts[0].strip(), parts[1].strip()
    return "Unknown", text


def parse_rss_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = parsedate_to_datetime(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except (TypeError, ValueError, IndexError):
        return parse_datetime(value)


class WeWorkRemotelyCollector(BaseCollector):
    source = "weworkremotely"

    async def fetch(self) -> list[NormalizedJob]:
        cutoff = datetime.now(timezone.utc) - timedelta(days=get_settings().freshness_days)
        seen: set[str] = set()
        results: list[NormalizedJob] = []

        for feed_url in WWR_FEEDS:
            try:
                resp = await self.client.get(
                    feed_url,
                    headers={"Accept": "application/rss+xml, application/xml, text/xml, */*"},
                )
                if resp.status_code != 200:
                    continue
                root = ET.fromstring(resp.text)
            except Exception:  # noqa: BLE001
                continue

            channel = root.find("channel")
            items = channel.findall("item") if channel is not None else root.findall(".//item")
            for item in items:
                link = (item.findtext("link") or "").strip()
                guid = (item.findtext("guid") or link or "").strip()
                title_raw = (item.findtext("title") or "").strip()
                if not link or not title_raw:
                    continue
                key = guid or link
                if key in seen:
                    continue
                seen.add(key)

                company, title = parse_wwr_title(title_raw)
                desc_html = item.findtext("description")
                text = html_to_text(desc_html)
                if not looks_technical(title) and not looks_like_software_role(title, text):
                    if not looks_technical(title_raw):
                        continue

                posted = parse_rss_date(item.findtext("pubDate"))
                if posted is not None and posted < cutoff:
                    continue
                location = "Remote"
                # Nonstandard region tags if present
                for child in list(item):
                    tag = child.tag.split("}")[-1].lower() if child.tag else ""
                    if tag in {"region", "country", "location"} and (child.text or "").strip():
                        location = child.text.strip()

                apply_url = normalize_url(link)
                enriched = enrich_job_fields(title, text, location)
                results.append(
                    NormalizedJob(
                        source=self.source,
                        external_id=key[:240],
                        title=title,
                        company_name=company,
                        career_page_url=apply_url,
                        apply_url=apply_url,
                        description_text=text,
                        description_html=desc_html,
                        location_raw=location,
                        workplace_type=infer_workplace_type(location, "remote", text),
                        career_stage=infer_career_stage(title, text),
                        skills=enriched["skills"],
                        tech_tags=enriched["tech_tags"],
                        posted_at=posted,
                    )
                )
        return results
