"""Local embedding fallback (no Gemini quota). Uses FastEmbed BGE-base (768-d)."""

from __future__ import annotations

import asyncio
import logging
from functools import lru_cache
from typing import Optional

logger = logging.getLogger(__name__)

_MODEL_NAME = "BAAI/bge-base-en-v1.5"


@lru_cache(maxsize=1)
def _local_model():
    try:
        from fastembed import TextEmbedding
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "fastembed is not installed. Run: pip install fastembed"
        ) from exc
    logger.info("Loading local embedding model %s (first run may download)", _MODEL_NAME)
    return TextEmbedding(model_name=_MODEL_NAME)


def local_embed_sync(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    model = _local_model()
    vectors = list(model.embed(texts))
    return [list(map(float, v)) for v in vectors]


async def local_embed_texts(texts: list[str]) -> list[list[float]]:
    return await asyncio.to_thread(local_embed_sync, texts)


def local_available() -> bool:
    try:
        import fastembed  # noqa: F401

        return True
    except ImportError:
        return False
