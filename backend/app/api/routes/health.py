from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.config import get_settings
from app.pipeline.freshness import freshness_cutoff
from app.schemas import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health(db: AsyncSession = Depends(get_db)) -> HealthResponse:
    """Liveness probe. Always reachable if the process is up; database status is reported separately."""
    try:
        await db.execute(text("SELECT 1"))
        return HealthResponse(status="ok", database="ok")
    except Exception:  # noqa: BLE001
        return HealthResponse(status="degraded", database="error")


@router.get("/health/ready", response_model=HealthResponse)
async def readiness(db: AsyncSession = Depends(get_db)) -> HealthResponse:
    """Return a failing status code when the API cannot serve database-backed traffic."""
    try:
        await db.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001
        # Log type/message only — never the connection string
        import logging

        logging.getLogger("health").error(
            "readiness database check failed: %s: %s", type(exc).__name__, exc
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database unavailable",
        ) from exc
    return HealthResponse(status="ok", database="ok")


@router.get("/health/ingest")
async def ingest_health(db: AsyncSession = Depends(get_db)) -> dict:
    """Source health + inventory snapshot for operators."""
    settings = get_settings()
    cutoff = freshness_cutoff(settings.freshness_days)
    from app.ai.provider import embedding_provider_name

    embedding_provider = embedding_provider_name()
    inventory = (
        await db.execute(
            text(
                """
                SELECT
                  count(*) AS total_jobs,
                  count(*) FILTER (WHERE is_active) AS active_jobs,
                  count(*) FILTER (
                    WHERE is_active AND (
                      posted_at >= :cutoff
                      OR (posted_at IS NULL AND first_seen_at >= :cutoff)
                    )
                  ) AS fresh_jobs,
                  count(*) FILTER (
                    WHERE is_active AND embedding IS NOT NULL
                      AND embedding_provider = :embedding_provider
                  ) AS embedded_jobs,
                  count(DISTINCT source) FILTER (WHERE is_active) AS active_sources,
                  count(DISTINCT company_name) FILTER (WHERE is_active) AS indexed_companies
                FROM jobs
                """
            ),
            {"cutoff": cutoff, "embedding_provider": embedding_provider},
        )
    ).mappings().one()
    companies = (
        await db.execute(
            text(
                """
                SELECT
                  count(*) FILTER (WHERE is_enabled) AS enabled_companies,
                  count(*) FILTER (WHERE region_focus IN ('pakistan','both')) AS pk_companies,
                  count(DISTINCT ats_type) FILTER (WHERE is_enabled) AS ats_integrations
                FROM companies
                """
            )
        )
    ).mappings().one()
    sources = (
        await db.execute(
            text(
                """
                SELECT source,
                       max(started_at) AS last_run,
                       max(jobs_fetched) FILTER (WHERE started_at = (
                         SELECT max(started_at) FROM ingest_runs ir2 WHERE ir2.source = ingest_runs.source
                       )) AS last_fetched,
                       bool_or(errors IS NOT NULL AND errors <> '') FILTER (WHERE started_at > NOW() - INTERVAL '24 hours') AS had_errors_24h
                FROM ingest_runs
                GROUP BY source
                ORDER BY last_run DESC NULLS LAST
                """
            )
        )
    ).mappings().all()
    return {
        "freshness_days": settings.freshness_days,
        "inventory": dict(inventory),
        "companies": dict(companies),
        "sources": [dict(r) for r in sources],
    }
