from __future__ import annotations

import hashlib
from typing import Optional

from app.ai.provider import embed_texts as provider_embed_texts


async def embed_texts(texts: list[str]) -> list[list[float]]:
    return await provider_embed_texts(texts)


def job_embedding_document(
    title: str,
    company: str | None,
    skills: list[str],
    career_stage: str | None,
    workplace: str | None,
    description: Optional[str],
) -> str:
    parts = [
        title,
        company or "",
        f"Skills: {', '.join(skills)}",
        f"Stage: {career_stage or 'unknown'}",
        f"Workplace: {workplace or 'unknown'}",
        (description or "")[:1500],
    ]
    return "\n".join(p for p in parts if p)


def job_embedding_hash(
    title: str,
    company: str | None,
    skills: list[str],
    career_stage: str | None,
    workplace: str | None,
    description: Optional[str],
) -> str:
    doc = job_embedding_document(title, company, skills, career_stage, workplace, description)
    return hashlib.sha256(doc.encode("utf-8")).hexdigest()[:40]


async def embed_job_document(
    title: str,
    company: str | None,
    skills: list[str],
    career_stage: str | None,
    workplace: str | None,
    description: Optional[str],
) -> Optional[list[float]]:
    doc = job_embedding_document(title, company, skills, career_stage, workplace, description)
    vectors = await embed_texts([doc])
    return vectors[0] if vectors else None
