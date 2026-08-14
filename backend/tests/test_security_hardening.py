from unittest.mock import patch

import pytest
from fastapi import HTTPException

from app.deploy import assert_production_jwt
from app.security.origin import cookie_mutation_allowed, origin_from_referer
from app.security.rate_limit import InMemoryRateLimiter, client_ip


class _Req:
    def __init__(self, headers, client_host="10.0.0.9"):
        self.headers = headers
        self.client = type("C", (), {"host": client_host})()


def test_cookie_mutation_requires_allowed_origin():
    allowed = {"https://remote-atlas.example"}
    assert cookie_mutation_allowed(
        origin="https://remote-atlas.example",
        referer=None,
        allowed=allowed,
    )
    assert not cookie_mutation_allowed(
        origin="https://evil.example",
        referer=None,
        allowed=allowed,
    )
    assert not cookie_mutation_allowed(origin=None, referer=None, allowed=allowed)
    assert cookie_mutation_allowed(
        origin=None,
        referer="https://remote-atlas.example/jobs/1",
        allowed=allowed,
    )
    assert origin_from_referer("https://remote-atlas.example/x") == "https://remote-atlas.example"


def test_client_ip_uses_last_forwarded_hop():
    req = _Req({"x-forwarded-for": "1.2.3.4, 10.1.1.8, 52.1.1.1"})
    assert client_ip(req) == "52.1.1.1"


def test_jwt_placeholder_exits_on_render(monkeypatch):
    monkeypatch.setenv("RENDER", "true")
    fake = type("S", (), {"jwt_secret": "change-me-in-production-remote-atlas"})()
    with patch("app.deploy.get_settings", return_value=fake):
        with pytest.raises(SystemExit):
            assert_production_jwt()


@pytest.mark.asyncio
async def test_rate_limiter_returns_429_after_cap():
    lim = InMemoryRateLimiter()
    await lim.check("ai:tailor", limit=2, period_seconds=3600)
    await lim.check("ai:tailor", limit=2, period_seconds=3600)
    with pytest.raises(HTTPException) as exc:
        await lim.check("ai:tailor", limit=2, period_seconds=3600)
    assert exc.value.status_code == 429
