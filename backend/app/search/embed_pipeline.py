"""Incremental, memory-bounded job embedding pipeline.

Designed for Render Starter cron (512 MiB): production uses Gemini HTTP
embeddings (768-d), never FastEmbed/ONNX on that dyno. Local BGE remains
available when EMBED_PROVIDER=local on machines with enough RAM.
"""

from __future__ import annotations

import asyncio
import gc
import logging
import time
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import load_only

from app.config import get_settings
from app.pipeline.freshness import freshness_cutoff
from app.search.embeddings import job_embedding_document, job_embedding_hash

logger = logging.getLogger(__name__)


@dataclass
class EmbedPassStats:
    """Structured result for observability (ingest success ≠ embed success)."""

    status: str = "SKIPPED"  # SUCCESS | PARTIAL | FAILED | SKIPPED
    provider: str | None = None
    candidates: int = 0
    processed: int = 0
    skipped: int = 0
    failed: int = 0
    remaining: int = 0
    batch_size: int = 0
    chunk_size: int = 0
    duration_s: float = 0.0
    errors: list[str] = field(default_factory=list)

    @property
    def embedded(self) -> int:
        """Back-compat alias for callers expecting a count."""
        return self.processed


def _candidate_where(provider_name: str, cutoff):
    from app.models import Job

    return (
        Job.is_active.is_(True),
        Job.apply_url.is_not(None),
        or_(
            Job.posted_at >= cutoff,
            (Job.posted_at.is_(None)) & (Job.first_seen_at >= cutoff),
        ),
        or_(
            Job.embedding.is_(None),
            Job.embedding_hash.is_(None),
            Job.embedding_provider.is_(None),
            Job.embedding_provider != provider_name,
        ),
    )


async def count_embed_candidates(session: AsyncSession, provider_name: str) -> int:
    from app.models import Job

    settings = get_settings()
    cutoff = freshness_cutoff(settings.freshness_days)
    result = await session.execute(
        select(func.count())
        .select_from(Job)
        .where(*_candidate_where(provider_name, cutoff))
    )
    return int(result.scalar_one() or 0)


