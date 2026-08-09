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


class RemoteOKCollector(BaseCollector):
    source = "remoteok"

    async def fetch(self) -> list[NormalizedJob]:
        resp = await self.client.get("https://remoteok.com/api")
        resp.raise_for_status()
        data = resp.json()
        if not isinstance(data, list):
            return []

        results: list[NormalizedJob] = []
        for item in data:
            # First element is legal/meta notice
            if not isinstance(item, dict) or "id" not in item or "position" not in item:
                continue
            title = (item.get("position") or item.get("title") or "").strip()
            company = (item.get("company") or "").strip()
            if not title or not company:
                continue

            # Prefer software/dev-ish tags
            tags = [t for t in (item.get("tags") or []) if isinstance(t, str)]
            tag_blob = " ".join(tags).lower()
            if tags and not any(
                k in tag_blob
                for k in (
                    "dev",
                    "engineer",
                    "software",
                    "backend",
                    "frontend",
                    "full",
                    "data",
                    "python",
                    "java",
                    "react",
                    "node",
                    "devops",
                    "mobile",
                    "ai",
                    "ml",
                )
            ):
                # Keep if title looks technical
                if not any(
                    k in title.lower()
                    for k in ("engineer", "developer", "software", "devops", "sre", "data", "ml", "ai")
                ):
                    continue

            description = item.get("description")
            text = html_to_text(description) if description else None
            location = item.get("location") or "Remote"
            enriched = enrich_job_fields(title, text, location, existing_tags=tags)
            apply_url = normalize_url(item.get("apply_url") or item.get("url"))

            results.append(
                NormalizedJob(
                    source=self.source,
                    external_id=str(item.get("id")),
                    title=title,
                    company_name=company,
                    company_url=normalize_url(item.get("company_link")),
                    career_page_url=normalize_url(item.get("url")),
                    apply_url=apply_url,
                    description_text=text,
                    description_html=description,
                    location_raw=location,
                    workplace_type=infer_workplace_type(location, "remote", text),
                    employment_type=None,
                    career_stage=infer_career_stage(title, text),
                    skills=enriched["skills"],
                    tech_tags=enriched["tech_tags"],
                    posted_at=parse_datetime(item.get("date")) or parse_datetime(item.get("epoch")),
                )
            )
        return results
