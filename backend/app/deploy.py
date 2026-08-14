"""Race-safe production entry points for the API and scheduled ingestion."""

from __future__ import annotations

import argparse
import logging
import os
import subprocess
import sys

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool

from app.config import BACKEND_ROOT, get_settings

logger = logging.getLogger("deploy")
MIGRATION_LOCK_ID = 7_245_109_391


def assert_production_jwt() -> None:
    """Fail closed on Render if JWT_SECRET is the placeholder or too short."""
    settings = get_settings()
    secret = (settings.jwt_secret or "").strip()
    on_render = bool(os.environ.get("RENDER"))
    weak = secret.startswith("change-me") or len(secret) < 32
    if on_render and weak:
        logger.error(
            "JWT_SECRET is the default placeholder or shorter than 32 characters. "
            "Refusing to start on Render."
        )
        sys.exit(1)
    if weak:
        logger.warning(
            "JWT_SECRET still uses the insecure default placeholder. "
            "Set a long random value before serving real users."
        )


def migrate() -> None:
    """Serialize Alembic migrations when multiple Render services start together."""
    settings = get_settings()
    assert_production_jwt()
    engine = create_engine(settings.database_url_sync, poolclass=NullPool)
    try:
        with engine.connect() as connection:
            logger.info("Waiting for the database migration lock")
            connection.execute(
                text("SELECT pg_advisory_lock(:lock_id)"),
                {"lock_id": MIGRATION_LOCK_ID},
            )
            try:
                config = Config(str(BACKEND_ROOT / "alembic.ini"))
                config.set_main_option("sqlalchemy.url", settings.database_url_sync)
                command.upgrade(config, "head")
            finally:
                connection.execute(
                    text("SELECT pg_advisory_unlock(:lock_id)"),
                    {"lock_id": MIGRATION_LOCK_ID},
                )
                connection.commit()
    finally:
        engine.dispose()


def exec_web() -> None:
    port = os.environ.get("PORT", "8000")
    os.execvp(
        "uvicorn",
        [
            "uvicorn",
            "app.main:app",
            "--host",
            "0.0.0.0",
            "--port",
            port,
            "--proxy-headers",
            "--forwarded-allow-ips=*",
        ],
    )


def exec_worker(interval_minutes: int, embed: bool) -> None:
    """Legacy always-on loop. Prefer `cron` for daily schedules on Render."""
    arguments = [
        sys.executable,
        "-m",
        "app.scheduler",
        "--interval-minutes",
        str(interval_minutes),
    ]
    if embed:
        arguments.append("--embed")
    os.execvp(sys.executable, arguments)


def _run_step(label: str, arguments: list[str]) -> int:
    logger.info("Starting step: %s | cmd=%s", label, " ".join(arguments))
    completed = subprocess.run(arguments, env=os.environ.copy(), check=False)
    if completed.returncode != 0:
        logger.error("Step failed: %s | exit_code=%s", label, completed.returncode)
    else:
        logger.info("Step finished: %s | exit_code=0", label)
    return completed.returncode


def exec_cron(embed: bool) -> None:
    """One-shot ingestion for Render Cron Jobs with failure isolation.

    Pipeline:
      1. crawl + housekeeping (+ pulse alerts) as process A
      2. incremental embeddings as process B (Gemini HTTP — no ONNX)

    Ingestion success is independent of embedding success. Jobs remain
    searchable via PostgreSQL FTS if embeds fail or are partial. The cron
    exits 0 after a successful ingest so Render does not mark the whole
    job index refresh as failed when only embeddings error (e.g. quota).
    """
    crawl_code = _run_step(
        "ingest",
        [sys.executable, "-m", "app.scheduler", "--once", "--ingest-only"],
    )
    if crawl_code != 0:
        logger.error("INGESTION STATUS = FAILED | exit_code=%s", crawl_code)
        sys.exit(crawl_code)

    logger.info("INGESTION STATUS = SUCCESS")

    if not embed:
        logger.info("EMBEDDING STATUS = SKIPPED")
        sys.exit(0)

    embed_code = _run_step(
        "embed",
        [sys.executable, "-m", "app.ingest", "embed"],
    )
    if embed_code != 0:
        # Soft-fail: index is already fresh; next cron resumes embed backlog.
        logger.error(
            "EMBEDDING STATUS = FAILED | exit_code=%s | "
            "ingest already succeeded — jobs searchable via FTS; "
            "next run resumes incremental embeddings",
            embed_code,
        )
        sys.exit(0)

    logger.info("EMBEDDING STATUS = SUCCESS")
    sys.exit(0)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Remote Atlas production launcher")
    subparsers = parser.add_subparsers(dest="service", required=True)
    subparsers.add_parser("web")
    worker = subparsers.add_parser("worker", help="Always-on loop (higher cost)")
    worker.add_argument("--interval-minutes", type=int, default=180)
    worker.add_argument("--embed", action="store_true")
    cron = subparsers.add_parser("cron", help="One-shot run for Render Cron Jobs")
    cron.add_argument(
        "--embed",
        action="store_true",
        help="After crawl, run embeddings in a separate process (recommended)",
    )
    args = parser.parse_args()

    migrate()
    if args.service == "web":
        exec_web()
    elif args.service == "cron":
        exec_cron(args.embed)
    else:
        exec_worker(args.interval_minutes, args.embed)


if __name__ == "__main__":
    main()
