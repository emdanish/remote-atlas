"""Race-safe production entry points for the API and scheduled ingestion."""

from __future__ import annotations

import argparse
import logging
import os
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


def exec_cron(embed: bool) -> None:
    """One-shot ingestion for Render Cron Jobs. Process must exit when finished."""
    arguments = [sys.executable, "-m", "app.scheduler", "--once"]
    if embed:
        arguments.append("--embed")
    os.execvp(sys.executable, arguments)


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
        help="Also embed this cycle (off by default; FTS still works)",
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
