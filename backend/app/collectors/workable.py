from __future__ import annotations

import asyncio
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


class WorkableCollector(BaseCollector):
    """Public Workable widget JSON — best-effort, per-account slug."""

    source = "workable"

    def __init__(self, boards: list[dict], client: Optional[httpx.AsyncClient] = None):
        super().__init__(client=client)
        self.boards = boards

    async def _fetch_board(self, board: dict) -> list[NormalizedJob]:
        slug = board["ats_slug"]
        company_name = board["name"]
        company_id = board.get("id")
        career_page = board.get("career_page_url") or f"https://apply.workable.com/{slug}/"
        website = board.get("website")

        url = f"https://www.workable.com/api/accounts/{slug}"
        try:
            resp = await self.client.get(url, params={"details": "true"})
            if resp.status_code == 404:
                return []
            resp.raise_for_status()
        except httpx.HTTPError:
            return []

        data = resp.json()
        jobs_raw = data.get("jobs") or []
        results: list[NormalizedJob] = []
        cutoff = datetime.now(timezone.utc) - timedelta(days=get_settings().freshness_days)

        for item in jobs_raw:
            title = (item.get("title") or "").strip()
            if not title or not _looks_technical(title, None):
                continue
            location = None
            if isinstance(item.get("location"), dict):
                location = item["location"].get("city") or item["location"].get("country")
            elif item.get("locations"):
                locs = item["locations"]
                if locs and isinstance(locs[0], dict):
                    location = locs[0].get("city") or locs[0].get("country")
            description = item.get("full_description") or item.get("description") or ""
            text = html_to_text(description) if "<" in str(description) else description
            enriched = enrich_job_fields(title, text, location)
            posted = parse_datetime(item.get("published_on") or item.get("created_at"))
            if posted is not None and posted < cutoff:
                continue

            results.append(
                NormalizedJob(
                    source=self.source,
                    external_id=f"{slug}:{item.get('shortcode') or item.get('id')}",
                    title=title,
                    company_name=company_name,
                    company_url=website,
                    career_page_url=career_page,
                    apply_url=normalize_url(item.get("url") or item.get("shortlink")),
                    description_text=text,
                    description_html=description if "<" in str(description) else None,
                    location_raw=location,
                    workplace_type=infer_workplace_type(
                        location, "remote" if item.get("remote") else None, text
                    ),
                    employment_type=item.get("employment_type"),
                    career_stage=infer_career_stage(title, text),
                    skills=enriched["skills"],
                    tech_tags=enriched["tech_tags"],
                    posted_at=posted,
                    company_id=company_id,
                )
            )
        return results

    async def fetch(self) -> list[NormalizedJob]:
        concurrency = get_settings().ingest_concurrency
        sem = asyncio.Semaphore(concurrency)

        async def run_one(board: dict) -> list[NormalizedJob]:
            async with sem:
                return await self._fetch_board(board)

        batches = await asyncio.gather(*(run_one(b) for b in self.boards), return_exceptions=True)
        results: list[NormalizedJob] = []
        for batch in batches:
            if isinstance(batch, Exception):
                continue
            results.extend(batch)
        return results
