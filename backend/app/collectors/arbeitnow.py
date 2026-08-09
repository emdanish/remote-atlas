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
        page = 1
        while page <= 40:
            resp = await self.client.get(
                "https://www.arbeitnow.com/api/job-board-api",
                params={"page": page},
            )
            if resp.status_code != 200:
                break
            data = resp.json()
            jobs_raw = data.get("data") or []
            if not jobs_raw:
                break

            page_fresh = 0
            for item in jobs_raw:
                title = (item.get("title") or "").strip()
                company = (item.get("company_name") or "").strip()
                if not title or not company or not looks_technical(title):
                    continue

                remote = bool(item.get("remote"))
                location = item.get("location") or ("Remote" if remote else None)
                # Prefer remote; still keep EU tech roles (visa/relocation signal for global seekers)
                tags = item.get("tags") or []
                tag_blob = " ".join(str(t).lower() for t in tags)
                if not remote and "remote" not in (location or "").lower() and "remote" not in tag_blob:
                    # Keep Germany/EU engineering if clearly technical (Arbeitnow is EU-heavy)
                    if not location:
                        continue

                description = item.get("description") or ""
                text = html_to_text(description) if "<" in description else description
                posted = parse_datetime(item.get("created_at"))
                if posted is not None and posted < cutoff:
                    continue
                apply = normalize_url(item.get("url"))
                if not apply:
                    continue
                page_fresh += 1

                enriched = enrich_job_fields(
                    title,
                    text,
                    location,
                    existing_tags=[str(t) for t in tags],
                )
                slug = item.get("slug") or item.get("url") or f"{company}:{title}"
                results.append(
                    NormalizedJob(
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
                        employment_type=None,
                        career_stage=infer_career_stage(title, text),
                        skills=enriched["skills"],
                        tech_tags=enriched["tech_tags"],
                        posted_at=posted,
                    )
                )

            # API pages newest-first; stop when a full page has no fresh tech remote jobs
            if page_fresh == 0 and page > 3:
                break
            page += 1

        return results
