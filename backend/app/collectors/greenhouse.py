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


class GreenhouseCollector(BaseCollector):
    """Two-phase Greenhouse ingest for quality + speed.

    1) List jobs without HTML (fast).
    2) Keep technical roles only.
    3) Fetch full descriptions only for those roles via per-job detail API
       (or one content=true pass when the board is small).
    """

    source = "greenhouse"

    def __init__(
        self,
        boards: list[dict],
        client: Optional[httpx.AsyncClient] = None,
    ):
        super().__init__(client=client)
        self.boards = boards

    async def _fetch_board(self, board: dict) -> list[NormalizedJob]:
        slug = board["ats_slug"]
        company_name = board["name"]
        company_id = board.get("id")
        career_page = board.get("career_page_url") or f"https://boards.greenhouse.io/{slug}"
        website = board.get("website")
        cutoff = datetime.now(timezone.utc) - timedelta(days=get_settings().freshness_days)

        url = f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"
        try:
            resp = await self.client.get(url)
            if resp.status_code == 404:
                return []
            resp.raise_for_status()
        except httpx.HTTPError:
            return []

        jobs_raw = (resp.json() or {}).get("jobs") or []
        tech = [
            item
            for item in jobs_raw
            if (item.get("title") or "").strip()
            and _looks_technical(item.get("title") or "", item.get("departments"))
        ]
        if not tech:
            return []

        # Small boards: one content=true call is cheaper than N detail calls
        if len(jobs_raw) <= 60:
            try:
                full = await self.client.get(url, params={"content": "true"})
                if full.status_code == 200:
                    by_id = {
                        j.get("id"): j
                        for j in ((full.json() or {}).get("jobs") or [])
                        if j.get("id") is not None
                    }
                    tech = [by_id.get(j.get("id"), j) for j in tech]
            except httpx.HTTPError:
                pass
        else:
            # Large boards: detail-fetch only tech roles (parallel, capped)
            sem = asyncio.Semaphore(10)
            max_detail = 200

            async def load_detail(item: dict) -> dict:
                job_id = item.get("id")
                if job_id is None:
                    return item
                async with sem:
                    try:
                        r = await self.client.get(f"{url}/{job_id}")
                        if r.status_code == 200:
                            return r.json()
                    except httpx.HTTPError:
                        return item
                return item

            detailed = await asyncio.gather(*(load_detail(j) for j in tech[:max_detail]))
            tech = list(detailed) + tech[max_detail:]

        results: list[NormalizedJob] = []
        for item in tech:
            title = (item.get("title") or "").strip()
            location = (
                (item.get("location") or {}).get("name")
                if isinstance(item.get("location"), dict)
                else item.get("location")
            )
            content = item.get("content")
            text = html_to_text(content) if content else None
            enriched = enrich_job_fields(title, text, location)
            posted = parse_datetime(item.get("first_published") or item.get("updated_at"))
            # Never null stale dates — that makes old jobs look fresh via first_seen_at
            if posted is not None and posted < cutoff:
                continue

            apply = normalize_url(item.get("absolute_url"))
            if not apply:
                continue

            results.append(
                NormalizedJob(
                    source=self.source,
                    external_id=f"{slug}:{item.get('id')}",
                    title=title,
                    company_name=company_name,
                    company_url=website,
                    career_page_url=career_page,
                    apply_url=apply,
                    description_text=text,
                    description_html=content,
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
        # Lower board concurrency — each board may fan out detail requests
        concurrency = min(8, get_settings().ingest_concurrency)
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
