# Remote Atlas

Intelligent job discovery for candidates: authentic ATS and career sources,
strict freshness, hybrid search, resume tailoring, and a direct path to apply.

```text
remote-atlas/
  backend/     # FastAPI, collectors, scheduler, Alembic, Postgres/pgvector
  frontend/    # Next.js App Router
  render.yaml  # Render API + daily Cron ingestion Blueprint
```

## Local development

### Backend

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env
alembic upgrade head
python -m app.ingest run --no-embed
uvicorn app.main:app --reload --port 8000
```

API docs: <http://127.0.0.1:8000/docs>

### Frontend

```bash
cd frontend
cp .env.example .env.local
npm install
npm run dev
```

App: <http://localhost:3000>

Only public URLs belong in `frontend/.env.local`. Never put API keys or database
credentials in a `NEXT_PUBLIC_*` variable.

## Environment variables

The full backend template is in `backend/.env.example`. Important production
values are:

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | SQLAlchemy async URL using `postgresql+asyncpg://` |
| `DATABASE_URL_SYNC` | Alembic URL using `postgresql+psycopg2://` |
| `DATABASE_POOL_SIZE` / `DATABASE_MAX_OVERFLOW` | Per-process connection limits |
| `JWT_SECRET` | Signing secret; Render generates this for the API |
| `AUTH_COOKIE_SECURE` | Must be `true` in production |
| `CORS_ORIGINS` | Exact comma-separated frontend origins, without paths |
| `FRESHNESS_DAYS` | Active index window (product default: `30`) |
| `GEMINI_API_KEY_1` / `GEMINI_API_KEY_2` | Chat + **embeddings** (required for hybrid search in production) |
| `DEEPSEEK_API_KEY` / `PERPLEXITY_API_KEY` | Optional chat fallbacks |
| `THE_MUSE_API_KEY` | Optional higher-rate collector access |
| `EMBED_PROVIDER` | `gemini` (production), `local` (high-RAM only), `auto`, or `none` |
| `EMBED_MAX_PER_RUN` | Incremental embed cap per cron (default `1500`) |

### Embedding architecture

Production uses **Gemini `embedding-001` at 768 dimensions** over HTTPS — the same
pgvector width as before. Local FastEmbed/`BAAI/bge-base-en-v1.5` exceeds Render
Starter's **512 MiB** at model load (proven in production OOM logs), so it is not
installed on the cron image.

Daily cron (`python -m app.deploy cron --embed`):

1. **Ingest process** — crawl, upsert, housekeeping, pulse alerts → `INGESTION STATUS = SUCCESS`
2. **Embed process** — incremental Gemini pass for missing/changed/provider-mismatched jobs

Embedding failure does **not** fail the cron after a successful ingest (jobs stay
searchable via PostgreSQL FTS). The next run resumes the backlog. Content changes
clear `embedding_hash` on upsert so re-embed is automatic. Hybrid search only
uses vectors whose `embedding_provider` matches the live provider (no mixed spaces).

```bash
python -m app.ingest embed --limit 800
```

Repeat until `/health/ingest` reports the desired coverage.

## Production deployment: Render + Vercel

The repository includes a Render Blueprint for:

- `remote-atlas-api`: free-tier-compatible FastAPI web service.
- `remote-atlas-ingest`: **Cron Job** that runs once per day (`0 1 * * *` UTC = 06:00 PKT).

Both services run Alembic before their commands (web startup / cron start). A
PostgreSQL advisory lock prevents migration races. Render checks
`/health/ready`, which returns HTTP 503 if Postgres is unavailable.

### Cost note

Render Cron Jobs bill prorated-by-the-second with a small monthly minimum
(currently about `$1` per cron service). That is far cheaper than an always-on
background worker for a daily crawl. Do not approve paid resources until you
have reviewed Render's current pricing screen.

A free Render web service sleeps after inactivity. If you stay on free compute,
point a free uptime monitor at `/health` (or `/health/ready`) every few minutes
so candidates are not waiting on a cold start. Paid web plans do not need a
keep-alive for sleep.

### 1. Prepare Postgres (Neon is fine)

1. Create a Postgres database (Neon, Render Postgres, etc.).
2. Enable the `vector` extension if your provider does not create it for you
   (Alembic also enables it on first migrate).
3. Copy the connection string twice:
   - `DATABASE_URL` → prefix `postgresql+asyncpg://`
   - `DATABASE_URL_SYNC` → prefix `postgresql+psycopg2://`
4. Keep SSL parameters your provider requires. Prefer the direct/session
   connection for migrations if a pooler URL is also provided.

### 2. Create the Render services

1. Open <https://dashboard.render.com/> → **New +** → **Blueprint**.
2. Connect this repository. Render detects `render.yaml`.
3. Review both resources. Enter secrets (`DATABASE_URL`, `DATABASE_URL_SYNC`,
   optional AI keys). Set `CORS_ORIGINS` to a temporary valid origin if needed.
4. Apply the Blueprint (or create the web service alone to stay free of the cron).
5. Wait for the API deploy. Open `<api-url>/health/ready` and confirm
   `"status":"ok"`.

Manual one-shot ingest (without waiting for the schedule):

```bash
python -m app.deploy cron
# equivalent:
python -m app.scheduler --once
```

### 3. Create the Vercel frontend

1. <https://vercel.com/new> → import the repository.
2. Root Directory: `frontend`.
3. Environment variables:
   - `NEXT_PUBLIC_API_URL` = Render API URL (no trailing slash)
   - `NEXT_PUBLIC_SITE_URL` = public frontend URL
4. Deploy. After the first production URL is known, update `NEXT_PUBLIC_SITE_URL`
   and redeploy if needed, then set Render `CORS_ORIGINS` to the same exact
   frontend origin(s).

### 4. Verify production

1. Register a temporary account; confirm session cookies work over HTTPS.
2. Search jobs, open a detail page, tailor a resume if keys are configured.
3. Open Render → cron job → **Logs** after `0 6 * * *` UTC or **Trigger Run**.
4. Confirm `/health/ingest` inventory numbers match the landing page live index.

## Production commands

| Purpose | Command |
|---|---|
| API process | `python -m app.deploy web` |
| Daily cron (ingest + embed) | `python -m app.deploy cron --embed` |
| Manual ingest only | `python -m app.scheduler --once --ingest-only` |
| Manual embed pass | `python -m app.ingest embed` |
| Liveness | `GET /health` |
| Readiness | `GET /health/ready` |
| Inventory | `GET /health/ingest` |

Ingestion and embedding are separate processes. After a successful ingest, an
embedding failure exits the cron with code 0 so Render does not treat the job
index refresh as failed. Look for `INGESTION STATUS` and `EMBEDDING STATUS` in
logs.

## Status

- Job intelligence, auth, profiles, saves, matches, alerts: implemented
- Resume upload + job-specific tailoring with content integrity: implemented
- Collectors: public feeds + Greenhouse, Lever, Ashby, Workable, SmartRecruiters,
  Recruitee, Personio, Teamtailor, Breezy, Workday, BambooHR
- Deployment Blueprint: API web service + daily Cron ingestion
