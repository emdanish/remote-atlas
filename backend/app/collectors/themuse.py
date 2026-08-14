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


class TheMuseCollector(BaseCollector):
    source = "themuse"

    async def fetch(self) -> list[NormalizedJob]:
        settings = get_settings()
        api_key = (settings.the_muse_api_key or "").strip()
        cutoff = datetime.now(timezone.utc) - timedelta(days=settings.freshness_days)
        results: list[NormalizedJob] = []
        seen: set[str] = set()

        categories = ("Software Engineering", "Data Science", "Design and UX")
        level_passes: tuple[str | None, ...] = (None, "Internship", "Entry Level")
        for category in categories:
            for level in level_passes:
                for page in range(0, 20):
                    params: dict = {
                        "page": page,
                        "category": category,
                        "location": "Flexible / Remote",
                        "descending": "true",
                    }
                    if level:
                        params["level"] = level
                    if api_key:
                        params["api_key"] = api_key
                    resp = await self.client.get(
                        "https://www.themuse.com/api/public/jobs",
                        params=params,
                    )
                    if resp.status_code == 429:
                        break
                    if resp.status_code != 200:
                        break
                    data = resp.json()
                    jobs_raw = data.get("results") or []
                    if not jobs_raw:
                        break

                    page_fresh = 0
                    for item in jobs_raw:
                        title = (item.get("name") or "").strip()
                        company = (
                            (item.get("company") or {}).get("name")
                            if isinstance(item.get("company"), dict)
                            else ""
                        )
                        company = (company or "").strip()
                        if not title or not company or not looks_technical(title):
                            continue

                        ext_id = str(item.get("id"))
                        if ext_id in seen:
                            continue
                        seen.add(ext_id)

                        posted = parse_datetime(item.get("publication_date"))
                        if posted is not None and posted < cutoff:
                            continue
                        page_fresh += 1

                        locs = item.get("locations") or []
                        location = ", ".join(
                            (loc.get("name") if isinstance(loc, dict) else str(loc))
                            for loc in locs
                        ) or "Remote"
                        contents = item.get("contents") or ""
                        text = html_to_text(contents) if "<" in contents else contents
                        levels = item.get("levels") or []
                        level_hint = " ".join(
                            (lv.get("name") if isinstance(lv, dict) else str(lv))
                            for lv in levels
                        )
                        enriched = enrich_job_fields(title, text, location)

                        refs = item.get("refs") or {}
                        apply = refs.get("landing_page") if isinstance(refs, dict) else None

                        results.append(
                            NormalizedJob(
                                source=self.source,
                                external_id=ext_id,
                                title=title,
                                company_name=company,
                                company_url=None,
                                career_page_url=normalize_url(apply),
                                apply_url=normalize_url(apply),
                                description_text=text,
                                description_html=contents if "<" in contents else None,
                                location_raw=location,
                                workplace_type=infer_workplace_type(location, "remote", text),
                                employment_type=item.get("type"),
                                career_stage=infer_career_stage(
                                    title, text, source_level=level_hint or None
                                ),
                                source_level=level_hint or None,
                                skills=enriched["skills"],
                                tech_tags=enriched["tech_tags"],
                                posted_at=posted,
                            )
                        )

                    if page_fresh == 0 and page > 2:
                        break

        return results
