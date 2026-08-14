from __future__ import annotations

import argparse
import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path

import yaml
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.collectors import (
    ArbeitnowCollector,
    AshbyCollector,
    BambooHRCollector,
    BreezyCollector,
    GreenhouseCollector,
    HimalayasCollector,
    JobicyCollector,
    LeverCollector,
    PersonioCollector,
    RecruiteeCollector,
    RemoteJobsOrgCollector,
    RemoteOKCollector,
    RemotiveCollector,
    SmartRecruitersCollector,
    TeamtailorCollector,
    TheMuseCollector,
    WeWorkRemotelyCollector,
    WorkableCollector,
    WorkdayCollector,
)
from app.config import get_settings
from app.db.session import AsyncSessionLocal
from app.models import Company, IngestRun
from app.pipeline.freshness import expire_stale_jobs, purge_expired_jobs
from app.pipeline.normalize import NormalizedJob
from app.pipeline.upsert import (
    deactivate_unseen_for_sources,
    suppress_cross_source_duplicates,
    upsert_jobs,
)
from app.search.embed_pipeline import EmbedPassStats, maybe_embed_missing

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger("ingest")

ALL_SOURCES = {
    "remotive",
    "remoteok",
    "jobicy",
    "himalayas",
    "arbeitnow",
    "themuse",
    "weworkremotely",
    "remotejobsorg",
    "greenhouse",
    "breezy",
    "lever",
    "ashby",
    "workable",
    "smartrecruiters",
    "recruitee",
    "personio",
    "teamtailor",
    "workday",
    "bamboohr",
}


async def _junior_hirer_names() -> set[str]:
    path = Path(__file__).resolve().parents[1] / "data" / "junior_hirers.yaml"
    if not path.exists():
        return set()
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    names = data.get("names") or []
    return {str(n).strip().lower() for n in names if str(n).strip()}


async def sync_companies_simple(session) -> list[Company]:
    """Batch upsert company registry from YAML (no N+1 selects)."""
    settings = get_settings()
    path = Path(settings.companies_path)
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    rows = data.get("companies") or []
    junior_names = await _junior_hirer_names()
    if not rows:
        result = await session.execute(select(Company).where(Company.is_enabled.is_(True)))
        return list(result.scalars().all())

    # Dedupe YAML keys so ON CONFLICT never double-updates the same row
    by_key: dict[tuple[str, str], dict] = {}
    for row in rows:
        ats = (row.get("ats_type") or "").strip()
        slug = (row.get("ats_slug") or "").strip()
        if not ats or not slug:
            continue
        by_key[(ats, slug)] = row

    payload = [
        {
            "name": (row.get("name") or slug)[:255],
            "website": ((row.get("website") or None) and str(row.get("website"))[:512]) or None,
            "ats_type": ats[:64],
            "ats_slug": slug[:128],
            "career_page_url": (
                (str(row.get("career_page_url"))[:1024] if row.get("career_page_url") else None)
            ),
            "region_focus": (row.get("region_focus") or "global")[:32],
            "is_enabled": bool(row.get("is_enabled", True)),
            "hires_juniors": bool(row.get("hires_juniors", False))
            or (row.get("name") or slug).strip().lower() in junior_names,
        }
        for (ats, slug), row in by_key.items()
    ]

    chunk = 500
    now = datetime.now(timezone.utc)
    for start in range(0, len(payload), chunk):
        part = payload[start : start + chunk]
        stmt = pg_insert(Company).values(part)
        stmt = stmt.on_conflict_do_update(
            index_elements=["ats_type", "ats_slug"],
            set_={
                "name": stmt.excluded.name,
                "website": stmt.excluded.website,
                "career_page_url": stmt.excluded.career_page_url,
                "region_focus": stmt.excluded.region_focus,
                "is_enabled": stmt.excluded.is_enabled,
                "hires_juniors": stmt.excluded.hires_juniors,
                "updated_at": now,
            },
        )
        await session.execute(stmt)
    await session.commit()
    result = await session.execute(select(Company).where(Company.is_enabled.is_(True)))
    return list(result.scalars().all())


