#!/usr/bin/env python3
"""Demonstrate Gemini embed path stays far under Render 512Mi (no ONNX).

Usage (from backend/):
  python scripts/bench_embed_memory.py

This does not call the Gemini API. It proves the production code path never
imports onnxruntime/fastembed, and reports RSS after importing the embed stack.
"""

from __future__ import annotations

import os
import sys
import tracemalloc

# Force production-like provider before importing app modules
os.environ.setdefault("EMBED_PROVIDER", "gemini")
os.environ.setdefault("GEMINI_API_KEY_1", "bench-placeholder-not-used")

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)


def _rss_mb() -> float | None:
    try:
        import psutil  # optional

        return psutil.Process().memory_info().rss / (1024 * 1024)
    except Exception:
        return None


def main() -> int:
    tracemalloc.start()
    rss0 = _rss_mb()

    from app.ai.provider import embedding_provider_name, embed_texts  # noqa: F401
    from app.search.embed_pipeline import EmbedPassStats, maybe_embed_missing  # noqa: F401

    name = embedding_provider_name()
    assert name == "gemini:embedding-001", name

    banned = [m for m in sys.modules if "onnxruntime" in m or m.split(".")[0] == "fastembed"]
    current, peak = tracemalloc.get_traced_memory()
    rss1 = _rss_mb()

    print("provider:", name)
    print("banned_modules_loaded:", banned or "none")
    print(f"tracemalloc_current_mb: {current / (1024 * 1024):.1f}")
    print(f"tracemalloc_peak_mb: {peak / (1024 * 1024):.1f}")
    if rss0 is not None and rss1 is not None:
        print(f"rss_before_mb: {rss0:.1f}")
        print(f"rss_after_import_mb: {rss1:.1f}")
        print(f"rss_delta_mb: {rss1 - rss0:.1f}")
        # Hard safety: stay well under 512 with margin for crawl leftover N/A
        # (embed runs in a fresh process). Import stack alone should be << 200Mi.
        if rss1 > 250:
            print("FAIL: RSS after Gemini stack import exceeds 250Mi safety budget")
            return 1
    else:
        print("rss: psutil not installed (pip install psutil for RSS); tracemalloc only")

    if banned:
        print("FAIL: ONNX/fastembed imported on Gemini path")
        return 1

    print("OK: Gemini embed architecture stays clear of ONNX and within budget")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
