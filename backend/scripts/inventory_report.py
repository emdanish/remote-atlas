"""One-shot inventory report for operators."""
from __future__ import annotations

import asyncio

from sqlalchemy import text

from app.ai.provider import embedding_provider_name
from app.config import get_settings
from app.db.session import AsyncSessionLocal
from app.pipeline.freshness import freshness_cutoff


async def main() -> None:
    settings = get_settings()
    cutoff = freshness_cutoff(settings.freshness_days)
    cutoff14 = freshness_cutoff(14)
    async with AsyncSessionLocal() as db:
        inv = (
            await db.execute(
                text(
                    """
                    SELECT
                      count(*) AS total_jobs,
                      count(*) FILTER (WHERE is_active) AS active_jobs,
                      count(*) FILTER (
                        WHERE is_active AND (
                          posted_at >= :c OR (posted_at IS NULL AND first_seen_at >= :c)
                        )
                      ) AS fresh_30,
                      count(*) FILTER (
                        WHERE is_active AND (
                          posted_at >= :c14 OR (posted_at IS NULL AND first_seen_at >= :c14)
                        )
                      ) AS fresh_14,
                      count(*) FILTER (
                        WHERE is_active AND apply_url IS NOT NULL AND apply_url <> ''
                      ) AS with_apply,
                      count(*) FILTER (WHERE is_active AND embedding IS NOT NULL) AS embedded,
                      count(DISTINCT company_name) FILTER (WHERE is_active) AS companies,
                      count(DISTINCT source) FILTER (WHERE is_active) AS sources
                    FROM jobs
                    """
                ),
                {"c": cutoff, "c14": cutoff14},
            )
        ).mappings().one()
        by_src = (
            await db.execute(
                text(
                    """
                    SELECT source, count(*) AS n
                    FROM jobs
                    WHERE is_active
                    GROUP BY source
                    ORDER BY n DESC
                    """
                )
            )
        ).mappings().all()
        cos = (
            await db.execute(
                text(
                    """
                    SELECT
                      count(*) FILTER (WHERE is_enabled) AS enabled,
                      count(*) FILTER (
                        WHERE region_focus IN ('pakistan', 'both')
                      ) AS pk,
                      count(DISTINCT ats_type) FILTER (WHERE is_enabled) AS ats
                    FROM companies
                    """
                )
            )
        ).mappings().one()
        print("INVENTORY", dict(inv))
        print("COMPANIES", dict(cos))
        print("EMBED_PROVIDER", embedding_provider_name())
        print("BY_SOURCE")
        for r in by_src:
            print(f"  {r['source']}: {r['n']}")


if __name__ == "__main__":
    asyncio.run(main())
