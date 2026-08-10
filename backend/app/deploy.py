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


def migrate() -> None:
    """Serialize Alembic migrations when multiple Render services start together."""
    settings = get_settings()
    if settings.jwt_secret.startswith("change-me"):
        logger.warning(
            "JWT_SECRET still uses the insecure default placeholder. "
            "Set a long random value before serving real users."
        )
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


def _low_ram_env() -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("OMP_NUM_THREADS", "1")
    env.setdefault("MKL_NUM_THREADS", "1")
    env.setdefault("OPENBLAS_NUM_THREADS", "1")
    env.setdefault("NUMEXPR_NUM_THREADS", "1")
    env.setdefault("ORT_NUM_THREADS", "1")
    env.setdefault("TOKENIZERS_PARALLELISM", "false")
    return env


def _run_step(label: str, arguments: list[str]) -> int:
    logger.info("Starting step: %s | cmd=%s", label, " ".join(arguments))
    completed = subprocess.run(arguments, env=_low_ram_env(), check=False)
    if completed.returncode != 0:
        logger.error("Step failed: %s | exit_code=%s", label, completed.returncode)
    else:
        logger.info("Step finished: %s | exit_code=0", label)
    return completed.returncode


def exec_cron(embed: bool) -> None:
    """One-shot ingestion for Render Cron Jobs with process isolation.

    Critical: crawl + ONNX embedding in the *same* process OOMs 512Mi dynos
    (ingest alone used most of the heap; loading BGE then fails). Run:

    1. crawl/housekeeping as process A (exits → OS reclaims memory)
    2. embed as process B (fresh heap for the model)

    Jobs stay fully searchable via FTS if embeds fail or partial.
    """
    crawl_code = _run_step(
        "ingest",
        [sys.executable, "-m", "app.scheduler", "--once", "--ingest-only"],
    )
    if crawl_code != 0:
        sys.exit(crawl_code)

    if not embed:
        sys.exit(0)

    embed_code = _run_step(
        "embed",
        [sys.executable, "-m", "app.ingest", "embed"],
    )
    # Non-zero embed should not hide successful crawl for monitoring, but
    # we still fail the cron so Render re-tries / alerts. FTS works either way.
    if embed_code != 0:
        sys.exit(embed_code)
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
