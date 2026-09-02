# Football Value Analytics — project notes for Claude Code

## Non-negotiables (from the product specification)
- Probabilities come from the statistical models in `backend/app/models_ml` and `backend/app/statistics`; an LLM may only paraphrase stored numbers (`backend/app/llm`).
- Never fabricate odds, injuries, statistics, fixtures or results. Missing data is `None` → "DATA UNAVAILABLE". Demo data is `source="demo"` / `is_demo=True` and never mixed with production.
- No guarantee language ("guaranteed", "sure bet", "lock", "free money"). Use "value candidate", "model edge", "estimated probability".
- The application never places real bets. Paper betting only; Kelly stakes are capped.
- Leakage prevention is structural: everything "as of" a cutoff goes through `statistics/engine.py::MatchHistory` (`team_matches`, `league_averages`, `elo_ratings` filter on kickoff < cutoff). Keep the daily scan and the backtester on that single path.

## Layout
- Backend: FastAPI in `backend/app` (routers in `api/`, jobs in `tasks/`, CLI in `__main__.py`). Tests: `backend/tests` (run `pytest` from `backend/`; builds a demo SQLite DB in `backend/data/test_fva.db`).
- Frontend: React + TypeScript + Vite + Tailwind + Recharts in `frontend/` (relative `/api` URLs only).
- Migrations: `migrations/` (Alembic, `alembic.ini` in `backend/`). After model changes: `alembic revision --autogenerate`, then replace any `app.models.mixins.UTCDateTime(...)` with `sa.DateTime(timezone=True)` in the generated file.
- Markets: add to `backend/app/odds/markets.py` (+ provider mapping in `providers/…` if priced, + settlement rule in `betting/settlement.py`).

## Conventions
- Settings that users may tune live in `services/settings_service.py::DEFAULTS` and are edited via `PUT /api/settings/{key}`; don't hard-code thresholds elsewhere.
- Datetimes are timezone-aware UTC everywhere (`models/mixins.py::UTCDateTime`); local day windows via `utils/time.py`.
- Windows dev: Python is `backend/.venv/Scripts/python.exe`; Docker is not installed on this machine.
- Run `ruff check app tests` and `pytest` before declaring backend work done; `npm run build` for the frontend.
