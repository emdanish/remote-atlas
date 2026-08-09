from __future__ import annotations

import asyncio
import re
import unicodedata
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


def _public_posting_url(company_slug: str, posting_id: str, title: str) -> str:
    """Build the public SmartRecruiters job page, never its JSON API endpoint."""
    ascii_title = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode()
    title_slug = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_title).strip("-").lower()
    suffix = f"-{title_slug}" if title_slug else ""
    return f"https://jobs.smartrecruiters.com/{company_slug}/{posting_id}{suffix}?oga=true"


class SmartRecruitersCollector(BaseCollector):
    source = "smartrecruiters"

    def __init__(self, boards: list[dict], client: Optional[httpx.AsyncClient] = None):
        super().__init__(client=client)
        self.boards = boards

    async def _fetch_board(self, board: dict) -> list[NormalizedJob]:
        slug = board["ats_slug"]
        company_name = board["name"]
        company_id = board.get("id")
        career_page = board.get("career_page_url") or f"https://jobs.smartrecruiters.com/{slug}"
        website = board.get("website")
        cutoff = datetime.now(timezone.utc) - timedelta(days=get_settings().freshness_days)

        results: list[NormalizedJob] = []
        offset = 0
        limit = 100
        while offset < 2000:
            url = f"https://api.smartrecruiters.com/v1/companies/{slug}/postings"
            try:
                resp = await self.client.get(url, params={"limit": limit, "offset": offset})
                if resp.status_code == 404:
                    return []
                resp.raise_for_status()
            except httpx.HTTPError:
                return results

            data = resp.json()
            jobs_raw = data.get("content") or []
            if not jobs_raw:
                break

            candidates = []
            for item in jobs_raw:
                title = (item.get("name") or item.get("title") or "").strip()
                if not title or not looks_technical(title):
                    continue

                posted = parse_datetime(item.get("releasedDate") or item.get("createdOn"))
                if posted is not None and posted < cutoff:
                    continue
                candidates.append(item)

            detail_sem = asyncio.Semaphore(6)

            async def load_detail(item: dict) -> dict:
                ref = item.get("id") or item.get("uuid")
                if not ref:
                    return item
                async with detail_sem:
                    try:
                        detail = await self.client.get(f"{url}/{ref}")
                        if detail.status_code == 200:
                            return detail.json() or item
                    except httpx.HTTPError:
                        pass
                return item

            detailed = await asyncio.gather(*(load_detail(item) for item in candidates))

            for item in detailed:
                title = (item.get("name") or item.get("title") or "").strip()

                location_obj = item.get("location") or {}
                if isinstance(location_obj, dict):
                    city = location_obj.get("city") or ""
                    region = location_obj.get("region") or ""
                    country = location_obj.get("country") or ""
                    remote_flag = location_obj.get("remote")
                    location = ", ".join(p for p in (city, region, country) if p)
                    if remote_flag:
                        location = (location + " · Remote").strip(" ·")
                else:
                    location = str(location_obj) if location_obj else None

                posted = parse_datetime(item.get("releasedDate") or item.get("createdOn"))

                # List endpoint often omits full description — still index metadata
                description = item.get("jobAd", {}).get("sections", {}) if isinstance(item.get("jobAd"), dict) else ""
                text = ""
                if isinstance(description, dict):
                    parts = []
                    for section in description.values():
                        if isinstance(section, dict):
                            parts.append(section.get("text") or "")
                    text = html_to_text(" ".join(parts)) or ""
                if not looks_like_software_role(title, text):
                    continue

                ref = item.get("id") or item.get("uuid") or item.get("refNumber")
                apply = item.get("applyUrl") or item.get("postingUrl")
                if apply and "api.smartrecruiters.com/" in str(apply).lower():
                    apply = None
                if not apply and ref:
                    apply = _public_posting_url(slug, str(ref), title)

                enriched = enrich_job_fields(title, text, location)
                results.append(
                    NormalizedJob(
                        source=self.source,
                        external_id=f"{slug}:{ref}",
                        title=title,
                        company_name=company_name,
                        company_url=website,
                        career_page_url=career_page,
                        apply_url=normalize_url(apply),
                        description_text=text or title,
                        description_html=None,
                        location_raw=location,
                        workplace_type=infer_workplace_type(location, None, text),
                        employment_type=item.get("typeOfEmployment", {}).get("label")
                        if isinstance(item.get("typeOfEmployment"), dict)
                        else None,
                        career_stage=infer_career_stage(title, text),
                        skills=enriched["skills"],
                        tech_tags=enriched["tech_tags"],
                        posted_at=posted,
                        company_id=company_id,
                    )
                )

            total = data.get("totalFound") or data.get("total") or 0
            offset += limit
            if offset >= total or len(jobs_raw) < limit:
                break

        return results

    async def fetch(self) -> list[NormalizedJob]:
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
