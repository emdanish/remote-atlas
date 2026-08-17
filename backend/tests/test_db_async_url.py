"""Hosted Postgres / asyncpg URL preparation."""

import ssl

from app.db.session import prepare_async_database_url


def test_prepare_async_strips_libpq_params_and_sets_pooler_flags():
    url = (
        "postgresql+asyncpg://u:p@ep-x-pooler.c-3.ap-southeast-1.aws.neon.tech/neondb"
        "?sslmode=require&channel_binding=require"
    )
    cleaned, extras = prepare_async_database_url(url)
    assert "sslmode" not in cleaned
    assert "channel_binding" not in cleaned
    assert "neondb" in cleaned
    ssl_ctx = extras["connect_args"]["ssl"]
    assert isinstance(ssl_ctx, ssl.SSLContext)
    assert ssl_ctx.verify_mode == ssl.CERT_NONE
    assert extras["connect_args"]["statement_cache_size"] == 0


def test_prepare_async_aiven_sets_require_tls():
    url = (
        "postgresql+asyncpg://avnadmin:x@pg-x-remote-atlas.k.aivencloud.com:20970/defaultdb"
        "?sslmode=require"
    )
    cleaned, extras = prepare_async_database_url(url)
    assert "sslmode" not in cleaned
    ssl_ctx = extras["connect_args"]["ssl"]
    assert isinstance(ssl_ctx, ssl.SSLContext)
    assert "statement_cache_size" not in extras["connect_args"]


def test_prepare_async_local_has_no_ssl_requirement():
    cleaned, extras = prepare_async_database_url(
        "postgresql+asyncpg://postgres:postgres@localhost:5432/remote_atlas"
    )
    assert "localhost" in cleaned
    assert extras == {} or "ssl" not in extras.get("connect_args", {})
