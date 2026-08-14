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
        # Public remote jobs API — extra intern/entry passes use unused jobLevel.
        queries: list[dict] = [
            {"count": 100, "tag": "software"},
            {"count": 50, "tag": "intern"},
            {"count": 50, "jobLevel": "Internship"},
            {"count": 50, "jobLevel": "Entry-Level"},
        ]
        seen: set[str] = set()
        results: list[NormalizedJob] = []
        for params in queries:
            resp = await self.client.get(
                "https://jobicy.com/api/v2/remote-jobs",
                params=params,
            )
            if resp.status_code != 200:
                if params.get("tag") == "software":
                    resp = await self.client.get(
                        "https://jobicy.com/api/v2/remote-jobs",
                        params={"count": 100},
                    )
                    if resp.status_code != 200:
                        continue
                else:
                    continue
            data = resp.json()
            jobs_raw = data.get("jobs") or []
            for item in jobs_raw:
                job = self._normalize(item)
                if job is None or job.external_id in seen:
                    continue
                seen.add(job.external_id)
                results.append(job)
        return results

    def _normalize(self, item: dict) -> NormalizedJob | None:
        title = (item.get("jobTitle") or "").strip()
        company = (item.get("companyName") or "").strip()
        if not title or not company:
            return None
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
            return None

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

        job_level = item.get("jobLevel")
        if isinstance(job_level, list):
            job_level = " ".join(str(x) for x in job_level)
        elif job_level is not None:
            job_level = str(job_level)
        source_level = (job_level or "").strip() or None

        return NormalizedJob(
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
            career_stage=infer_career_stage(
                title, text, source_level=source_level, employment_type=job_type
            ),
            source_level=source_level,
            skills=enriched["skills"],
            tech_tags=enriched["tech_tags"],
            posted_at=parse_datetime(item.get("pubDate")),
        )
