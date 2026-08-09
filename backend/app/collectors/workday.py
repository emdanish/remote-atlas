from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx

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


class WorkdayCollector(BaseCollector):
    """Collect published jobs from curated Workday public career sites.

    ``ats_slug`` is stored as ``host|tenant|site``. These values come from the
    checked-in company registry, so user-supplied hostnames never reach here.
    """

    source = "workday"

    def __init__(self, boards: list[dict], client: Optional[httpx.AsyncClient] = None):
        super().__init__(client=client)
        self.boards = boards

    @staticmethod
    def _parts(value: str) -> tuple[str, str, str] | None:
        parts = [part.strip() for part in value.split("|")]
        if len(parts) != 3 or not all(parts):
            return None
        host, tenant, site = parts
        if not host.endswith(".myworkdayjobs.com"):
            return None
        return host, tenant, site

    async def _fetch_board(self, board: dict) -> list[NormalizedJob]:
        parts = self._parts(board["ats_slug"])
        if not parts:
            return []
        host, tenant, site = parts
        base = f"https://{host}"
        api = f"{base}/wday/cxs/{tenant}/{site}"
        company_name = board["name"]
        company_id = board.get("id")
        website = board.get("website")
        career_page = board.get("career_page_url") or f"{base}/en-US/{site}"
        cutoff = datetime.now(timezone.utc) - timedelta(days=get_settings().freshness_days)

        postings: list[dict] = []
        offset = 0
        total = 1
        while offset < total and offset < 2000:
            try:
                response = await self.client.post(
                    f"{api}/jobs",
                    json={"appliedFacets": {}, "limit": 20, "offset": offset, "searchText": ""},
                )
                if response.status_code == 404:
                    return []
                response.raise_for_status()
            except httpx.HTTPError:
                return []
            payload = response.json() or {}
            batch = payload.get("jobPostings") or []
            total = min(int(payload.get("total") or 0), 2000)
            if not batch:
                break
            postings.extend(
                item
                for item in batch
                if (item.get("title") or "").strip()
                and looks_technical(item.get("title") or "")
            )
            offset += len(batch)

        sem = asyncio.Semaphore(10)

        async def load_detail(item: dict) -> dict | None:
            path = item.get("externalPath")
            if not path or not str(path).startswith("/job/"):
                return None
            async with sem:
                try:
                    response = await self.client.get(f"{api}{path}")
                    if response.status_code == 200:
                        return response.json() or None
                except httpx.HTTPError:
                    return None
            return None

        details = await asyncio.gather(*(load_detail(item) for item in postings))
        results: list[NormalizedJob] = []
        for summary, detail in zip(postings, details):
            info = (detail or {}).get("jobPostingInfo") or {}
            if not info or info.get("posted") is False or info.get("canApply") is False:
                continue
            title = (info.get("title") or summary.get("title") or "").strip()
            if not title:
                continue
            description_html = info.get("jobDescription")
            description = html_to_text(description_html)
            if not looks_like_software_role(title, description):
                continue
            location = info.get("location") or summary.get("locationsText")
            country = ((info.get("country") or {}).get("descriptor") or "").strip()
            if country and country.lower() not in (location or "").lower():
                location = ", ".join(part for part in (location, country) if part)
            posted = parse_datetime(info.get("startDate"))
            if posted is not None and posted < cutoff:
                continue
            external_path = summary.get("externalPath")
            apply_url = info.get("externalUrl")
            if not apply_url and external_path:
                apply_url = f"{base}/{site}{external_path}"
            apply_url = normalize_url(apply_url)
            if not apply_url:
                continue
            external_id = (
                info.get("jobReqId")
                or info.get("jobPostingId")
                or info.get("id")
                or external_path
            )
            enriched = enrich_job_fields(title, description, location)
            results.append(
                NormalizedJob(
                    source=self.source,
                    external_id=f"{tenant}:{site}:{external_id}",
                    title=title,
                    company_name=company_name,
                    company_url=website,
                    career_page_url=career_page,
                    apply_url=apply_url,
                    description_text=description or title,
                    description_html=description_html,
                    location_raw=location,
                    workplace_type=infer_workplace_type(location, None, description),
                    employment_type=info.get("timeType") or summary.get("timeType"),
                    career_stage=infer_career_stage(title, description),
                    skills=enriched["skills"],
                    tech_tags=enriched["tech_tags"],
                    posted_at=posted,
                    company_id=company_id,
                )
            )
        return results

    async def fetch(self) -> list[NormalizedJob]:
        sem = asyncio.Semaphore(min(8, get_settings().ingest_concurrency))

        async def run_one(board: dict) -> list[NormalizedJob]:
            async with sem:
                return await self._fetch_board(board)

        batches = await asyncio.gather(*(run_one(board) for board in self.boards), return_exceptions=True)
        results: list[NormalizedJob] = []
        for batch in batches:
            if not isinstance(batch, Exception):
                results.extend(batch)
        return results
