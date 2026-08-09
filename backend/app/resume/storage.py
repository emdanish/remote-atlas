"""Local secure storage for resumes and generated PDFs (no object store required)."""

from __future__ import annotations

import hashlib
import re
import secrets
from pathlib import Path

from app.config import BACKEND_ROOT

UPLOAD_ROOT = BACKEND_ROOT / "data" / "uploads"
RESUME_DIR = UPLOAD_ROOT / "resumes"
TAILOR_DIR = UPLOAD_ROOT / "tailored"

MAX_RESUME_BYTES = 2_000_000
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md"}
ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/msword",
    "text/plain",
    "text/markdown",
    "application/octet-stream",
}


def ensure_dirs() -> None:
    RESUME_DIR.mkdir(parents=True, exist_ok=True)
    TAILOR_DIR.mkdir(parents=True, exist_ok=True)


def safe_filename(name: str) -> str:
    base = Path(name or "resume").name
    base = re.sub(r"[^\w.\- ()+]", "_", base)[:180]
    return base or "resume.pdf"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def store_resume_bytes(user_id: int, filename: str, data: bytes) -> Path:
    ensure_dirs()
    user_dir = RESUME_DIR / str(user_id)
    user_dir.mkdir(parents=True, exist_ok=True)
    token = secrets.token_hex(8)
    path = user_dir / f"{token}_{safe_filename(filename)}"
    path.write_bytes(data)
    return path


def store_tailored_pdf(user_id: int, tailoring_id: int, data: bytes) -> Path:
    ensure_dirs()
    user_dir = TAILOR_DIR / str(user_id)
    user_dir.mkdir(parents=True, exist_ok=True)
    path = user_dir / f"tailored_{tailoring_id}.pdf"
    path.write_bytes(data)
    return path


def resolve_stored(path_str: str) -> Path | None:
    path = Path(path_str)
    if not path.is_absolute():
        path = BACKEND_ROOT / path
    try:
        resolved = path.resolve()
        root = UPLOAD_ROOT.resolve()
        if not str(resolved).startswith(str(root)):
            return None
        if not resolved.is_file():
            return None
        return resolved
    except OSError:
        return None
