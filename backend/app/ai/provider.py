"""AI chat providers with ordered key/provider fallback.

Order: Gemini key 1 → Gemini key 2 → DeepSeek → Perplexity.

Any single quota/auth/network failure must continue to the next option.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)


class AIProviderError(RuntimeError):
    pass


# Prefer cheap/fast then solid fallbacks. A missing model id is treated as retry-next.
_GEMINI_CHAT_MODELS = (
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
    "gemini-1.5-flash",
    "gemini-1.5-flash-8b",
)


def embedding_provider_name() -> str | None:
    """Resolve one vector space before embedding; mixed vectors are invalid."""
    settings = get_settings()
    mode = (settings.embed_provider or "auto").lower().strip()
    # Web free-tier: never load ONNX / BGE in-process
    if mode in {"none", "off", "fts", "disabled", "false", "0"}:
        return None
    if mode == "local":
        from app.search.local_embeddings import local_available

        return "local:bge-base-en-v1.5" if local_available() else None
    if mode == "gemini":
        return "gemini:embedding-001" if settings.gemini_keys else None
    from app.search.local_embeddings import local_available

    if local_available():
        return "local:bge-base-en-v1.5"
    return "gemini:embedding-001" if settings.gemini_keys else None


async def chat_completion(
    *,
    system: str,
    user: str,
    temperature: float = 0.2,
    max_tokens: int = 1024,
) -> str:
    """
    Secure server-side chat with provider fallback.
    Order: Gemini key1 → Gemini key2 → DeepSeek → Perplexity.
    API keys never leave the backend process.
    """
    settings = get_settings()
    errors: list[str] = []

    gemini_keys = settings.gemini_keys
    if not gemini_keys and not settings.deepseek_api_key and not settings.perplexity_api_key:
        raise AIProviderError("No API keys configured for chat providers")

    for idx, key in enumerate(gemini_keys, start=1):
        last_for_key: Exception | None = None
        for model in _GEMINI_CHAT_MODELS:
            try:
                text = await _gemini_chat(key, system, user, temperature, max_tokens, model=model)
                logger.info("chat_completion succeeded via gemini_%s model=%s", idx, model)
                return text
            except Exception as exc:  # noqa: BLE001
                last_for_key = exc
                msg = f"gemini_{idx}/{model}: {exc}"
                logger.warning("AI fallback — %s", msg)
                errors.append(msg)
                # Don't thrash every model on hard auth failure
                if _is_auth_failure(exc):
                    break
        if last_for_key is not None and not _is_auth_failure(last_for_key):
            # Key was usable but models failed (rate limit etc.) — try next key
            continue

    if settings.deepseek_api_key:
        try:
            text = await _openai_compatible_chat(
                api_key=settings.deepseek_api_key,
                base_url="https://api.deepseek.com",
                model="deepseek-chat",
                system=system,
                user=user,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            logger.info("chat_completion succeeded via deepseek")
            return text
        except Exception as exc:  # noqa: BLE001
            msg = f"deepseek: {exc}"
            logger.warning("AI fallback — %s", msg)
            errors.append(msg)

    if settings.perplexity_api_key:
        try:
            text = await _openai_compatible_chat(
                api_key=settings.perplexity_api_key,
                base_url="https://api.perplexity.ai",
                model="sonar",
                system=system,
                user=user,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            logger.info("chat_completion succeeded via perplexity")
            return text
        except Exception as exc:  # noqa: BLE001
            msg = f"perplexity: {exc}"
            logger.warning("AI fallback — %s", msg)
            errors.append(msg)

    raise AIProviderError(
        "All AI providers failed: " + ("; ".join(errors) if errors else "No API keys configured")
    )


def _is_auth_failure(exc: BaseException) -> bool:
    text = str(exc).lower()
    return any(
        tok in text
        for tok in (
            "401",
            "403",
            "api key not valid",
            "invalid api key",
            "permission_denied",
            "unauthenticated",
            "incorrect api key",
        )
    )


async def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed texts. Provider: gemini / local / auto / none (config)."""
    settings = get_settings()
    if not texts:
        return []

    mode = (settings.embed_provider or "auto").lower().strip()
    if mode in {"none", "off", "fts", "disabled", "false", "0"}:
        return []

    provider = embedding_provider_name()
    if provider == "local:bge-base-en-v1.5":
        from app.search.local_embeddings import local_embed_texts

        try:
            return await local_embed_texts(texts)
        except Exception as exc:  # noqa: BLE001
            logger.error("Local embedding failed (use FTS fallback): %s", exc)
            return []

    if provider == "gemini:embedding-001":
        last_error: Optional[Exception] = None
        for idx, key in enumerate(settings.gemini_keys, start=1):
            try:
                return await _gemini_embed(key, texts, settings.embedding_dimensions)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Embedding fallback — gemini_%s: %s", idx, exc)
                last_error = exc
        if last_error:
            logger.error("All Gemini embedding keys failed: %s", last_error)
        return []

    # auto: try local only when explicitly available and mode is auto
    if mode == "auto":
        try:
            from app.search.local_embeddings import local_available, local_embed_texts

            if local_available():
                logger.info("Using local embeddings (auto)")
                return await local_embed_texts(texts)
        except Exception as exc:  # noqa: BLE001
            logger.error("Local embedding failed: %s", exc)
    return []


