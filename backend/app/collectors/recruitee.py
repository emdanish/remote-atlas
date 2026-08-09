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


class RecruiteeCollector(BaseCollector):
    source = "recruitee"

    def __init__(self, boards: list[dict], client: Optional[httpx.AsyncClient] = None):
        super().__init__(client=client)
        self.boards = boards

    async def _fetch_board(self, board: dict) -> list[NormalizedJob]:
        slug = board["ats_slug"]
        company_name = board["name"]
        company_id = board.get("id")
        career_page = board.get("career_page_url") or f"https://{slug}.recruitee.com"
        website = board.get("website")
        cutoff = datetime.now(timezone.utc) - timedelta(days=get_settings().freshness_days)

        url = f"https://{slug}.recruitee.com/api/offers/"
        try:
            resp = await self.client.get(url)
            if resp.status_code == 404:
                return []
            resp.raise_for_status()
        except httpx.HTTPError:
            return []

        data = resp.json()
        jobs_raw = data.get("offers") or []
        results: list[NormalizedJob] = []

        for item in jobs_raw:
            if item.get("status") and str(item.get("status")).lower() not in {"published", "open", ""}:
                # Recruitee usually only returns published offers
                pass
            title = (item.get("title") or "").strip()
            if not title or not looks_technical(title):
                continue

            location = item.get("location") or item.get("city")
            remote = item.get("remote") or item.get("workplace_type")
            description = item.get("description") or item.get("description_html") or ""
            text = html_to_text(description) if "<" in str(description) else str(description or "")
            enriched = enrich_job_fields(title, text, location)

            posted = parse_datetime(item.get("published_at") or item.get("created_at"))
            if posted is not None and posted < cutoff:
                continue

            apply = item.get("careers_url") or item.get("url")
            if not apply and item.get("slug"):
                apply = f"https://{slug}.recruitee.com/o/{item.get('slug')}"

            results.append(
                NormalizedJob(
                    source=self.source,
                    external_id=f"{slug}:{item.get('id') or item.get('slug')}",
                    title=title,
                    company_name=company_name,
                    company_url=website,
                    career_page_url=career_page,
                    apply_url=normalize_url(apply),
                    description_text=text,
                    description_html=description if "<" in str(description) else None,
                    location_raw=location,
                    workplace_type=infer_workplace_type(
                        location, "remote" if remote else None, text
                    ),
                    employment_type=item.get("employment_type") or item.get("contract_type"),
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
