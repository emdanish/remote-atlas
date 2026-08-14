from __future__ import annotations

from datetime import datetime, timedelta, timezone

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


class ArbeitnowCollector(BaseCollector):
    source = "arbeitnow"

    async def fetch(self) -> list[NormalizedJob]:
        cutoff = datetime.now(timezone.utc) - timedelta(days=get_settings().freshness_days)
        results: list[NormalizedJob] = []
        seen: set[str] = set()
        for extra in ({}, {"jobTypes[]": "internship"}):
            page = 1
            max_pages = 8 if extra else 40
            while page <= max_pages:
                params: dict = {"page": page}
                params.update(extra)
                resp = await self.client.get(
                    "https://www.arbeitnow.com/api/job-board-api",
                    params=params,
                )
                if resp.status_code != 200:
                    break
                data = resp.json()
                jobs_raw = data.get("data") or []
                if not jobs_raw:
                    break

                page_fresh = 0
                for item in jobs_raw:
                    job = self._normalize(item, cutoff, extra)
                    if job is None:
                        continue
                    page_fresh += 1
                    if job.external_id in seen:
                        continue
                    seen.add(job.external_id)
                    results.append(job)

                if page_fresh == 0 and page > 3:
                    break
                page += 1

        return results

    def _normalize(
        self, item: dict, cutoff: datetime, extra: dict
    ) -> NormalizedJob | None:
        title = (item.get("title") or "").strip()
        company = (item.get("company_name") or "").strip()
        if not title or not company or not looks_technical(title):
            return None

        remote = bool(item.get("remote"))
        location = item.get("location") or ("Remote" if remote else None)
        tags = item.get("tags") or []
        tag_blob = " ".join(str(t).lower() for t in tags)
        if not remote and "remote" not in (location or "").lower() and "remote" not in tag_blob:
            if not location:
                return None

        description = item.get("description") or ""
        text = html_to_text(description) if "<" in description else description
        posted = parse_datetime(item.get("created_at"))
        if posted is not None and posted < cutoff:
            return None
        apply = normalize_url(item.get("url"))
        if not apply:
            return None

        enriched = enrich_job_fields(
            title,
            text,
            location,
            existing_tags=[str(t) for t in tags],
        )
        slug = item.get("slug") or item.get("url") or f"{company}:{title}"
        job_types = item.get("job_types") or item.get("jobTypes") or []
        if isinstance(job_types, str):
            job_types = [job_types]
        type_blob = " ".join(str(t) for t in job_types)
        if extra and "intern" not in f"{title} {type_blob} {tag_blob}".lower():
            # Dedicated intern pass: skip rows that are not intern-coded
            pass
        intern_hint = None
        if extra or "intern" in f"{title} {type_blob} {tag_blob}".lower():
            intern_hint = "internship" if "intern" in f"{title} {type_blob}".lower() else None
        employment = type_blob[:60] or None
        return NormalizedJob(
            source=self.source,
            external_id=str(slug)[:240],
            title=title,
            company_name=company,
            company_url=None,
            career_page_url=apply,
            apply_url=apply,
            description_text=text,
            description_html=description if "<" in description else None,
            location_raw=location,
            workplace_type=infer_workplace_type(
                location, "remote" if remote else None, text
            ),
            employment_type=employment,
            career_stage=infer_career_stage(
                title, text, source_level=intern_hint, employment_type=employment
            ),
            source_level=intern_hint,
            skills=enriched["skills"],
            tech_tags=enriched["tech_tags"],
            posted_at=posted,
        )
