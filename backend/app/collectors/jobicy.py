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


class JobicyCollector(BaseCollector):
    source = "jobicy"

    async def fetch(self) -> list[NormalizedJob]:
        # Public remote jobs API — filter to tech-ish industry when possible
        resp = await self.client.get(
            "https://jobicy.com/api/v2/remote-jobs",
            params={"count": 100, "tag": "software"},
        )
        if resp.status_code != 200:
            resp = await self.client.get(
                "https://jobicy.com/api/v2/remote-jobs",
                params={"count": 100},
            )
        resp.raise_for_status()
        data = resp.json()
        jobs_raw = data.get("jobs") or []
        results: list[NormalizedJob] = []

        for item in jobs_raw:
            title = (item.get("jobTitle") or "").strip()
            company = (item.get("companyName") or "").strip()
            if not title or not company:
                continue
            if not any(
                w in title.lower()
                for w in (
                    "engineer",
                    "developer",
                    "software",
                    "devops",
                    "data",
                    "ml",
                    "ai",
                    "sre",
                    "frontend",
                    "backend",
                    "full stack",
                    "intern",
                )
            ):
                continue

            description = item.get("jobDescription") or ""
            text = html_to_text(description) if "<" in description else description
            location = item.get("jobGeo") or "Remote"
            tags = item.get("jobIndustry") or []
            if isinstance(tags, str):
                tags = [tags]
            enriched = enrich_job_fields(title, text, location, existing_tags=[str(t) for t in tags])

            job_type = item.get("jobType")
            if isinstance(job_type, list):
                job_type = ", ".join(str(x) for x in job_type)
            elif job_type is not None:
                job_type = str(job_type)

            results.append(
                NormalizedJob(
                    source=self.source,
                    external_id=str(item.get("id") or item.get("url")),
                    title=title,
                    company_name=company,
                    company_url=normalize_url(item.get("companyUrl")),
                    career_page_url=normalize_url(item.get("url")),
                    apply_url=normalize_url(item.get("url")),
                    description_text=text,
                    description_html=description if "<" in description else None,
                    location_raw=location,
                    workplace_type=infer_workplace_type(location, "remote", text),
                    employment_type=job_type,
                    career_stage=infer_career_stage(title, text),
                    skills=enriched["skills"],
                    tech_tags=enriched["tech_tags"],
                    posted_at=parse_datetime(item.get("pubDate")),
                )
            )
        return results
