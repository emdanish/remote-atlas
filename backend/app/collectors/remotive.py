from __future__ import annotations

from app.collectors.base import BaseCollector
from app.pipeline.enrich import enrich_job_fields
from app.pipeline.normalize import (
    NormalizedJob,
    html_to_text,
    infer_career_stage,
    infer_workplace_type,
    normalize_url,
    parse_datetime,
)


class RemotiveCollector(BaseCollector):
    source = "remotive"

    async def fetch(self) -> list[NormalizedJob]:
        url = "https://remotive.com/api/remote-jobs"
        params = {"category": "software-dev"}
        resp = await self.client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()
        jobs_raw = data.get("jobs") or []
        results: list[NormalizedJob] = []

        for item in jobs_raw:
            title = (item.get("title") or "").strip()
            company = (item.get("company_name") or "").strip()
            if not title or not company:
                continue
            description = item.get("description")
            text = html_to_text(description) if description and "<" in str(description) else description
            location = item.get("candidate_required_location") or "Remote"
            tags = item.get("tags") or []
            enriched = enrich_job_fields(title, text, location, existing_tags=tags)
            job_type = item.get("job_type")
            job_type_s = str(job_type).strip() if job_type else None
            source_level = job_type_s if job_type_s and "intern" in job_type_s.lower() else None
            results.append(
                NormalizedJob(
                    source=self.source,
                    external_id=str(item.get("id")),
                    title=title,
                    company_name=company,
                    company_url=None,
                    career_page_url=normalize_url(item.get("url")),
                    apply_url=normalize_url(item.get("url")),
                    description_text=text,
                    description_html=description if description and "<" in str(description) else None,
                    location_raw=location,
                    workplace_type="remote",
                    employment_type=job_type_s,
                    career_stage=infer_career_stage(
                        title, text, source_level=source_level, employment_type=job_type_s
                    ),
                    source_level=source_level,
                    skills=enriched["skills"],
                    tech_tags=enriched["tech_tags"],
                    posted_at=parse_datetime(item.get("publication_date")),
                )
            )
        return results
