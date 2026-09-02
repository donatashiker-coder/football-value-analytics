# Setup

## 1. Local development (no Docker)

Requirements: Python 3.12+, Node 20+ (Node 24 tested), Git.

```bash
git clone <repo> football-value-analytics && cd football-value-analytics
cp .env.example .env
```

Edit `.env`:

* **Demo mode** (no keys): `APP_MODE=demo`, `DATABASE_URL=sqlite:///./data/fva.db`.
* **Production**: `APP_MODE=production`, set `API_FOOTBALL_KEY` (recommended) and/or `FOOTBALL_DATA_API_KEY`,
  `ODDS_API_KEY`, and a PostgreSQL `DATABASE_URL`.

Backend:

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate            # Windows      |  . .venv/bin/activate   # macOS/Linux
pip install -r requirements-dev.txt
cp ../.env .env                     # pydantic-settings reads backend/.env (or export the variables)
python -m app check-config          # validates DB connectivity + provider configuration
python -m app init-db               # SQLite only; PostgreSQL uses: alembic upgrade head
python -m app pipeline              # fixtures → statistics → news → odds → settle → scan → report
uvicorn app.main:app --reload --port 8000
```

Frontend:

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173 ; /api is proxied to http://localhost:8000
npm run build      # production bundle in frontend/dist
```

## 2. Docker Compose

```bash
cp .env.example .env    # edit as above (DATABASE_URL/REDIS_URL are overridden by compose)
docker compose up --build
```

Services: `postgres` (16), `redis`, `backend` (runs `alembic upgrade head`, serves `:8000`), `scheduler`
(`python -m app scheduler`), `worker` (one-shot `python -m app pipeline` on startup — rerun with
`docker compose run --rm worker`), `frontend` (nginx on `:3000`, proxies `/api`).

Every service has a health check; `backend` waits for `postgres`/`redis`, `scheduler`/`worker`/`frontend` wait
for a healthy `backend`.

## 3. Database migrations

```bash
cd backend
alembic upgrade head                       # apply
alembic revision --autogenerate -m "msg"   # after changing models
alembic downgrade -1
alembic check                              # verify models == migrations
```

The initial migration creates all 26 tables from an empty database and has been round-trip tested
(upgrade → downgrade → upgrade → check).

## 4. Scheduler times

Configured via `SCHEDULE_*` (HH:MM, interpreted in `TIMEZONE`, default `Europe/London`, DST-aware) and
`ODDS_REFRESH_MINUTES` (periodic odds refresh + rescan). Set `SCHEDULER_ENABLED=false` to disable.

## 5. Alerts

Email (`SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `ALERT_EMAIL_TO`), Telegram
(`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`), Discord (`DISCORD_WEBHOOK_URL`). Thresholds are in Settings →
`alerts`. Alerts only fire when EV, confidence, data quality and odds freshness all pass.

## 6. LLM explanations (optional)

`LLM_PROVIDER=anthropic` + `ANTHROPIC_API_KEY` (model `LLM_MODEL`, default `claude-sonnet-5`), or
`LLM_PROVIDER=openai` + `OPENAI_API_KEY`. `POST /api/opportunities/{id}/explain` sends only structured JSON of
stored numbers. Without a provider the deterministic explanation is shown.

## 7. Tests and quality gates

```bash
cd backend
pytest                    # 70 tests, ~1-2 min (builds a demo database)
ruff check app tests
mypy app                  # optional
cd ../frontend && npm run build
```

## 8. Troubleshooting

* `Production data provider not configured.` → set `API_FOOTBALL_KEY` or `FOOTBALL_DATA_API_KEY`, or use
  `APP_MODE=demo`.
* `ODDS UNAVAILABLE` everywhere → `ODDS_API_KEY` missing, the league is not covered by the odds provider, or
  the odds refresh has not run (`python -m app update-odds`).
* Rate limited (HTTP 429) → the client backs off automatically and logs to `api_requests`; reduce enabled
  leagues (Settings → Leagues) or refresh intervals.
* Stale data warnings → check `/api/data-health` and the scheduler logs.

## Deploying to Render (free plan) + Neon Postgres

One container (`docker/Dockerfile.render`) serves the API, the built frontend and the in-process scheduler
(`SCHEDULER_IN_APP=true`). The blueprint is `render.yaml`; it never contains secrets.

1. Create a free Postgres database at https://neon.tech and copy its connection string
   (`postgresql://...neon.tech/neondb?sslmode=require`; the app rewrites it to the psycopg driver).
2. On https://dashboard.render.com choose **New → Blueprint**, connect the GitHub repository and set the
   prompted values: `DATABASE_URL`, `FOOTBALL_DATA_API_KEY`, `ODDS_API_KEY`.
3. The first start runs `alembic upgrade head`. Load data either with the pipeline
   (`POST /api/jobs/pipeline` — uses provider credits) or by copying an existing SQLite database with
   `scripts/copy_sqlite_to_postgres.py`.
4. The free instance sleeps after 15 minutes without traffic. `.github/workflows/keep-awake.yml` pings
   `/api/health` around the 06:00–07:05 Europe/London job window; set the repository variable `APP_URL`
   (Settings → Secrets and variables → Actions → Variables) to the Render URL.
