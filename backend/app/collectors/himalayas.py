from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import httpx

from app.collectors.base import BaseCollector
from app.collectors.tech_filter import looks_technical, looks_technical_category
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

_SEARCH_QUERIES = (
    "software engineer",
    "developer",
    "backend",
    "frontend",
    "fullstack",
    "devops",
    "data engineer",
    "machine learning",
    "flutter",
    "react",
    "python",
    "internship",
)
_MAX_PAGES = 12


class HimalayasCollector(BaseCollector):
    source = "himalayas"

    async def fetch(self) -> list[NormalizedJob]:
        cutoff = datetime.now(timezone.utc) - timedelta(days=get_settings().freshness_days)
        by_guid: dict[str, NormalizedJob] = {}
        sem = asyncio.Semaphore(4)

        async def one_query(query: str) -> list[NormalizedJob]:
            out: list[NormalizedJob] = []
            page = 1
            stale_pages = 0
            while page <= _MAX_PAGES:
                async with sem:
                    try:
                        resp = await self.client.get(
                            "https://himalayas.app/jobs/api/search",
                            params={"q": query, "sort": "recent", "page": page},
                        )
                    except httpx.HTTPError:
                        break
                if resp.status_code == 429:
                    break
                if resp.status_code != 200:
                    break
                data = resp.json()
                jobs_raw = data.get("jobs") or []
                if not jobs_raw:
                    break
                page_all_stale = True
                for item in jobs_raw:
                    job = self._normalize(item, cutoff)
                    if job is None:
                        continue
                    page_all_stale = False
                    out.append(job)
                if page_all_stale:
                    stale_pages += 1
                    if stale_pages >= 2:
                        break
                else:
                    stale_pages = 0
                page += 1
            return out

        batches = await asyncio.gather(
            *(one_query(q) for q in _SEARCH_QUERIES),
            return_exceptions=True,
        )
        for batch in batches:
            if isinstance(batch, Exception):
                continue
            for job in batch:
                by_guid[job.external_id] = job
        return list(by_guid.values())

    def _normalize(self, item: dict, cutoff: datetime) -> NormalizedJob | None:
        title = (item.get("title") or "").strip()
        company = (item.get("companyName") or "").strip()
        if not title or not company:
            return None

        categories = item.get("categories") or item.get("parentCategories") or []
        if not looks_technical(title) and not looks_technical_category(categories):
            return None

        posted = parse_datetime(item.get("pubDate"))
        expiry = parse_datetime(item.get("expiryDate"))
        if expiry is not None and expiry < datetime.now(timezone.utc):
            return None
        if posted is not None and posted < cutoff:
            return None

        description = item.get("description") or item.get("excerpt") or ""
        text = html_to_text(description) if "<" in description else description
        locs = item.get("locationRestrictions") or []
        if isinstance(locs, list) and locs:
            location_parts = []
            for loc in locs[:8]:
                if isinstance(loc, dict):
                    location_parts.append(loc.get("name") or loc.get("slug") or "")
                else:
                    location_parts.append(str(loc))
            location = ", ".join(p for p in location_parts if p) or "Remote"
        else:
            location = "Worldwide Remote"
        location = location[:480]

        seniority = item.get("seniority") or []
        if isinstance(seniority, list):
            seniority_hint = " ".join(str(s) for s in seniority)
        else:
            seniority_hint = str(seniority)
        cats = [str(c) for c in (categories or [])][:8]
        enriched = enrich_job_fields(title, text, location, existing_tags=cats)

        guid = str(item.get("guid") or item.get("applicationLink") or f"{company}:{title}")
        return NormalizedJob(
            source=self.source,
            external_id=guid[:240],
            title=title[:500],
            company_name=company[:240],
            company_url=None,
            career_page_url=normalize_url(item.get("applicationLink")),
            apply_url=normalize_url(item.get("applicationLink")),
            description_text=text,
            description_html=description if "<" in description else None,
            location_raw=location,
            workplace_type=infer_workplace_type(location, "remote", text),
            employment_type=str(item.get("employmentType") or "")[:60] or None,
            career_stage=infer_career_stage(f"{title} {seniority_hint}", text),
            skills=enriched["skills"],
            tech_tags=enriched["tech_tags"],
            posted_at=posted,
        )