async def record_run(
    session,
    source: str,
    *,
    fetched: int,
    upserted: int,
    error: str | None,
    started: datetime,
) -> None:
    run = IngestRun(
        source=source,
        started_at=started,
        finished_at=datetime.now(timezone.utc),
        jobs_fetched=fetched,
        jobs_upserted=upserted,
        errors=error,
    )
    session.add(run)
    await session.commit()


async def run_ingest(sources: list[str] | None = None, embed: bool = True) -> int:
    wanted = set(sources) if sources else set(ALL_SOURCES)
    t0 = datetime.now(timezone.utc)
    totals = {
        "sources_started": 0,
        "sources_ok": 0,
        "sources_failed": 0,
        "fetched": 0,
        "upserted": 0,
    }

    async with AsyncSessionLocal() as session:
        companies = await sync_companies_simple(session)
        logger.info("Ingestion started | companies=%s | sources_wanted=%s", len(companies), len(wanted))

        def boards(ats: str) -> list[dict]:
            return [
                {
                    "id": c.id,
                    "name": c.name,
                    "ats_slug": c.ats_slug,
                    "website": c.website,
                    "career_page_url": c.career_page_url,
                }
                for c in companies
                if c.ats_type == ats and c.ats_slug
            ]

        # Build fetch callables (HTTP only — no DB)
        fetchers: list[tuple[str, object]] = []

        async def wrap_feed(name: str, cls):
            async def _fetch() -> list[NormalizedJob]:
                async with cls() as c:
                    return await c.fetch()

            return name, _fetch

        async def wrap_ats(name: str, cls, board_list: list[dict]):
            async def _fetch() -> list[NormalizedJob]:
                async with cls(board_list) as c:
                    return await c.fetch()

            return name, _fetch

        if "remotive" in wanted:
            fetchers.append(await wrap_feed("remotive", RemotiveCollector))
        if "remoteok" in wanted:
            fetchers.append(await wrap_feed("remoteok", RemoteOKCollector))
        if "jobicy" in wanted:
            fetchers.append(await wrap_feed("jobicy", JobicyCollector))
        if "himalayas" in wanted:
            fetchers.append(await wrap_feed("himalayas", HimalayasCollector))
        if "arbeitnow" in wanted:
            fetchers.append(await wrap_feed("arbeitnow", ArbeitnowCollector))
        if "themuse" in wanted:
            fetchers.append(await wrap_feed("themuse", TheMuseCollector))
        if "weworkremotely" in wanted:
            fetchers.append(await wrap_feed("weworkremotely", WeWorkRemotelyCollector))
        if "remotejobsorg" in wanted:
            fetchers.append(await wrap_feed("remotejobsorg", RemoteJobsOrgCollector))

        for ats_name, cls, board_list in (
            ("greenhouse", GreenhouseCollector, boards("greenhouse")),
            ("lever", LeverCollector, boards("lever")),
            ("ashby", AshbyCollector, boards("ashby")),
            ("workable", WorkableCollector, boards("workable")),
            ("smartrecruiters", SmartRecruitersCollector, boards("smartrecruiters")),
            ("recruitee", RecruiteeCollector, boards("recruitee")),
            ("personio", PersonioCollector, boards("personio")),
            ("teamtailor", TeamtailorCollector, boards("teamtailor")),
            ("breezy", BreezyCollector, boards("breezy")),
            ("workday", WorkdayCollector, boards("workday")),
            ("bamboohr", BambooHRCollector, boards("bamboohr")),
        ):
            if ats_name in wanted and board_list:
                fetchers.append(await wrap_ats(ats_name, cls, board_list))

        totals["sources_started"] = len(fetchers)
        # Run one source at a time (feeds first, then ATS). Inside each collector
        # board concurrency still applies via INGEST_CONCURRENCY.
        # Parallel source-start was starving/killing long Greenhouse/Ashby runs on
        # small Render instances before they could finish recording jobs.
        feed_order = (
            "remotive",
            "remoteok",
            "jobicy",
            "himalayas",
            "arbeitnow",
            "themuse",
            "weworkremotely",
            "remotejobsorg",
        )
        order_index = {name: i for i, name in enumerate(feed_order)}
        fetchers.sort(key=lambda pair: (0 if pair[0] in order_index else 1, order_index.get(pair[0], 99), pair[0]))

        logger.info(
            "Fetching %s sources sequentially (feeds first, then company ATS boards)…",
            len(fetchers),
        )
        started: dict[str, datetime] = {}

        async def fetch_named(
            name: str, fn
        ) -> tuple[str, list[NormalizedJob] | None, Exception | None]:
            try:
                return name, await fn(), None
            except Exception as exc:  # noqa: BLE001
                return name, None, exc

        successful_sources: list[str] = []
        for name, fn in fetchers:
            started[name] = datetime.now(timezone.utc)
            logger.info("Source %s starting…", name)
            name, result, fetch_error = await fetch_named(name, fn)
            if fetch_error is not None:
                totals["sources_failed"] += 1
                logger.error("Source %s failed: %s", name, fetch_error)
                await record_run(
                    session,
                    name,
                    fetched=0,
                    upserted=0,
                    error=str(fetch_error)[:2000],
                    started=started[name],
                )
                continue
            jobs = result or []
            try:
                upserted = await upsert_jobs(session, jobs)
                successful_sources.append(name)
                totals["sources_ok"] += 1
                totals["fetched"] += len(jobs)
                totals["upserted"] += upserted
                logger.info(
                    "Source %s completed | fetched=%s upserted=%s",
                    name,
                    len(jobs),
                    upserted,
                )
                await record_run(
                    session,
                    name,
                    fetched=len(jobs),
                    upserted=upserted,
                    error=None,
                    started=started[name],
                )
            except Exception as exc:  # noqa: BLE001
                totals["sources_failed"] += 1
                logger.exception("Source %s upsert failed: %s", name, exc)
                await session.rollback()
                await record_run(
                    session,
                    name,
                    fetched=len(jobs),
                    upserted=0,
                    error=str(exc)[:2000],
                    started=started[name],
                )

        unseen = await deactivate_unseen_for_sources(session, successful_sources, t0)
        deactivated = await suppress_cross_source_duplicates(session)
        expired = await expire_stale_jobs(session)
        purged = await purge_expired_jobs(session)
        logger.info(
            "Housekeeping | unseen_deactivated=%s duplicates_deactivated=%s "
            "stale_expired=%s purged_past_window=%s",
            unseen,
            deactivated,
            expired,
            purged,
        )

        jobs_elapsed = (datetime.now(timezone.utc) - t0).total_seconds()
        logger.info(
            "Job sync finished in %.1fs | started=%s ok=%s failed=%s fetched=%s upserted=%s — embeddings=%s",
            jobs_elapsed,
            totals["sources_started"],
            totals["sources_ok"],
            totals["sources_failed"],
            totals["fetched"],
            totals["upserted"],
            embed,
        )

        embed_stats = EmbedPassStats(status="SKIPPED")
        if embed:
            # Prefer deploy cron process isolation; in-process embed is for local only.
            try:
                embed_stats = await maybe_embed_missing(session)
            except Exception:  # noqa: BLE001
                logger.exception(
                    "Embedding pass crashed; jobs remain searchable via FTS"
                )
                embed_stats = EmbedPassStats(status="FAILED", errors=["exception"])

        from sqlalchemy import text as sql_text

        inventory = (
            await session.execute(
                sql_text(
                    """
                    SELECT
                      count(*) FILTER (WHERE is_active) AS active_jobs,
                      count(*) FILTER (
                        WHERE is_active AND (
                          posted_at >= NOW() - make_interval(days => :days)
                          OR (posted_at IS NULL AND first_seen_at >= NOW() - make_interval(days => :days))
                        )
                      ) AS fresh_jobs,
                      count(*) FILTER (
                        WHERE is_active AND junior_eligible AND (
                          posted_at >= NOW() - make_interval(days => :days)
                          OR (posted_at IS NULL AND first_seen_at >= NOW() - make_interval(days => :days))
                        )
                      ) AS junior_eligible_jobs,
                      count(*) FILTER (
                        WHERE is_active AND career_stage = 'internship' AND (
                          posted_at >= NOW() - make_interval(days => :days)
                          OR (posted_at IS NULL AND first_seen_at >= NOW() - make_interval(days => :days))
                        )
                      ) AS internship_jobs,
                      count(*) FILTER (
                        WHERE is_active AND career_stage = 'new_grad' AND (
                          posted_at >= NOW() - make_interval(days => :days)
                          OR (posted_at IS NULL AND first_seen_at >= NOW() - make_interval(days => :days))
                        )
                      ) AS new_grad_jobs
                    FROM jobs
                    """
                ),
                {"days": get_settings().freshness_days},
            )
        ).mappings().one()

        elapsed = (datetime.now(timezone.utc) - t0).total_seconds()
        if totals["sources_started"] > 0 and totals["sources_ok"] == 0:
            logger.error(
                "INGESTION STATUS = FAILED | duration=%.1fs | sources_ok=0/%s | fetched=%s",
                elapsed,
                totals["sources_started"],
                totals["fetched"],
            )
            return 1
        logger.info(
            "INGESTION STATUS = SUCCESS | duration=%.1fs | sources_ok=%s/%s | fetched=%s | "
            "upserted=%s | embedded=%s | active_jobs=%s | fresh_jobs=%s | "
            "junior_eligible=%s | internships=%s | new_grad=%s | freshness_days=%s",
            elapsed,
            totals["sources_ok"],
            totals["sources_started"],
            totals["fetched"],
            totals["upserted"],
            embed_stats.processed,
            inventory["active_jobs"],
            inventory["fresh_jobs"],
            inventory["junior_eligible_jobs"],
            inventory["internship_jobs"],
            inventory["new_grad_jobs"],
            get_settings().freshness_days,
        )
        if embed:
            logger.info("EMBEDDING STATUS = %s", embed_stats.status)
        return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Remote Atlas ingest CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    run_parser = sub.add_parser("run", help="Fetch + upsert jobs, then optional batch-embed")
    run_parser.add_argument("--sources", nargs="*", help="Subset of sources")
    run_parser.add_argument(
        "--embed",
        action="store_true",
        help="Also embed in this process (prefer separate process via deploy cron)",
    )
    run_parser.add_argument(
        "--no-embed",
        action="store_true",
        help="Skip embeddings (default for production crawl process)",
    )

    embed_parser = sub.add_parser("embed", help="Batch-embed jobs missing vectors (fresh process)")
    embed_parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Max jobs this run (default: settings.embed_max_per_run)",
    )

    args = parser.parse_args()
    if args.command == "run":
        # Default: no embed in same process (memory). Use --embed only for local convenience.
        do_embed = bool(args.embed) and not bool(args.no_embed)
        raise SystemExit(asyncio.run(run_ingest(sources=args.sources, embed=do_embed)))
    elif args.command == "embed":

        async def _embed() -> int:
            async with AsyncSessionLocal() as session:
                stats = await maybe_embed_missing(session, limit=args.limit)
                logger.info(
                    "Embed CLI finished | status=%s | embedded=%s | remaining=%s",
                    stats.status,
                    stats.processed,
                    stats.remaining,
                )
                if stats.status == "FAILED":
                    return 1
                return 0

        raise SystemExit(asyncio.run(_embed()))


if __name__ == "__main__":
    main()
