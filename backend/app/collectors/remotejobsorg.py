"""RemoteJobs.org public JSON API — programming category only."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

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

BASE = "https://remotejobs.org/api/v1/jobs"


class RemoteJobsOrgCollector(BaseCollector):
    source = "remotejobsorg"

    async def fetch(self) -> list[NormalizedJob]:
        cutoff = datetime.now(timezone.utc) - timedelta(days=get_settings().freshness_days)
        results: list[NormalizedJob] = []
        seen: set[str] = set()
        offset = 0
        limit = 50
        max_pages = 40

        for _ in range(max_pages):
            try:
                resp = await self.client.get(
                    BASE,
                    params={"category": "programming", "limit": limit, "offset": offset},
                )
                if resp.status_code != 200:
                    break
                data = resp.json()
            except Exception:  # noqa: BLE001
                break

            jobs = data if isinstance(data, list) else (data or {}).get("jobs") or (data or {}).get("data") or []
            if not isinstance(jobs, list) or not jobs:
                break

            for item in jobs:
                if not isinstance(item, dict):
                    continue
                ext_id = str(item.get("id") or item.get("slug") or item.get("url") or "").strip()
                title = (item.get("title") or item.get("position") or "").strip()
                company_raw = item.get("company")
                if isinstance(company_raw, dict):
                    company = (company_raw.get("name") or "").strip()
                    company_site = company_raw.get("url") or company_raw.get("website")
                else:
                    company = (
                        (item.get("company_name") or company_raw or "")
                        if isinstance(company_raw, str)
                        else (item.get("company_name") or "")
                    )
                    company = (company or "").strip()
                    company_site = item.get("company_url") or item.get("company_website")
                if not title or not company:
                    continue
                if not looks_technical(title) and not looks_like_software_role(title, None):
                    continue
                apply_url = normalize_url(
                    item.get("url")
                    or item.get("apply_url")
                    or item.get("application_url")
                    or item.get("link")
                )
                if not apply_url:
                    continue
                key = ext_id or apply_url
                if key in seen:
                    continue
                seen.add(key)

                desc = item.get("description") or item.get("description_html")
                if isinstance(desc, str) and "<" in desc:
                    text = html_to_text(desc)
                elif isinstance(desc, str):
                    text = desc
                else:
                    text = None
                location = item.get("location") or item.get("location_raw") or "Remote"
                if isinstance(location, list):
                    location = ", ".join(str(x) for x in location)
                posted = parse_datetime(
                    item.get("published_at")
                    or item.get("posted_at")
                    or item.get("date")
                    or item.get("created_at")
                )
                if posted is not None and posted < cutoff:
                    continue
                enriched = enrich_job_fields(title, text, str(location))
                results.append(
                    NormalizedJob(
                        source=self.source,
                        external_id=str(key)[:240],
                        title=title,
                        company_name=company,
                        company_url=normalize_url(company_site if isinstance(company_site, str) else None),
                        career_page_url=apply_url,
                        apply_url=apply_url,
                        description_text=text,
                        description_html=desc if isinstance(desc, str) else None,
                        location_raw=str(location) if location else "Remote",
                        workplace_type=infer_workplace_type(str(location), "remote", text),
                        employment_type=(item.get("type") or item.get("employment_type") or None),
                        career_stage=infer_career_stage(title, text),
                        skills=enriched["skills"],
                        tech_tags=enriched["tech_tags"],
                        posted_at=posted,
                    )
                )

            if len(jobs) < limit:
                break
            offset += limit

        return results
