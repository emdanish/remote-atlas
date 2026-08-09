from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx

from app.collectors.base import BaseCollector
from app.collectors.tech_filter import looks_technical as _looks_technical
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


class BreezyCollector(BaseCollector):
    """Public Breezy HR JSON: `https://{slug}.breezy.hr/json` (no auth)."""

    source = "breezy"

    def __init__(self, boards: list[dict], client: Optional[httpx.AsyncClient] = None):
        super().__init__(client=client)
        self.boards = boards

    async def _fetch_board(self, board: dict) -> list[NormalizedJob]:
        slug = board["ats_slug"]
        company_name = board["name"]
        company_id = board.get("id")
        career_page = board.get("career_page_url") or f"https://{slug}.breezy.hr"
        website = board.get("website")
        cutoff = datetime.now(timezone.utc) - timedelta(days=get_settings().freshness_days)

        url = f"https://{slug}.breezy.hr/json"
        try:
            resp = await self.client.get(url)
            if resp.status_code != 200:
                return []
            data = resp.json()
        except httpx.HTTPError:
            return []
        if not isinstance(data, list):
            return []

        results: list[NormalizedJob] = []
        for item in data:
            title = (item.get("name") or item.get("title") or "").strip()
            if not title or not _looks_technical(title, item.get("department")):
                continue
            location = item.get("location")
            if isinstance(location, dict):
                location = location.get("name") or location.get("city")
            elif isinstance(location, list) and location:
                first = location[0]
                location = (
                    first.get("name") if isinstance(first, dict) else str(first)
                )
            if location is not None and not isinstance(location, str):
                location = str(location)
            desc = item.get("description") or ""
            text = html_to_text(desc) if isinstance(desc, str) and "<" in desc else (
                desc if isinstance(desc, str) else None
            )
            posted = parse_datetime(item.get("published_date") or item.get("created_date"))
            if posted is not None and posted < cutoff:
                continue
            apply = normalize_url(item.get("url") or item.get("friendly_id"))
            if apply and not apply.startswith("http"):
                apply = f"{career_page.rstrip('/')}/{apply.lstrip('/')}"
            if not apply:
                continue
            emp_raw = item.get("type")
            if isinstance(emp_raw, dict):
                employment = emp_raw.get("name") or emp_raw.get("id") or None
            else:
                employment = emp_raw if isinstance(emp_raw, str) else None
            workplace_hint = employment if isinstance(employment, str) else None
            enriched = enrich_job_fields(title, text, location)
            results.append(
                NormalizedJob(
                    source=self.source,
                    external_id=f"{slug}:{item.get('_id') or item.get('id') or apply}",
                    title=title,
                    company_name=company_name,
                    company_url=website,
                    career_page_url=career_page,
                    apply_url=apply,
                    description_text=text or None,
                    description_html=desc if isinstance(desc, str) and "<" in desc else None,
                    location_raw=location,
                    workplace_type=infer_workplace_type(location, workplace_hint, text),
                    employment_type=employment if isinstance(employment, str) else None,
                    career_stage=infer_career_stage(title, text),
                    skills=enriched["skills"],
                    tech_tags=enriched["tech_tags"],
                    posted_at=posted,
                    company_id=company_id,
                )
            )
        return results

    async def fetch(self) -> list[NormalizedJob]:
        import asyncio

        concurrency = get_settings().ingest_concurrency
        sem = asyncio.Semaphore(concurrency)

        async def run_one(board: dict) -> list[NormalizedJob]:
            async with sem:
                return await self._fetch_board(board)

        batches = await asyncio.gather(*(run_one(b) for b in self.boards), return_exceptions=True)
        results: list[NormalizedJob] = []
        for batch in batches:
            if isinstance(batch, Exception):
                logger = __import__("logging").getLogger("breezy")
                logger.warning("breezy board failed: %s", batch)
                continue
            results.extend(batch)
        return results