async def maybe_embed_missing(
    session: AsyncSession,
    limit: int | None = None,
) -> EmbedPassStats:
    """Embed jobs missing/stale vectors in bounded waves; resumeable across runs."""
    settings = get_settings()
    stats = EmbedPassStats(
        batch_size=settings.embed_batch_size,
        chunk_size=settings.embed_chunk_size,
    )
    t0 = time.perf_counter()

    from app.ai.provider import embedding_provider_name, embed_texts

    provider_name = embedding_provider_name()
    stats.provider = provider_name
    mode = (settings.embed_provider or "auto").lower().strip()

    if mode in {"none", "off", "fts", "disabled", "false", "0"}:
        logger.info("EMBED_PROVIDER=%s — skipping embeddings (FTS still works)", mode)
        stats.status = "SKIPPED"
        stats.duration_s = time.perf_counter() - t0
        _log_pass(stats)
        return stats

    if not provider_name:
        if mode == "gemini":
            logger.error(
                "EMBED_PROVIDER=gemini but no GEMINI_API_KEY_* configured; "
                "skipping embeddings (FTS still works)"
            )
            stats.status = "FAILED"
            stats.errors.append("no_gemini_keys")
        elif mode == "local":
            logger.error(
                "EMBED_PROVIDER=local but fastembed is not installed; skipping"
            )
            stats.status = "FAILED"
            stats.errors.append("local_unavailable")
        else:
            logger.info("No configured embedding provider; skipping embeddings")
            stats.status = "SKIPPED"
        stats.duration_s = time.perf_counter() - t0
        _log_pass(stats)
        return stats

    if mode == "local":
        logger.warning(
            "EMBED_PROVIDER=local loads BGE/ONNX in-process; this OOMs Render "
            "512Mi cron. Prefer EMBED_PROVIDER=gemini for production."
        )

    # Never load local ONNX as a Gemini fallback — that is what OOMs production.
    use_local = provider_name.startswith("local:")
    max_jobs = limit if limit is not None else settings.embed_max_per_run
    wave = max(8, min(settings.embed_batch_size, max_jobs))
    chunk = max(1, settings.embed_chunk_size)
    stats.batch_size = wave
    stats.chunk_size = chunk
    cutoff = freshness_cutoff(settings.freshness_days)
    consecutive_fail = 0
    max_fail = settings.embed_max_consecutive_failures

    from app.models import Job

    stats.candidates = await count_embed_candidates(session, provider_name)
    logger.info(
        "EMBEDDING start | provider=%s | candidates=%s | cap=%s | batch=%s | chunk=%s",
        provider_name,
        stats.candidates,
        max_jobs,
        wave,
        chunk,
    )

    while stats.processed < max_jobs:
        remaining_cap = max_jobs - stats.processed
        batch_limit = min(wave, remaining_cap)
        id_result = await session.execute(
            select(Job.id)
            .where(*_candidate_where(provider_name, cutoff))
            .order_by(Job.last_seen_at.desc())
            .limit(batch_limit)
        )
        ids = [row[0] for row in id_result.all()]
        if not ids:
            break

        jobs_result = await session.execute(
            select(Job)
            .options(
                load_only(
                    Job.id,
                    Job.title,
                    Job.company_name,
                    Job.skills,
                    Job.career_stage,
                    Job.workplace_type,
                    Job.description_text,
                    Job.embedding,
                    Job.embedding_hash,
                    Job.embedding_provider,
                )
            )
            .where(Job.id.in_(ids))
        )
        jobs = list(jobs_result.scalars().all())
        if not jobs:
            break

        docs: list[str] = []
        hashes: list[str] = []
        eligible: list[Any] = []
        wave_failed = 0

        for job in jobs:
            h = job_embedding_hash(
                job.title,
                job.company_name,
                job.skills or [],
                job.career_stage,
                job.workplace_type,
                job.description_text,
            )
            # Same content + same vector space → skip (idempotent).
            # Different provider ⇒ must re-embed (never relabel foreign vectors).
            if (
                job.embedding is not None
                and job.embedding_hash == h
                and job.embedding_provider == provider_name
            ):
                stats.skipped += 1
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

        if not eligible:
            # Selected by SQL but all skipped after hash check — avoid spin.
            break

        wave_updated = 0
        for start in range(0, len(docs), chunk):
            end = min(start + chunk, len(docs))
            part = docs[start:end]
            try:
                if use_local:
                    from app.search.local_embeddings import local_embed_texts

                    vecs = await local_embed_texts(part, batch_size=chunk)
                else:
                    vecs = await embed_texts(part)
                if not vecs or len(vecs) != len(part):
                    raise RuntimeError(
                        f"embed returned {0 if not vecs else len(vecs)} vectors for {len(part)} texts"
                    )
                for i, v in enumerate(vecs):
                    job = eligible[start + i]
                    job.embedding = v
                    job.embedding_hash = hashes[start + i]
                    job.embedding_provider = provider_name
                    stats.processed += 1
                    wave_updated += 1
                consecutive_fail = 0
                await session.commit()
                if not use_local:
                    await asyncio.sleep(0.15)
            except Exception as exc:  # noqa: BLE001
                await session.rollback()
                msg = str(exc)
                stats.failed += len(part)
                wave_failed += len(part)
                consecutive_fail += 1
                err = f"slice {start}-{end}: {msg[:200]}"
                stats.errors.append(err)
                logger.warning("Embed %s", err)

                if "429" in msg or "Too Many" in msg or "RESOURCE_EXHAUSTED" in msg:
                    wait = min(60, 8 * consecutive_fail)
                    logger.warning(
                        "Embed rate-limited; sleeping %ss (streak %s/%s)",
                        wait,
                        consecutive_fail,
                        max_fail,
                    )
                    if consecutive_fail >= max_fail:
                        logger.error(
                            "Embedding rate-limit circuit open — stopping this pass early"
                        )
                        stats.status = "PARTIAL" if stats.processed else "FAILED"
                        stats.remaining = await count_embed_candidates(
                            session, provider_name
                        )
                        stats.duration_s = time.perf_counter() - t0
                        _unload_if_local(use_local)
                        _log_pass(stats)
                        return stats
                    await asyncio.sleep(wait)
                    continue

                # One bad slice must not kill the whole pass — skip ahead.
                if consecutive_fail >= max_fail:
                    logger.error(
                        "Too many consecutive embed failures — stopping this pass early"
                    )
                    stats.status = "PARTIAL" if stats.processed else "FAILED"
                    stats.remaining = await count_embed_candidates(session, provider_name)
                    stats.duration_s = time.perf_counter() - t0
                    _unload_if_local(use_local)
                    _log_pass(stats)
                    return stats

            if stats.processed and stats.processed % 64 == 0:
                logger.info(
                    "EMBEDDING progress | processed=%s | failed=%s | cap=%s",
                    stats.processed,
                    stats.failed,
                    max_jobs,
                )

        if wave_updated == 0 and wave_failed == 0:
            break

        del docs, hashes, eligible, jobs
        session.expire_all()
        gc.collect()

    _unload_if_local(use_local)
    stats.remaining = await count_embed_candidates(session, provider_name)
    stats.duration_s = time.perf_counter() - t0
    if stats.failed and stats.processed:
        stats.status = "PARTIAL"
    elif stats.failed and not stats.processed:
        stats.status = "FAILED"
    else:
        stats.status = "SUCCESS"
    _log_pass(stats)
    return stats


def _unload_if_local(use_local: bool) -> None:
    if not use_local:
        return
    try:
        from app.search.local_embeddings import unload_local_model

        unload_local_model()
    except Exception:  # noqa: BLE001
        pass


def _log_pass(stats: EmbedPassStats) -> None:
    throughput = (
        (stats.processed / stats.duration_s) if stats.duration_s > 0 and stats.processed else 0.0
    )
    logger.info(
        "EMBEDDING | status=%s | provider=%s | candidates=%s | processed=%s | "
        "skipped=%s | failed=%s | remaining=%s | batch_size=%s | chunk_size=%s | "
        "duration=%.1fs | throughput=%.1f/s",
        stats.status,
        stats.provider,
        stats.candidates,
        stats.processed,
        stats.skipped,
        stats.failed,
        stats.remaining,
        stats.batch_size,
        stats.chunk_size,
        stats.duration_s,
        throughput,
    )
    logger.info("EMBEDDING STATUS = %s", stats.status)


__all__ = [
    "EmbedPassStats",
    "count_embed_candidates",
    "maybe_embed_missing",
]
