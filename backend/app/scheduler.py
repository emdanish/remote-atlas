"""Simple scheduled ingestion + atlas pulse alerts.

Usage:
  python -m app.scheduler --interval-minutes 180
  python -m app.scheduler --once
  python -m app.scheduler --alerts-only
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import time

from app.db.session import AsyncSessionLocal
from app.ingest import run_ingest
from app.matching.alerts import process_all_saved_search_alerts

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("scheduler")


async def run_alerts() -> dict[str, int]:
    async with AsyncSessionLocal() as db:
        try:
            return await process_all_saved_search_alerts(db)
        except Exception:  # noqa: BLE001
            logger.exception("Pulse alerts failed")
            return {"checked": 0, "notified": 0}


async def loop(interval_minutes: int, embed: bool, sources: list[str] | None) -> None:
    while True:
        started = time.time()
        try:
            await run_ingest(sources=sources, embed=embed)
        except Exception:  # noqa: BLE001
            logger.exception("Scheduled ingest failed")
        try:
            stats = await run_alerts()
            logger.info("Pulse alerts: %s", stats)
        except Exception:  # noqa: BLE001
            logger.exception("Pulse alerts crashed")
        elapsed = time.time() - started
        sleep_for = max(60.0, interval_minutes * 60 - elapsed)
        logger.info("Next cycle in %.0fs", sleep_for)
        await asyncio.sleep(sleep_for)


def main() -> None:
    parser = argparse.ArgumentParser(description="Remote Atlas ingest + pulse scheduler")
    parser.add_argument("--interval-minutes", type=int, default=180)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--alerts-only", action="store_true", help="Only run saved-search pulses")
    parser.add_argument(
        "--embed",
        action="store_true",
        help="Also run embeddings after jobs (off by default)",
    )
    parser.add_argument("--sources", nargs="*")
    args = parser.parse_args()
    if args.alerts_only:
        stats = asyncio.run(run_alerts())
        logger.info("Pulse alerts: %s", stats)
        return
    if args.once:
        async def _once() -> None:
            await run_ingest(sources=args.sources, embed=args.embed)
            stats = await run_alerts()
            logger.info("Pulse alerts: %s", stats)

        asyncio.run(_once())
        return
    asyncio.run(loop(args.interval_minutes, embed=args.embed, sources=args.sources))


if __name__ == "__main__":
    main()
