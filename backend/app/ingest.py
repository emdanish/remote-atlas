from __future__ import annotations

import argparse
import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path

import yaml
from sqlalchemy import or_, select

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
from app.search.embeddings import (
    job_embedding_document,
    job_embedding_hash,
)

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


async def sync_companies_simple(session) -> list[Company]:
    """Batch upsert company registry from YAML (no N+1 selects)."""
    settings = get_settings()
    path = Path(settings.companies_path)
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    rows = data.get("companies") or []
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


async def maybe_embed_missing(session, limit: int | None = None) -> int:
    """Embed active jobs missing vectors, memory-safe for 512Mi dynos.

    Processes at most ``embed_max_per_run`` (or *limit*) jobs, in small DB waves
    and tiny model chunks. Designed to run in a **fresh process** after crawl
    (see ``deploy.exec_cron``) so ONNX is not loaded on top of crawl RSS.
    """
    import gc

    settings = get_settings()
    from app.ai.provider import embedding_provider_name

    provider_name = embedding_provider_name()
    if not provider_name:
        logger.info("No configured embedding provider is available; skipping embeddings")
        return 0
    provider = (settings.embed_provider or "auto").lower()
    if provider in {"none", "off", "fts", "disabled"}:
        logger.info("EMBED_PROVIDER=%s — skipping embeddings (FTS still works)", provider)
        return 0
    if provider == "gemini" and not settings.gemini_keys:
        logger.info("No Gemini API keys set; skipping embeddings")
        return 0
    if provider == "local":
        from app.search.local_embeddings import local_available

        if not local_available():
            logger.info("Local embeddings unavailable (pip install fastembed); skipping")
            return 0

    from app.ai.provider import embed_texts
    from app.models import Job
    from app.search.local_embeddings import local_available, local_embed_texts, unload_local_model
    from app.pipeline.freshness import freshness_cutoff

    max_jobs = limit if limit is not None else settings.embed_max_per_run
    wave = max(8, min(settings.embed_batch_size, max_jobs))
    chunk = max(1, settings.embed_chunk_size)
    use_local = provider == "local" or (
        provider == "auto" and (not settings.gemini_keys or False)
    )
    if provider == "auto" and settings.gemini_keys:
        use_local = False
    consecutive_fail = 0
    max_fail = settings.embed_max_consecutive_failures
    updated = 0
    cutoff = freshness_cutoff(settings.freshness_days)

    while updated < max_jobs:
        remaining = max_jobs - updated
        batch_limit = min(wave, remaining)
        result = await session.execute(
            select(Job.id)
            .where(Job.is_active.is_(True))
            .where(Job.apply_url.is_not(None))
            .where(
                or_(
                    Job.posted_at >= cutoff,
                    (Job.posted_at.is_(None)) & (Job.first_seen_at >= cutoff),
                )
            )
            .where(
                or_(
                    Job.embedding.is_(None),
                    Job.embedding_hash.is_(None),
                    Job.embedding_provider.is_(None),
                    Job.embedding_provider != provider_name,
                )
            )
            .order_by(Job.last_seen_at.desc())
            .limit(batch_limit)
        )
        ids = [row[0] for row in result.all()]
        if not ids:
            break

        jobs_result = await session.execute(select(Job).where(Job.id.in_(ids)))
        jobs = list(jobs_result.scalars().all())
        if not jobs:
            break

        docs: list[str] = []
        hashes: list[str] = []
        eligible: list = []
        provider_fixed = 0
        for job in jobs:
            h = job_embedding_hash(
                job.title,
                job.company_name,
                job.skills or [],
                job.career_stage,
                job.workplace_type,
                job.description_text,
            )
            if job.embedding is not None and job.embedding_hash == h:
                # Already embedded for this content; only sync provider label if needed
                if job.embedding_provider != provider_name:
                    job.embedding_provider = provider_name
                    provider_fixed += 1
                continue
            hashes.append(h)
            docs.append(
                job_embedding_document(
                    job.title,
                    job.company_name,
                    job.skills or [],
                    job.career_stage,
                    job.workplace_type,
                    job.description_text,
                )
            )
            eligible.append(job)

        if provider_fixed:
            await session.commit()

        if not eligible:
            if not provider_fixed:
                break
            continue

        wave_updated = 0
        for start in range(0, len(docs), chunk):
            end = min(start + chunk, len(docs))
            part = docs[start:end]
            success = False
            for attempt in range(4):
                try:
                    if use_local or provider == "local":
                        vecs = await local_embed_texts(part, batch_size=chunk)
                    else:
                        vecs = await embed_texts(part)
                        if not vecs and provider == "auto" and local_available():
                            logger.warning("Gemini returned empty; switching to local embeddings")
                            use_local = True
                            vecs = await local_embed_texts(part, batch_size=chunk)
                    if not vecs or len(vecs) != len(part):
                        raise RuntimeError(
                            f"embed returned {0 if not vecs else len(vecs)} vectors"
                        )
                    for i, v in enumerate(vecs):
                        job = eligible[start + i]
                        job.embedding = v
                        job.embedding_hash = hashes[start + i]
                        job.embedding_provider = provider_name
                        updated += 1
                        wave_updated += 1
                    success = True
                    consecutive_fail = 0
                    break
                except Exception as exc:  # noqa: BLE001
                    msg = str(exc)
                    if "429" in msg or "Too Many" in msg or "RESOURCE_EXHAUSTED" in msg:
                        consecutive_fail += 1
                        wait = min(60, 8 * (attempt + 1))
                        logger.warning(
                            "Embed rate-limited; sleeping %ss (attempt %s, streak %s)",
                            wait,
                            attempt + 1,
                            consecutive_fail,
                        )
                        if consecutive_fail >= max_fail and provider == "auto" and local_available():
                            logger.warning(
                                "Gemini quota circuit open — switching to local embeddings"
                            )
                            use_local = True
                            consecutive_fail = 0
                            continue
                        if consecutive_fail >= max_fail and provider == "gemini":
                            logger.error("Gemini quota exhausted; stopping embed pass early")
                            if updated:
                                await session.commit()
                            unload_local_model()
                            return updated
                        await asyncio.sleep(wait)
                        continue
                    logger.warning("Embed slice %s-%s failed: %s", start, end, exc)
                    consecutive_fail += 1
                    break
            if success:
                await session.commit()
                if not use_local:
                    await asyncio.sleep(0.25)
            if updated % 32 == 0 and updated:
                logger.info("Embedded progress %s (max this run %s)", updated, max_jobs)
            # Encourage memory return between slices on tiny dynos
            if use_local and (start // chunk) % 8 == 7:
                gc.collect()

        if wave_updated == 0:
            # No progress — avoid infinite loop if rows keep reappearing
            break
        # Free description text references before next wave
        del docs, hashes, eligible, jobs
        gc.collect()

    unload_local_model()
    logger.info("Embedded %s jobs this pass (cap=%s)", updated, max_jobs)
    return updated


async def run_ingest(sources: list[str] | None = None, embed: bool = True) -> None:
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

        embedded = 0
        if embed:
            # Async batched embeddings after jobs are searchable via FTS
            try:
                embedded = await maybe_embed_missing(session)
            except Exception:  # noqa: BLE001
                logger.exception("Embedding pass failed; jobs remain searchable via FTS")

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
                      ) AS fresh_jobs
                    FROM jobs
                    """
                ),
                {"days": get_settings().freshness_days},
            )
        ).mappings().one()

        elapsed = (datetime.now(timezone.utc) - t0).total_seconds()
        logger.info(
            "Ingestion completed | duration=%.1fs | sources_ok=%s/%s | fetched=%s | upserted=%s | "
            "embedded=%s | active_jobs=%s | fresh_jobs=%s | freshness_days=%s",
            elapsed,
            totals["sources_ok"],
            totals["sources_started"],
            totals["fetched"],
            totals["upserted"],
            embedded,
            inventory["active_jobs"],
            inventory["fresh_jobs"],
            get_settings().freshness_days,
        )


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
        asyncio.run(run_ingest(sources=args.sources, embed=do_embed))
    elif args.command == "embed":

        async def _embed() -> None:
            async with AsyncSessionLocal() as session:
                n = await maybe_embed_missing(session, limit=args.limit)
                logger.info("Embed CLI finished | embedded=%s", n)

        asyncio.run(_embed())


if __name__ == "__main__":
    main()
