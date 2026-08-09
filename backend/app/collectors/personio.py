from __future__ import annotations

import asyncio
import xml.etree.ElementTree as ET
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


class PersonioCollector(BaseCollector):
    """Public Personio XML career feeds — no auth.

    Tries `{slug}.jobs.personio.de/xml` then `.com`.
    """

    source = "personio"

    def __init__(self, boards: list[dict], client: Optional[httpx.AsyncClient] = None):
        super().__init__(client=client)
        self.boards = boards

    async def _fetch_xml(self, slug: str) -> str | None:
        for host in (
            f"https://{slug}.jobs.personio.de/xml",
            f"https://{slug}.jobs.personio.com/xml",
        ):
            try:
                resp = await self.client.get(host, params={"language": "en"})
                if resp.status_code == 200 and "<position" in resp.text.lower():
                    return resp.text
            except httpx.HTTPError:
                continue
        return None

    def _parse(self, xml_text: str, board: dict) -> list[NormalizedJob]:
        slug = board["ats_slug"]
        company_name = board["name"]
        company_id = board.get("id")
        career_page = board.get("career_page_url") or f"https://{slug}.jobs.personio.de"
        website = board.get("website")
        cutoff = datetime.now(timezone.utc) - timedelta(days=get_settings().freshness_days)

        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError:
            return []

        results: list[NormalizedJob] = []
        for pos in root.findall(".//position"):
            title = (pos.findtext("name") or "").strip()
            if not title or not looks_technical(title, None):
                continue
            job_id = (pos.findtext("id") or "").strip()
            office = (pos.findtext("office") or "").strip()
            department = (pos.findtext("department") or "").strip()
            employment = (pos.findtext("employmentType") or "").strip()
            seniority = (pos.findtext("seniority") or "").strip()
            created = parse_datetime(pos.findtext("createdAt"))
            if created is not None and created < cutoff:
                created = None

            desc_parts: list[str] = []
            for block in pos.findall("./jobDescriptions/jobDescription"):
                name = block.findtext("name") or ""
                value = block.findtext("value") or ""
                if value:
                    desc_parts.append(f"{name}\n{value}" if name else value)
            html = "\n".join(desc_parts)
            text = html_to_text(html) if html else None
            location = office or None
            enriched = enrich_job_fields(
                title,
                text,
                location,
                existing_tags=[department] if department else [],
            )

            apply = f"https://{slug}.jobs.personio.de/job/{job_id}" if job_id else career_page
            results.append(
                NormalizedJob(
                    source=self.source,
                    external_id=f"{slug}:{job_id or title}",
                    title=title[:500],
                    company_name=company_name,
                    company_url=website,
                    career_page_url=career_page,
                    apply_url=normalize_url(apply),
                    description_text=text,
                    description_html=html or None,
                    location_raw=location,
                    workplace_type=infer_workplace_type(location, None, text),
                    employment_type=employment[:60] or None,
                    career_stage=infer_career_stage(f"{title} {seniority}", text),
                    skills=enriched["skills"],
                    tech_tags=enriched["tech_tags"],
                    posted_at=created,
                    company_id=company_id,
                )
            )
        return results

    async def _fetch_board(self, board: dict) -> list[NormalizedJob]:
        xml_text = await self._fetch_xml(board["ats_slug"])
        if not xml_text:
            return []
        return self._parse(xml_text, board)

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
