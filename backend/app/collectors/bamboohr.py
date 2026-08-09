"""BambooHR public careers API — list + optional per-job detail."""

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


class BambooHRCollector(BaseCollector):
    source = "bamboohr"

    def __init__(
        self,
        boards: list[dict],
        client: Optional[httpx.AsyncClient] = None,
        *,
        detail_concurrency: int = 8,
    ):
        super().__init__(client=client)
        self.boards = boards
        self.detail_concurrency = detail_concurrency

    async def _list_jobs(self, slug: str) -> list[dict]:
        url = f"https://{slug}.bamboohr.com/careers/list"
        try:
            resp = await self.client.get(url)
            if resp.status_code in {301, 302, 303, 307, 308, 404}:
                return []
            # Private/auth boards return HTML login
            ctype = (resp.headers.get("content-type") or "").lower()
            if "json" not in ctype:
                text = (resp.text or "")[:80].lstrip()
                if text.startswith("<") or "login" in text.lower():
                    return []
            if resp.status_code != 200:
                return []
            data = resp.json()
            return list((data or {}).get("result") or [])
        except (httpx.HTTPError, ValueError):
            return []

    async def _detail(self, slug: str, job_id: str) -> dict | None:
        url = f"https://{slug}.bamboohr.com/careers/{job_id}/detail"
        try:
            resp = await self.client.get(url)
            if resp.status_code != 200:
                return None
            ctype = (resp.headers.get("content-type") or "").lower()
            if "json" not in ctype:
                return None
            return resp.json() or None
        except (httpx.HTTPError, ValueError):
            return None

    def _location_blob(self, item: dict) -> str:
        parts: list[str] = []
        loc = item.get("location") or item.get("atsLocation") or {}
        if isinstance(loc, dict):
            for key in ("city", "state", "province", "country"):
                v = loc.get(key)
                if v:
                    parts.append(str(v))
        elif isinstance(loc, str) and loc.strip():
            parts.append(loc.strip())
        if item.get("isRemote") is True:
            parts.append("Remote")
        elif str(item.get("locationType") or "") in {"2", "3"}:  # remote-ish codes
            parts.append("Remote")
        return ", ".join(parts) if parts else "Remote" if item.get("isRemote") else ""

    async def _fetch_board(self, board: dict) -> list[NormalizedJob]:
        slug = board["ats_slug"]
        company_name = board["name"]
        company_id = board.get("id")
        career_page = board.get("career_page_url") or f"https://{slug}.bamboohr.com/careers"
        website = board.get("website")
        cutoff = datetime.now(timezone.utc) - timedelta(days=get_settings().freshness_days)

        raw = await self._list_jobs(slug)
        if not raw:
            return []

        tech_items: list[dict] = []
        for item in raw:
            title = (item.get("jobOpeningName") or item.get("jobTitle") or "").strip()
            if not title:
                continue
            if not looks_technical(title) and not looks_like_software_role(title, None):
                continue
            tech_items.append(item)

        if not tech_items:
            return []

        sem = asyncio.Semaphore(self.detail_concurrency)
        results: list[NormalizedJob] = []

        async def one(item: dict) -> NormalizedJob | None:
            job_id = str(item.get("id") or "").strip()
            if not job_id:
                return None
            title = (item.get("jobOpeningName") or item.get("jobTitle") or "").strip()
            async with sem:
                detail = await self._detail(slug, job_id)
            desc_html = None
            posted = None
            location = self._location_blob(item)
            employment = item.get("employmentStatusLabel") or item.get("employmentType")
            if isinstance(employment, str):
                employment = employment[:60]
            else:
                employment = None
            if detail:
                # BambooHR detail shapes vary; try common keys
                job_opening = detail.get("jobOpening") or detail
                if isinstance(job_opening, dict):
                    title = (job_opening.get("jobOpeningName") or title).strip()
                    desc_html = (
                        job_opening.get("description")
                        or job_opening.get("jobDescription")
                        or job_opening.get("descriptionHtml")
                    )
                    posted = parse_datetime(
                        job_opening.get("datePosted")
                        or job_opening.get("postedDate")
                        or job_opening.get("createdDate")
                    )
                    if not location:
                        location = self._location_blob(job_opening)
            # Never invent posted_at; drop stale when known
            if posted is not None and posted < cutoff:
                return None
            text = html_to_text(desc_html) if desc_html else None
            apply_url = normalize_url(f"https://{slug}.bamboohr.com/careers/{job_id}")
            location_raw = location or None
            workplace = infer_workplace_type(location_raw, None, text)
            if item.get("isRemote") is True:
                workplace = "remote"
            enriched = enrich_job_fields(title, text, location_raw)
            return NormalizedJob(
                source=self.source,
                external_id=f"{slug}:{job_id}",
                title=title,
                company_name=company_name,
                company_url=normalize_url(website),
                career_page_url=normalize_url(career_page),
                apply_url=apply_url,
                description_text=text,
                description_html=desc_html if isinstance(desc_html, str) else None,
                location_raw=location_raw,
                workplace_type=workplace,
                employment_type=employment,
                career_stage=infer_career_stage(title, text),
                skills=enriched["skills"],
                tech_tags=enriched["tech_tags"],
                posted_at=posted,
                company_id=company_id,
            )

        gathered = await asyncio.gather(*(one(i) for i in tech_items))
        for row in gathered:
            if row is not None:
                results.append(row)
        return results

    async def fetch(self) -> list[NormalizedJob]:
        if not self.boards:
            return []
        board_sem = asyncio.Semaphore(get_settings().ingest_concurrency)
        out: list[NormalizedJob] = []

        async def run(board: dict) -> list[NormalizedJob]:
            async with board_sem:
                return await self._fetch_board(board)

        chunks = await asyncio.gather(*(run(b) for b in self.boards))
        for chunk in chunks:
            out.extend(chunk)
        return out
