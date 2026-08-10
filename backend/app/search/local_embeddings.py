"""Local embedding (BGE-base 768-d) tuned for small RAM cron dynos.

Render free/starter plan often has only 512Mi. Loading ONNX after a full crawl
OOMs the same process. Cron therefore embeds in a *fresh* subprocess; this
module still stays minimal: 1 thread, small batches, optional model unload.
"""

from __future__ import annotations

import asyncio
import gc
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

# Keep 768-d model so hybrid search vectors stay compatible with pgvector schema.
_MODEL_NAME = "BAAI/bge-base-en-v1.5"
_model = None


def _apply_runtime_thread_limits() -> None:
    """Reduce ONNX / BLAS / tokenizer parallelism (huge win under 512Mi)."""
    os.environ.setdefault("OMP_NUM_THREADS", "1")
    os.environ.setdefault("MKL_NUM_THREADS", "1")
    os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
    os.environ.setdefault("NUMEXPR_NUM_THREADS", "1")
    os.environ.setdefault("ORT_NUM_THREADS", "1")
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")


def _get_model():
    global _model
    if _model is not None:
        return _model
    _apply_runtime_thread_limits()
    try:
        from fastembed import TextEmbedding
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "fastembed is not installed. Run: pip install fastembed"
        ) from exc
    logger.info(
        "Loading local embedding model %s (threads=1, low-RAM mode)",
        _MODEL_NAME,
    )
    # threads=1 prevents multi-threaded ORT from ballooning RSS on small dynos
    try:
        _model = TextEmbedding(model_name=_MODEL_NAME, threads=1)
    except TypeError:
        # Older fastembed without threads kwarg
        _model = TextEmbedding(model_name=_MODEL_NAME)
    return _model


def unload_local_model() -> None:
    """Drop model reference so RSS can shrink (next call reloads)."""
    global _model
    _model = None
    gc.collect()


def local_embed_sync(texts: list[str], *, batch_size: int = 4) -> list[list[float]]:
    if not texts:
        return []
    model = _get_model()
    # Small batch_size keeps peak ONNX / allocator overhead down.
    try:
        vectors = list(model.embed(texts, batch_size=max(1, batch_size)))
    except TypeError:
        vectors = list(model.embed(texts))
    return [list(map(float, v)) for v in vectors]


async def local_embed_texts(texts: list[str], *, batch_size: int = 4) -> list[list[float]]:
    return await asyncio.to_thread(local_embed_sync, texts, batch_size=batch_size)


def local_available() -> bool:
    try:
        import fastembed  # noqa: F401

        return True
    except ImportError:
        return False
