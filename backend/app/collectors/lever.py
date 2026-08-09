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


class LeverCollector(BaseCollector):
    source = "lever"

    def __init__(self, boards: list[dict], client: Optional[httpx.AsyncClient] = None):
        super().__init__(client=client)
        self.boards = boards

    async def _fetch_board(self, board: dict) -> list[NormalizedJob]:
        slug = board["ats_slug"]
        company_name = board["name"]
        company_id = board.get("id")
        career_page = board.get("career_page_url") or f"https://jobs.lever.co/{slug}"
        website = board.get("website")

        url = f"https://api.lever.co/v0/postings/{slug}"
        try:
            resp = await self.client.get(url, params={"mode": "json", "limit": "100"})
            if resp.status_code == 404:
                return []
            resp.raise_for_status()
        except httpx.HTTPError:
            return []

        data = resp.json()
        if not isinstance(data, list):
            return []

        results: list[NormalizedJob] = []
        for item in data:
            title = (item.get("text") or "").strip()
            if not title or not _looks_technical(title, None):
                continue

            categories = item.get("categories") or {}
            location = categories.get("location")
            workplace = item.get("workplaceType") or categories.get("commitment")
            description_parts = []
            for key in ("descriptionPlain", "description", "additionalPlain", "additional"):
                val = item.get(key)
                if val:
                    description_parts.append(val)
            # lists
            for list_key in ("lists",):
                for block in item.get(list_key) or []:
                    if isinstance(block, dict):
                        description_parts.append(block.get("text") or "")
                        description_parts.append(block.get("content") or "")

            html_desc = "\n".join(p for p in description_parts if p)
            text = html_to_text(html_desc) if "<" in html_desc else html_desc
            enriched = enrich_job_fields(title, text, location)
            posted = parse_datetime(item.get("createdAt"))
            cutoff = datetime.now(timezone.utc) - timedelta(days=get_settings().freshness_days)
            if posted is not None and posted < cutoff:
                continue

            results.append(
                NormalizedJob(
                    source=self.source,
                    external_id=f"{slug}:{item.get('id')}",
                    title=title,
                    company_name=company_name,
                    company_url=website,
                    career_page_url=career_page,
                    apply_url=normalize_url(item.get("applyUrl") or item.get("hostedUrl")),
                    description_text=text,
                    description_html=html_desc if "<" in html_desc else None,
                    location_raw=location,
                    workplace_type=infer_workplace_type(location, workplace, text),
                    employment_type=categories.get("commitment"),
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
