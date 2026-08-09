#!/usr/bin/env python3
"""Re-normalize stored job descriptions in batches (idempotent).

Usage (from backend/):
  python -m app.scripts.normalize_descriptions --dry-run
  python -m app.scripts.normalize_descriptions --limit 500
  python -m app.scripts.normalize_descriptions
"""

from __future__ import annotations

import argparse
import asyncio
import logging
from typing import Optional

from sqlalchemy import select, text

from app.db.session import AsyncSessionLocal
from app.models import Job
from app.pipeline.description import (
    looks_like_encoded_html,
    normalize_job_description_fields,
)

logger = logging.getLogger("normalize_descriptions")
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


def _needs_repair(html: Optional[str], text: Optional[str]) -> bool:
    html = html or ""
    text = text or ""
    if looks_like_encoded_html(html) or looks_like_encoded_html(text):
        return True
    if "data-sheets" in html or "data-stringify" in html:
        return True
    # Visible markup leaked into plain text
    if "<p>" in text or "<li>" in text or "&lt;p&gt;" in text:
        return True
    # Always re-run canonicalizer — it is idempotent for good content
    return bool(html or text)


async def run(*, dry_run: bool, limit: Optional[int], batch_size: int) -> dict:
    stats = {
        "scanned": 0,
        "changed": 0,
        "unchanged": 0,
        "encoded_before": 0,
        "sheets_before": 0,
        "by_source": {},
    }
    offset_id = 0
    processed = 0

    async with AsyncSessionLocal() as session:
        while True:
            q = (
                select(Job)
                .where(Job.id > offset_id)
                .order_by(Job.id.asc())
                .limit(batch_size)
            )
            if limit is not None:
                remaining = limit - processed
                if remaining <= 0:
                    break
                q = q.limit(min(batch_size, remaining))

            rows = (await session.execute(q)).scalars().all()
            if not rows:
                break

            for job in rows:
                offset_id = job.id
                processed += 1
                stats["scanned"] += 1
                before_html = job.description_html or ""
                before_text = job.description_text or ""
                if looks_like_encoded_html(before_html) or looks_like_encoded_html(before_text):
                    stats["encoded_before"] += 1
                if "data-sheets" in before_html:
                    stats["sheets_before"] += 1

                if not _needs_repair(before_html, before_text):
                    stats["unchanged"] += 1
                    continue

                new_html, new_text = normalize_job_description_fields(
                    job.description_html,
                    job.description_text,
                )
                if (new_html or "") == before_html and (new_text or "") == before_text:
                    stats["unchanged"] += 1
                    continue

                stats["changed"] += 1
                src = job.source or "unknown"
                stats["by_source"][src] = stats["by_source"].get(src, 0) + 1

                if not dry_run:
                    job.description_html = new_html
                    job.description_text = new_text

            if not dry_run:
                await session.commit()
            else:
                await session.rollback()

            logger.info(
                "batch complete through id=%s scanned=%s changed=%s",
                offset_id,
                stats["scanned"],
                stats["changed"],
            )

        if not dry_run and stats["changed"]:
            # Refresh FTS for changed batch set is heavy — rebuild search_tsv for active jobs in chunks
            await session.execute(
                text(
                    """
                    UPDATE jobs j SET search_tsv =
                      setweight(to_tsvector('english', coalesce(j.title, '')), 'A') ||
                      setweight(to_tsvector('english', coalesce(j.company_name, '')), 'A') ||
                      setweight(to_tsvector('english', coalesce(array_to_string(j.skills, ' '), '')), 'B') ||
                      setweight(to_tsvector('english', coalesce(left(j.description_text, 8000), '')), 'C')
                    WHERE j.is_active = true
                    """
                )
            )
            await session.commit()

    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description="Normalize stored job descriptions")
    parser.add_argument("--dry-run", action="store_true", help="Report only; no writes")
    parser.add_argument("--limit", type=int, default=None, help="Max jobs to scan")
    parser.add_argument("--batch-size", type=int, default=200)
    args = parser.parse_args()
    stats = asyncio.run(
        run(dry_run=args.dry_run, limit=args.limit, batch_size=args.batch_size)
    )
    logger.info("DONE %s", stats)


if __name__ == "__main__":
    main()
