"""Async SQLAlchemy engine + session factory.

Hosted Postgres (Neon, Aiven, Render) needs extra care with asyncpg:
- strip libpq-only query params (sslmode, channel_binding)
- use an SSL context that matches sslmode=require (encrypt; Aiven's project CA
  is not in the public trust store, so full verify would fail)
- set statement_cache_size=0 for transaction-mode poolers (-pooler host)
"""

from __future__ import annotations

import logging
import ssl
from collections.abc import AsyncGenerator
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings

logger = logging.getLogger(__name__)


def _require_tls_context() -> ssl.SSLContext:
    """TLS for sslmode=require: encrypt traffic, do not demand a public CA."""
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx

# Query keys understood by libpq / Neon UI, not by asyncpg via SQLAlchemy URL
_ASYNCPG_STRIP_QUERY_KEYS = {
    "sslmode",
    "ssl",
    "channel_binding",
    "channelbinding",
}


def prepare_async_database_url(url: str) -> tuple[str, dict[str, Any]]:
    """
    Return (cleaned_url, create_async_engine kwargs extras).

    Callers should merge connect_args from the second dict into create_async_engine.
    """
    raw = (url or "").strip()
    if not raw:
        return raw, {}

    parsed = urlparse(raw)
    host = (parsed.hostname or "").lower()
    is_local = host in {"localhost", "127.0.0.1", "::1"} or host.endswith(".local")

    # Drop query params that make asyncpg fail with Neon pooled strings
    query_pairs = [
        (k, v)
        for k, v in parse_qsl(parsed.query, keep_blank_values=True)
        if k.lower() not in _ASYNCPG_STRIP_QUERY_KEYS
    ]
    cleaned = urlunparse(parsed._replace(query=urlencode(query_pairs)))

    connect_args: dict[str, Any] = {}
    if not is_local:
        # asyncpg ignores sslmode= in the URL; this matches libpq sslmode=require
        connect_args["ssl"] = _require_tls_context()

    # Neon / PgBouncer transaction poolers break prepared statement caching
    if "pooler" in host or host.endswith(".neon.tech"):
        connect_args["statement_cache_size"] = 0
        logger.info(
            "Async DB: Neon/pooler host detected — ssl=%s statement_cache_size=0",
            connect_args.get("ssl"),
        )

    return cleaned, {"connect_args": connect_args} if connect_args else {}


settings = get_settings()
_async_url, _engine_extras = prepare_async_database_url(settings.database_url)

engine = create_async_engine(
    _async_url,
    echo=False,
    pool_pre_ping=True,
    pool_size=settings.database_pool_size,
    max_overflow=settings.database_max_overflow,
    **_engine_extras,
)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
