# Remote Atlas Backend

FastAPI job intelligence engine + auth.

```bash
pip install -r requirements.txt
# configure .env (DB + AI keys)
alembic upgrade head
python -m app.ingest run --no-embed
uvicorn app.main:app --reload --port 8000
```

The default embedding provider is local BGE. Run `python -m app.ingest embed --limit 800` repeatedly to fill embeddings without consuming Gemini quota. Production deployments must use a strong `JWT_SECRET`, HTTPS with `AUTH_COOKIE_SECURE=true`, and an exact frontend origin in `CORS_ORIGINS`.
