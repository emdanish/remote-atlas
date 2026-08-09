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


class AshbyCollector(BaseCollector):
    source = "ashby"

    def __init__(self, boards: list[dict], client: Optional[httpx.AsyncClient] = None):
        super().__init__(client=client)
        self.boards = boards

    async def _fetch_board(self, board: dict) -> list[NormalizedJob]:
        slug = board["ats_slug"]
        company_name = board["name"]
        company_id = board.get("id")
        career_page = board.get("career_page_url") or f"https://jobs.ashbyhq.com/{slug}"
        website = board.get("website")

        url = f"https://api.ashbyhq.com/posting-api/job-board/{slug}"
        try:
            resp = await self.client.get(url, params={"includeCompensation": "true"})
            if resp.status_code == 404:
                return []
            resp.raise_for_status()
        except httpx.HTTPError:
            return []

        data = resp.json()
        jobs_raw = data.get("jobs") or []
        results: list[NormalizedJob] = []

        for item in jobs_raw:
            if item.get("isListed") is False:
                continue
            title = (item.get("title") or "").strip()
            if not title or not _looks_technical(title, None):
                continue

            location = item.get("location")
            workplace = item.get("workplaceType")
            if item.get("isRemote"):
                workplace = workplace or "Remote"
            description = item.get("descriptionPlain") or item.get("descriptionHtml") or ""
            text = (
                description
                if item.get("descriptionPlain")
                else html_to_text(description)
            )
            enriched = enrich_job_fields(title, text, location)
            posted = parse_datetime(item.get("publishedAt"))
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
                    apply_url=normalize_url(item.get("applyUrl") or item.get("jobUrl")),
                    description_text=text,
                    description_html=item.get("descriptionHtml"),
                    location_raw=location,
                    workplace_type=infer_workplace_type(location, workplace, text),
                    employment_type=item.get("employmentType"),
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
