"""Provider chain must fail over when one API key/model errors."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.ai.provider import AIProviderError, chat_completion


@pytest.mark.asyncio
async def test_chat_completion_prefers_deepseek_before_gemini():
    calls: list[str] = []

    async def fake_gemini(api_key, system, user, temperature, max_tokens, *, model=""):
        calls.append(f"gemini:{api_key}:{model}")
        return "should-not-run"

    async def fake_openai(**kwargs):
        calls.append(f"openai:{kwargs.get('model')}")
        return "ok-from-deepseek"

    with (
        patch("app.ai.provider.get_settings") as gs,
        patch("app.ai.provider._gemini_chat", side_effect=fake_gemini),
        patch("app.ai.provider._openai_compatible_chat", side_effect=fake_openai),
    ):
        settings = gs.return_value
        settings.gemini_keys = ["key-a", "key-b"]
        settings.deepseek_api_key = "deep-key"
        settings.perplexity_api_key = ""

        text = await chat_completion(system="sys", user="hi", max_tokens=32)

    assert text == "ok-from-deepseek"
    assert "openai:deepseek-chat" in calls
    assert not any(c.startswith("gemini:") for c in calls)


@pytest.mark.asyncio
async def test_chat_completion_uses_second_gemini_when_first_fails():
    async def fake_gemini(api_key, system, user, temperature, max_tokens, *, model=""):
        if api_key == "key-a":
            raise AIProviderError("HTTP 429: rate limited")
        return f"ok:{api_key}:{model}"

    with (
        patch("app.ai.provider.get_settings") as gs,
        patch("app.ai.provider._gemini_chat", side_effect=fake_gemini),
    ):
        settings = gs.return_value
        settings.gemini_keys = ["key-a", "key-b"]
        settings.deepseek_api_key = ""
        settings.perplexity_api_key = ""

        text = await chat_completion(system="sys", user="hi", max_tokens=32)

    assert text.startswith("ok:key-b:")


@pytest.mark.asyncio
async def test_chat_completion_errors_when_all_providers_fail():
    with (
        patch("app.ai.provider.get_settings") as gs,
        patch(
            "app.ai.provider._gemini_chat",
            new=AsyncMock(side_effect=AIProviderError("HTTP 500")),
        ),
        patch(
            "app.ai.provider._openai_compatible_chat",
            new=AsyncMock(side_effect=AIProviderError("HTTP 500")),
        ),
    ):
        settings = gs.return_value
        settings.gemini_keys = ["k1"]
        settings.deepseek_api_key = "d"
        settings.perplexity_api_key = "p"

        with pytest.raises(AIProviderError, match="All AI providers failed"):
            await chat_completion(system="sys", user="hi")
