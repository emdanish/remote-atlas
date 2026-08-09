from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx

from app.collectors.base import BaseCollector
from app.collectors.tech_filter import looks_technical
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


class TeamtailorCollector(BaseCollector):
    """Public Teamtailor JSON Feed at `{slug}.teamtailor.com/jobs.json` (no auth)."""

    source = "teamtailor"

    def __init__(self, boards: list[dict], client: Optional[httpx.AsyncClient] = None):
        super().__init__(client=client)
        self.boards = boards

    async def _fetch_board(self, board: dict) -> list[NormalizedJob]:
        slug = board["ats_slug"]
        company_name = board["name"]
        company_id = board.get("id")
        career_page = board.get("career_page_url") or f"https://{slug}.teamtailor.com"
        website = board.get("website")
        cutoff = datetime.now(timezone.utc) - timedelta(days=get_settings().freshness_days)

        url = f"https://{slug}.teamtailor.com/jobs.json"
        try:
            resp = await self.client.get(url)
            if resp.status_code == 404:
                return []
            resp.raise_for_status()
        except httpx.HTTPError:
            return []

        data = resp.json()
        items = data.get("items") or []
        results: list[NormalizedJob] = []
        for item in items:
            title = (item.get("title") or "").strip()
            if not title or not looks_technical(title):
                continue
            posted = parse_datetime(item.get("date_published"))
            if posted is not None and posted < cutoff:
                continue
            html = item.get("content_html") or ""
            text = html_to_text(html) if html else None
            meta = item.get("_jobposting") or {}
            location = None
            if isinstance(meta, dict):
                loc = meta.get("jobLocation") or meta.get("location")
                if isinstance(loc, dict):
                    location = loc.get("address") or loc.get("name")
                elif isinstance(loc, str):
                    location = loc
            apply = normalize_url(item.get("url"))
            if not apply:
                continue
            enriched = enrich_job_fields(title, text, location)
            results.append(
                NormalizedJob(
                    source=self.source,
                    external_id=str(item.get("id") or apply)[:240],
                    title=title[:500],
                    company_name=company_name,
                    company_url=website,
                    career_page_url=career_page,
                    apply_url=apply,
                    description_text=text,
                    description_html=html or None,
                    location_raw=location,
                    workplace_type=infer_workplace_type(location, None, text),
                    employment_type=None,
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
