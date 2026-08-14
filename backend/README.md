# Remote Atlas Backend

FastAPI job intelligence engine + auth.

```bash
pip install -r requirements.txt
# configure .env (DB + AI keys; set EMBED_PROVIDER=gemini for production-like embeds)
alembic upgrade head
python -m app.ingest run --no-embed
uvicorn app.main:app --reload --port 8000
```

## Embeddings

- **Production (Render):** `EMBED_PROVIDER=gemini` — HTTP `gemini-embedding-001` at
  768-d. Fits 512 MiB. Requires `GEMINI_API_KEY_1` (and optionally `_2`).
- **Local optional BGE:** only on hosts with ample RAM (≥2 GiB recommended):
  `pip install -r requirements-local-embed.txt` then `EMBED_PROVIDER=local`.
  Do **not** use local BGE on Render Starter — model load OOMs.

Incremental / resumeable:

```bash
python -m app.ingest embed --limit 800
# or production launcher:
python -m app.deploy cron --embed
```

Logs distinguish `INGESTION STATUS` from `EMBEDDING STATUS`. Embedding failure
after a successful ingest does not fail the cron exit code.

Production deployments must use a strong `JWT_SECRET` (≥32 chars, not the
placeholder). On Render, a weak secret **refuses to start**. Use HTTPS with
`AUTH_COOKIE_SECURE=true`, and an exact frontend origin in `CORS_ORIGINS`.
Sessions are **HttpOnly cookies only** — the API does not return JWTs to JavaScript.

Resume binaries on disk are ephemeral on Render. Extracted text in Postgres is
durable; see [docs/junior-hunt.md](../docs/junior-hunt.md).

Himalayas listings must keep official apply URLs (link-back). Do not ingest
unlicensed community job JSON as first-class catalog rows.
