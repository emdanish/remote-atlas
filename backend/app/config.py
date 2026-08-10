from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BACKEND_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/remote_atlas"
    database_url_sync: str = "postgresql+psycopg2://postgres:postgres@localhost:5432/remote_atlas"

    # Multi-provider AI keys (server-side only — never expose to frontend)
    gemini_api_key_1: str = ""
    gemini_api_key_2: str = ""
    # Back-compat single key
    gemini_api_key: str = ""
    deepseek_api_key: str = ""
    perplexity_api_key: str = ""
    the_muse_api_key: str = ""

    jwt_secret: str = "change-me-in-production-remote-atlas"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24 * 7
    jwt_issuer: str = "remote-atlas"
    jwt_audience: str = "remote-atlas-web"
    auth_cookie_name: str = "remote_atlas_session"
    auth_cookie_secure: bool = False
    auth_cookie_samesite: str = "lax"

    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    database_pool_size: int = 5
    database_max_overflow: int = 5

    # Product default: active index window for posted/first-seen jobs (days).
    freshness_days: int = 30
    ingest_concurrency: int = 24
    embedding_dimensions: int = 768
    # How many jobs to load from DB per embed wave (keep small on 512Mi dynos)
    embed_batch_size: int = 48
    # Texts per local ONNX/Gemini slice
    embed_chunk_size: int = 4
    # Cap per embed process so cron finishes before OOM / time-out; next day continues
    embed_max_per_run: int = 400
    # gemini | local | auto | none/off/fts (none = never load local models; FTS-only search)
    embed_provider: str = "local"
    embed_max_consecutive_failures: int = 3
    companies_path: str = str(BACKEND_ROOT / "data" / "companies.yaml")

    @property
    def gemini_keys(self) -> list[str]:
        keys: list[str] = []
        for k in (self.gemini_api_key_1, self.gemini_api_key_2, self.gemini_api_key):
            if k and k.strip() and k.strip() not in keys:
                keys.append(k.strip())
        return keys

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
