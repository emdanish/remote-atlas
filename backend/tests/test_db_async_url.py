"""Neon / asyncpg URL preparation for hosted Postgres."""

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
    assert extras["connect_args"]["ssl"] is True
    assert extras["connect_args"]["statement_cache_size"] == 0


def test_prepare_async_local_has_no_ssl_requirement():
    cleaned, extras = prepare_async_database_url(
        "postgresql+asyncpg://postgres:postgres@localhost:5432/remote_atlas"
    )
    assert "localhost" in cleaned
    assert extras == {} or "ssl" not in extras.get("connect_args", {})
