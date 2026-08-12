"""Embedding architecture: provider selection, hash logic, pipeline isolation."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.search.embeddings import job_embedding_document, job_embedding_hash
from app.search.embed_pipeline import EmbedPassStats, maybe_embed_missing


def test_embedding_hash_stable_for_same_content():
    args = ("Engineer", "Acme", ["Python"], "mid", "remote", "Build APIs")
    assert job_embedding_hash(*args) == job_embedding_hash(*args)


def test_embedding_hash_changes_when_description_changes():
    a = job_embedding_hash("Eng", "Acme", ["Go"], "mid", "remote", "v1")
    b = job_embedding_hash("Eng", "Acme", ["Go"], "mid", "remote", "v2")
    assert a != b


def test_embedding_document_truncates_description():
    long = "x" * 5000
    doc = job_embedding_document("T", "C", ["s"], "mid", "remote", long)
    assert len(doc) < len(long) + 200
    assert "x" * 1500 in doc


def test_embedding_provider_prefers_gemini_in_auto():
    from app.ai.provider import embedding_provider_name

    with patch("app.ai.provider.get_settings") as gs:
        settings = gs.return_value
        settings.embed_provider = "auto"
        settings.gemini_keys = ["k1"]
        with patch("app.search.local_embeddings.local_available", return_value=True):
            assert embedding_provider_name() == "gemini:embedding-001"


def test_embedding_provider_local_only_when_explicit():
    from app.ai.provider import embedding_provider_name

    with patch("app.ai.provider.get_settings") as gs:
        settings = gs.return_value
        settings.embed_provider = "local"
        settings.gemini_keys = ["k1"]
        with patch("app.search.local_embeddings.local_available", return_value=True):
            assert embedding_provider_name() == "local:bge-base-en-v1.5"


def test_embedding_provider_none():
    from app.ai.provider import embedding_provider_name

    with patch("app.ai.provider.get_settings") as gs:
        settings = gs.return_value
        settings.embed_provider = "none"
        settings.gemini_keys = ["k1"]
        assert embedding_provider_name() is None


def test_exec_cron_soft_fails_embed_after_successful_ingest():
    from app.deploy import exec_cron

    codes = {"ingest": 0, "embed": 137}  # 137 = OOM-style kill

    def fake_run(label, arguments):
        if "scheduler" in " ".join(arguments):
            return codes["ingest"]
        return codes["embed"]

    def fake_exit(code=0):
        raise SystemExit(code)

    with (
        patch("app.deploy._run_step", side_effect=fake_run),
        patch("app.deploy.sys.exit", side_effect=fake_exit),
    ):
        with pytest.raises(SystemExit) as ei:
            exec_cron(embed=True)
        assert ei.value.code == 0


def test_exec_cron_fails_when_ingest_fails():
    from app.deploy import exec_cron

    def fake_exit(code=0):
        raise SystemExit(code)

    with (
        patch("app.deploy._run_step", return_value=2),
        patch("app.deploy.sys.exit", side_effect=fake_exit),
    ):
        with pytest.raises(SystemExit) as ei:
            exec_cron(embed=True)
        assert ei.value.code == 2


@pytest.mark.asyncio
async def test_maybe_embed_skips_when_provider_none():
    session = AsyncMock()
    with patch("app.search.embed_pipeline.get_settings") as gs:
        settings = gs.return_value
        settings.embed_provider = "none"
        settings.embed_batch_size = 32
        settings.embed_chunk_size = 8
        settings.embed_max_per_run = 100
        settings.freshness_days = 30
        with patch(
            "app.ai.provider.embedding_provider_name",
            return_value=None,
        ):
            stats = await maybe_embed_missing(session)
    assert stats.status == "SKIPPED"
    assert stats.processed == 0


@pytest.mark.asyncio
async def test_maybe_embed_skips_unchanged_same_provider():
    """Jobs already embedded for current provider+hash are not re-sent."""
    session = MagicMock()
    job = SimpleNamespace(
        id=1,
        title="Eng",
        company_name="Acme",
        skills=["Python"],
        career_stage="mid",
        workplace_type="remote",
        description_text="Build APIs",
        embedding=[0.1] * 8,
        embedding_hash=None,
        embedding_provider="gemini:embedding-001",
    )
    job.embedding_hash = job_embedding_hash(
        job.title,
        job.company_name,
        job.skills,
        job.career_stage,
        job.workplace_type,
        job.description_text,
    )

    id_result = MagicMock()
    id_result.all.return_value = [(1,)]
    jobs_result = MagicMock()
    jobs_result.scalars.return_value.all.return_value = [job]

    # candidates count, then ids, then jobs load, then remaining count
    session.execute = AsyncMock(
        side_effect=[
            MagicMock(scalar_one=MagicMock(return_value=1)),  # count candidates
            id_result,
            jobs_result,
            MagicMock(scalar_one=MagicMock(return_value=0)),  # remaining
        ]
    )
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.expire_all = MagicMock()

    with (
        patch("app.search.embed_pipeline.get_settings") as gs,
        patch(
            "app.ai.provider.embedding_provider_name",
            return_value="gemini:embedding-001",
        ),
        patch("app.ai.provider.embed_texts", new=AsyncMock()) as embed_mock,
    ):
        settings = gs.return_value
        settings.embed_provider = "gemini"
        settings.embed_batch_size = 32
        settings.embed_chunk_size = 8
        settings.embed_max_per_run = 100
        settings.embed_max_consecutive_failures = 3
        settings.freshness_days = 30
        settings.gemini_keys = ["k"]
        stats = await maybe_embed_missing(session)

    embed_mock.assert_not_called()
    assert stats.skipped >= 1
    assert stats.processed == 0


@pytest.mark.asyncio
async def test_maybe_embed_reembeds_on_provider_mismatch():
    """Foreign vector space must be re-embedded — never relabeled."""
    session = MagicMock()
    h = job_embedding_hash("Eng", "Acme", ["Python"], "mid", "remote", "Build")
    job = SimpleNamespace(
        id=7,
        title="Eng",
        company_name="Acme",
        skills=["Python"],
        career_stage="mid",
        workplace_type="remote",
        description_text="Build",
        embedding=[0.2] * 8,
        embedding_hash=h,
        embedding_provider="local:bge-base-en-v1.5",
    )

    id_result = MagicMock()
    id_result.all.return_value = [(7,)]
    jobs_result = MagicMock()
    jobs_result.scalars.return_value.all.return_value = [job]
    empty_ids = MagicMock()
    empty_ids.all.return_value = []

    session.execute = AsyncMock(
        side_effect=[
            MagicMock(scalar_one=MagicMock(return_value=1)),
            id_result,
            jobs_result,
            empty_ids,  # next wave empty
            MagicMock(scalar_one=MagicMock(return_value=0)),
        ]
    )
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.expire_all = MagicMock()

    fake_vec = [[0.01] * 768]

    with (
        patch("app.search.embed_pipeline.get_settings") as gs,
        patch(
            "app.ai.provider.embedding_provider_name",
            return_value="gemini:embedding-001",
        ),
        patch(
            "app.ai.provider.embed_texts",
            new=AsyncMock(return_value=fake_vec),
        ) as embed_mock,
    ):
        settings = gs.return_value
        settings.embed_provider = "gemini"
        settings.embed_batch_size = 32
        settings.embed_chunk_size = 8
        settings.embed_max_per_run = 100
        settings.embed_max_consecutive_failures = 3
        settings.freshness_days = 30
        settings.gemini_keys = ["k"]
        stats = await maybe_embed_missing(session)

    embed_mock.assert_called()
    assert stats.processed == 1
    assert job.embedding_provider == "gemini:embedding-001"
    assert stats.status == "SUCCESS"


@pytest.mark.asyncio
async def test_maybe_embed_isolates_slice_failure():
    session = MagicMock()
    job_a = SimpleNamespace(
        id=1,
        title="A",
        company_name="C",
        skills=[],
        career_stage="mid",
        workplace_type="remote",
        description_text="a",
        embedding=None,
        embedding_hash=None,
        embedding_provider=None,
    )
    job_b = SimpleNamespace(
        id=2,
        title="B",
        company_name="C",
        skills=[],
        career_stage="mid",
        workplace_type="remote",
        description_text="b",
        embedding=None,
        embedding_hash=None,
        embedding_provider=None,
    )

    id_result = MagicMock()
    id_result.all.return_value = [(1,), (2,)]
    jobs_result = MagicMock()
    jobs_result.scalars.return_value.all.return_value = [job_a, job_b]
    empty_ids = MagicMock()
    empty_ids.all.return_value = []

    session.execute = AsyncMock(
        side_effect=[
            MagicMock(scalar_one=MagicMock(return_value=2)),
            id_result,
            jobs_result,
            empty_ids,
            MagicMock(scalar_one=MagicMock(return_value=1)),
        ]
    )
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.expire_all = MagicMock()

    calls = {"n": 0}

    async def flaky(texts):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("boom on first slice")
        return [[0.01] * 768 for _ in texts]

    with (
        patch("app.search.embed_pipeline.get_settings") as gs,
        patch(
            "app.ai.provider.embedding_provider_name",
            return_value="gemini:embedding-001",
        ),
        patch("app.ai.provider.embed_texts", new=AsyncMock(side_effect=flaky)),
    ):
        settings = gs.return_value
        settings.embed_provider = "gemini"
        settings.embed_batch_size = 32
        settings.embed_chunk_size = 1  # one job per slice
        settings.embed_max_per_run = 100
        settings.embed_max_consecutive_failures = 5
        settings.freshness_days = 30
        settings.gemini_keys = ["k"]
        stats = await maybe_embed_missing(session)

    assert stats.failed >= 1
    assert stats.processed >= 1
    assert stats.status == "PARTIAL"


def test_gemini_embed_path_does_not_import_onnx():
    """Memory safety: Gemini provider must not pull ONNX into the process."""
    import sys

    banned = [m for m in sys.modules if "onnxruntime" in m or m == "fastembed"]
    # Clear any prior accidental imports from other tests
    for m in banned:
        sys.modules.pop(m, None)

    with patch("app.ai.provider.get_settings") as gs:
        settings = gs.return_value
        settings.embed_provider = "gemini"
        settings.gemini_keys = ["k"]
        settings.embedding_dimensions = 768
        name = __import__("app.ai.provider", fromlist=["embedding_provider_name"]).embedding_provider_name()
        assert name == "gemini:embedding-001"

    assert "onnxruntime" not in sys.modules
    assert "fastembed" not in sys.modules


def test_embed_pass_stats_embedded_alias():
    s = EmbedPassStats(processed=12)
    assert s.embedded == 12