async def _gemini_chat(
    api_key: str,
    system: str,
    user: str,
    temperature: float,
    max_tokens: int,
    *,
    model: str = "gemini-2.0-flash",
) -> str:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    payload: dict[str, Any] = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": user}]}],
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_tokens,
        },
    }
    async with httpx.AsyncClient(timeout=90.0) as client:
        resp = await client.post(url, params={"key": api_key}, json=payload)
        if resp.status_code >= 400:
            detail = resp.text[:400]
            raise AIProviderError(f"HTTP {resp.status_code}: {detail}")
        data = resp.json()
    # Blocked / safety without candidates
    if data.get("promptFeedback", {}).get("blockReason"):
        raise AIProviderError(f"Gemini blocked: {data['promptFeedback']['blockReason']}")
    candidates = data.get("candidates") or []
    if not candidates:
        raise AIProviderError(f"Gemini empty response: {str(data)[:300]}")
    finish = (candidates[0] or {}).get("finishReason")
    parts = (((candidates[0] or {}).get("content") or {}).get("parts")) or []
    text = "".join(p.get("text", "") for p in parts if isinstance(p, dict))
    if not text.strip():
        raise AIProviderError(f"Gemini returned empty text (finish={finish})")
    return text.strip()


async def _gemini_embed(api_key: str, texts: list[str], dim: int) -> list[list[float]]:
    """Batch-embed via Gemini REST batchEmbedContents (many texts per HTTP call)."""

    async def _embed_chunk(chunk: list[str]) -> list[list[float]]:
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            "gemini-embedding-001:batchEmbedContents"
        )
        requests = []
        for text in chunk:
            truncated = (text or "")[:6000]
            if not truncated.strip():
                truncated = " "
            requests.append(
                {
                    "model": "models/gemini-embedding-001",
                    "content": {"parts": [{"text": truncated}]},
                    "outputDimensionality": dim,
                }
            )
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                url,
                params={"key": api_key},
                json={"requests": requests},
            )
            if resp.status_code >= 400:
                raise AIProviderError(f"HTTP {resp.status_code}: {resp.text[:300]}")
            data = resp.json()
        embeddings = data.get("embeddings") or []
        out: list[list[float]] = []
        for i, text in enumerate(chunk):
            if not (text or "").strip():
                out.append([0.0] * dim)
                continue
            emb = embeddings[i] if i < len(embeddings) else None
            values = (emb or {}).get("values") if isinstance(emb, dict) else None
            if not values:
                raise AIProviderError("Empty embedding in batch")
            out.append(list(values)[:dim])
        return out

    chunk_size = 48
    vectors: list[list[float]] = []
    for i in range(0, len(texts), chunk_size):
        chunk = texts[i : i + chunk_size]
        vectors.extend(await _embed_chunk(chunk))
    return vectors


async def _openai_compatible_chat(
    *,
    api_key: str,
    base_url: str,
    model: str,
    system: str,
    user: str,
    temperature: float,
    max_tokens: int,
) -> str:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    async with httpx.AsyncClient(timeout=90.0, base_url=base_url) as client:
        resp = await client.post("/chat/completions", headers=headers, json=payload)
        if resp.status_code >= 400:
            raise AIProviderError(f"HTTP {resp.status_code}: {resp.text[:300]}")
        data = resp.json()
    choices = data.get("choices") or []
    if not choices:
        raise AIProviderError(f"{model} empty choices")
    content = ((choices[0].get("message") or {}).get("content")) or ""
    if not str(content).strip():
        raise AIProviderError(f"{model} empty content")
    return str(content).strip()
