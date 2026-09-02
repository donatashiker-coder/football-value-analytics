# Football Value Analytics

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/donatashiker-coder/football-value-analytics)

Lietuviška paleidimo instrukcija: [docs/DEPLOY_LT.md](docs/DEPLOY_LT.md).

A football analytics and **value-betting research** platform. Every day it ingests fixtures, results, per-match
statistics, team news and bookmaker odds; computes model probabilities with statistical models (Poisson /
Dixon-Coles for goals, Negative-Binomial for corners, Elo for strength); compares them with
overround-corrected bookmaker prices; and surfaces *statistical value candidates* — or says **NO BET** — on a
web dashboard, with walk-forward backtesting, paper betting, bankroll tracking and model-calibration monitoring.

> **Statistical analysis is not a guarantee of future results.** This application never places bets. It reports
> *estimated* probabilities, *estimated* edges and *historical* performance. Nothing here is a recommendation.

---

## Contents

1. [What it does](#what-it-does)
2. [Architecture](#architecture)
3. [Quick start (demo mode, no API keys)](#quick-start-demo-mode)
4. [Docker](#docker)
5. [Environment variables](#environment-variables)
6. [Data providers](#data-providers)
7. [Database](#database)
8. [Running the backend, frontend, scanner, backtests, tests](#running-things)
9. [Model methodology](#model-methodology)
10. [Value calculation](#value-calculation)
11. [Responsible use](#responsible-use)
12. [Known limitations](#known-limitations)

Further documentation: [docs/SETUP.md](docs/SETUP.md) · [docs/API.md](docs/API.md) · [docs/MODELS.md](docs/MODELS.md) ·
[docs/BACKTESTING.md](docs/BACKTESTING.md) · [docs/DATA_PROVIDERS.md](docs/DATA_PROVIDERS.md)

---

## What it does

```
DATA → VALIDATION → FEATURE ENGINEERING → STATISTICAL MODEL → MODEL PROBABILITY
     → BOOKMAKER MARKET PROBABILITY → VALUE CALCULATION → QUALITY FILTER → RANKING → (optional) LLM EXPLANATION
```

* **Markets**: 1X2, double chance, draw-no-bet, Asian handicap (whole/half lines), total goals O/U 0.5–4.5,
  team goals, BTTS, total corners O/U 7.5–12.5, team corners, first-half goals / BTTS / corners.
  Adding a market = one entry in `backend/app/odds/markets.py`.
* **Models**: Dixon-Coles adjusted Poisson (primary goals model), independent Poisson and Elo (secondary, for
  model-agreement), Negative Binomial vs Poisson for corners (selected by backtest log-likelihood).
* **Value engine**: fair odds = 1/p, EV = p·O − 1, edge = p − normalised market probability, configurable
  EV labels (IGNORE / WEAK / INTERESTING / STRONG / VERY STRONG), separate **confidence** (0–100) and
  **data-quality** (0–100) scores, composite **value score** (weights configurable) and a **NO-BET filter**
  with explicit reasons.
* **Backtesting**: chronological walk-forward; features are built strictly from matches before each kickoff;
  pre-match odds only (closing odds only for CLV); ROI, yield, drawdown, streaks, profit factor, Sharpe-like,
  CLV, calibration (Brier / log-loss / ECE / reliability bins), breakdowns by league / market / odds range /
  month / season / EV range / expected total.
* **Paper betting & bankroll**: record bets with flat / percentage / ¼, ½, full Kelly (capped) stakes;
  auto-settlement from results; CLV per bet; equity curve and drawdown.
* **Model monitoring**: every prediction is stored with feature snapshot, model version and data timestamp,
  settled against results, and evaluated (leaderboard, calibration curve, drift detection).
* **Daily automation**: APScheduler jobs (06:00 fixtures → 06:15 stats → 06:30 news → 06:45 odds → 07:00 models
  → 07:05 report, Europe/London, DST-aware) plus periodic odds refresh + rescan.
* **Alerts**: optional email / Telegram / Discord when EV, confidence, data quality and odds freshness all pass.
* **Demo mode**: deterministic synthetic leagues, results, statistics, injuries and odds — clearly labelled,
  never mixed with production data — so the whole system runs without any API key.

## Architecture

```
football-value-analytics/
├── backend/app/
│   ├── main.py            FastAPI app (CORS, rate limiting, secure headers, /api/docs)
│   ├── __main__.py        CLI  (python -m app scan | backtest | update-data | ...)
│   ├── config.py          pydantic-settings; secrets only from environment
│   ├── database.py        SQLAlchemy engine/session (PostgreSQL in Docker, SQLite for dev/tests)
│   ├── models/            ORM: competitions, seasons, teams, players, fixtures, results, fixture_statistics,
│   │                      team_statistics, player_statistics, odds, bookmakers, markets, injuries, suspensions,
│   │                      transfers, manager_changes, weather, model_versions, feature_snapshots,
│   │                      model_predictions, value_opportunities, team_ratings, backtests, bets,
│   │                      bankroll_snapshots, data_quality_logs, api_requests, league_settings, system_settings
│   ├── providers/         FootballDataProvider / OddsDataProvider / InjuryDataProvider / WeatherDataProvider
│   │   ├── football/      api_football.py, football_data_org.py, demo.py
│   │   ├── odds/          the_odds_api.py
│   │   ├── weather/       open_meteo.py
│   │   ├── http.py        cached, retrying, rate-limit-aware httpx client (logs to api_requests)
│   │   └── factory.py     demo vs production resolution (never mixed)
│   ├── statistics/        MatchHistory (as-of cutoff), team statistics, shrinkage, weighted form, Elo
│   ├── models_ml/         distributions, goal_model (Poisson/Dixon-Coles), corner_model (NB/Poisson),
│   │                      elo, calibration (Brier, log-loss, ECE, AUC, drift, Platt)
│   ├── odds/              markets registry, odds maths (implied, overround, normalisation, comparison, CLV)
│   ├── betting/           value (EV/edge/labels/confidence/ranking/NO-BET), staking, settlement, paper betting
│   ├── services/          ingestion, features, prediction, value_engine, scan, evaluation, settings
│   ├── backtesting/       walk-forward engine + corner threshold analysis
│   ├── reporting/         daily report (JSON + text)
│   ├── team_news/         player importance, absence impact, manager-change analysis
│   ├── llm/               optional explanation layer (Anthropic / OpenAI), structured-JSON-only
│   ├── notifications/     email / Telegram / Discord alerts
│   ├── tasks/             jobs + APScheduler
│   └── api/               routers: health, fixtures, value, teams, leagues, odds, models, backtests, paper, settings, reports
├── backend/tests/         70 tests: maths, odds, value, settlement, staking, statistics, calibration, backtest arithmetic,
│                          leakage, end-to-end demo pipeline + API
├── frontend/              React + TypeScript + Vite + Tailwind + Recharts dashboard
├── migrations/            Alembic (initial schema included)
├── docker/                Dockerfiles + nginx config
├── docs/                  documentation
├── scripts/               container entrypoints
├── docker-compose.yml     postgres, redis, backend, scheduler, worker, frontend
└── .env.example
```

## Quick start (demo mode)

Requirements: Python 3.12+, Node 20+. No API keys needed.

```bash
# backend
cd backend
python -m venv .venv && . .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
cp ../.env.example ../.env                          # keep APP_MODE=demo, set DATABASE_URL=sqlite:///./data/fva.db
export DATABASE_URL=sqlite:///./data/fva.db APP_MODE=demo   # or put them in backend/.env
python -m app init-db
python -m app scan --refresh --days 3               # ingest demo data, run models, compute value
python -m app backtest --strategy corners           # walk-forward backtest
python -m app generate-report                       # text report
uvicorn app.main:app --reload                       # API on http://localhost:8000  (docs: /api/docs)

# frontend (second terminal)
cd frontend
npm install
npm run dev                                         # http://localhost:5173 (proxies /api to :8000)
```

## Docker

```bash
cp .env.example .env          # fill in keys for production, or leave APP_MODE=demo
docker compose up --build     # postgres, redis, backend (runs Alembic), scheduler, worker (one-shot pipeline), frontend
# UI: http://localhost:3000    API: http://localhost:8000/api/docs
```

Health checks: `/api/health`, `/api/status`, `/api/data-health`, `/api/model-health`.

## Environment variables

See `.env.example` (documented inline). Key ones:

| Variable | Purpose |
|---|---|
| `APP_MODE` | `demo` (synthetic data) or `production` (requires provider keys; refuses to fabricate) |
| `DATABASE_URL` | `postgresql+psycopg://…` or `sqlite:///./data/fva.db` |
| `API_FOOTBALL_KEY` | API-Football (fixtures, results, corners, shots, xG*, injuries, odds) |
| `FOOTBALL_DATA_API_KEY` | football-data.org (fixtures/results fallback; no corners/xG/injuries/odds) |
| `ODDS_API_KEY` | The Odds API (1X2, totals, BTTS, team totals, spreads; **no corners**) |
| `FOOTBALL_PROVIDER`, `ODDS_PROVIDER` | provider selection |
| `LLM_PROVIDER`, `ANTHROPIC_API_KEY` / `OPENAI_API_KEY`, `LLM_MODEL` | optional explanation layer |
| `TIMEZONE`, `SCHEDULE_*`, `ODDS_REFRESH_MINUTES` | scheduler |
| `SMTP_*`, `TELEGRAM_*`, `DISCORD_WEBHOOK_URL` | optional alerts |

Secrets are never logged (the log formatter redacts `key=/token=` patterns) and never reach the frontend.

## Data providers

Full field-by-field mapping, limits and pricing notes: [docs/DATA_PROVIDERS.md](docs/DATA_PROVIDERS.md).
If a provider does not supply a statistic, the field is stored as `NULL` and shown as **DATA UNAVAILABLE**;
markets without prices are shown as **ODDS UNAVAILABLE** / **MARKET UNAVAILABLE**; odds older than 4 h are
flagged **STALE ODDS**. Nothing is ever fabricated. In production mode with no keys the API reports
`"Production data provider not configured."`.

## Database

PostgreSQL via Alembic (`migrations/versions/…_initial_schema.py`; `alembic upgrade head` runs on container
start). SQLite is supported for development and tests (tables auto-created). All externally sourced rows carry
`source`, `source_id`, `retrieved_at`, `last_updated_at`, `data_quality`.

## Running things

| Task | Command |
|---|---|
| API | `uvicorn app.main:app --reload` (from `backend/`) |
| Frontend | `npm run dev` / `npm run build` (from `frontend/`) |
| Scanner | `python -m app scan [--date YYYY-MM-DD] [--days N] [--league ENG_PL] [--refresh]` |
| Data refresh | `python -m app update-data`, `python -m app update-odds` |
| Full morning pipeline | `python -m app pipeline` |
| Backtest | `python -m app backtest --strategy corners|goals|BTTS|MATCH_RESULT|… [--min-ev 0.03] [--corner-distribution poisson]` |
| Model evaluation | `python -m app evaluate-model` |
| Daily report | `python -m app generate-report [--send]` |
| Scheduler | `python -m app scheduler` |
| Config validation | `python -m app check-config` |
| Tests | `pytest` (from `backend/`) |
| Lint | `ruff check app tests` |

## Model methodology

Summarised here; full detail in [docs/MODELS.md](docs/MODELS.md).

* **Team strengths** are multiplicative attack/defence factors vs. the league venue average, computed
  separately for home and away, opponent-adjusted, blended with the previous season (weight decays as
  current-season matches accumulate) and **shrunk** towards 1.0 with an empirical-Bayes prior
  (`(n·x̄ + k·μ)/(n + k)`, k = 8 matches by default). 3 matches never dominate 100.
* **Goals**: λ_home = league_home_avg × home_attack × away_defence × home_advantage; λ_away likewise.
  Scoreline matrix from independent Poissons with the **Dixon-Coles** low-score correction (ρ, default −0.05,
  fittable by maximum likelihood). All goals / result / handicap / BTTS / team-goal probabilities come from the
  matrix. First-half markets use a league-estimated first-half goal share.
* **Corners**: expected corners from opponent-adjusted shrunk corner rates; total distribution is
  **Negative Binomial** with dispersion derived from the league's observed variance/mean ratio (falls back to
  Poisson when not over-dispersed). Backtests report Poisson vs NB log-likelihood and the preferred one.
* **Elo** with margin-of-victory scaling and between-season regression provides an independent 1X2 view used
  for model-agreement, not as the primary probability.
* **Confidence** (0–100) is independent of EV: sample size, data completeness, calibration, league
  reliability, bookmaker liquidity, model agreement, volatility, team-news uncertainty, odds freshness, strategy
  history.
* **Calibration**: Brier, log-loss, ROC-AUC, expected calibration error and reliability bins on every settled
  prediction; drift flag when recent Brier deteriorates materially versus history.

## Value calculation

```
implied            = 1 / odds
market probability = implied / Σ implied over the complete outcome set   (overround removed; median odds)
fair odds          = 1 / model probability
edge               = model probability − market probability
EV                 = model probability × best odds − 1
```

Value labels (configurable): < 2 % IGNORE · 2–5 % WEAK · 5–8 % INTERESTING · 8–12 % STRONG · > 12 % VERY STRONG.
NO-BET gates (configurable): min EV, min confidence, min data quality, odds range, min sample, max odds age,
max model disagreement, min bookmakers, EV sanity cap, team-news uncertainty.
Value score (weights configurable): 35 % EV · 20 % confidence · 15 % data quality · 10 % model agreement ·
10 % historical strategy performance · 10 % sample reliability. A +20 % EV from a weak model with poor data
ranks below a +8 % EV from a calibrated model with good data.

## Responsible use

This is a research tool. It does not and will not place bets. The UI, reports and alerts carry the
disclaimer, avoid "guaranteed / sure / lock" language (the LLM layer is instructed likewise and its output is
checked), default to flat stakes, and cap Kelly stakes at 2 % of bankroll. Backtest results on demo data are
synthetic and prove nothing about real markets; results on real data are historical and not predictive.

## Known limitations

* **Providers**: free tiers are restrictive — football-data.org has no corners/xG/shots/injuries/odds;
  API-Football's per-fixture statistics, injuries and odds need a paid plan, and xG exists only for some
  competitions; The Odds API offers no corner markets and historical odds only on paid plans. Backtests on real
  data therefore depend on the odds snapshots this platform stores itself over time (opening/closing are
  recorded by the scheduler), or on paid historical feeds.
* **Player importance / absence impact** is only estimated when player minutes/goals are available; otherwise
  injuries raise uncertainty (lower confidence) without changing probabilities. Weather is stored but has no
  model weight until a backtest justifies it.
* **Machine-learning ensembles** (logistic / gradient boosting) are deliberately not enabled: the registry and
  evaluation framework support additional models, but with the data available the calibrated Dixon-Coles +
  NB models are the simplest that perform, and ML would need genuine out-of-sample validation first.
* The LLM layer is optional and off by default; it only paraphrases stored numbers.
* No authentication is included (single-user deployment assumed); add a reverse-proxy auth layer before
  exposing it publicly. Rate limiting and secure headers are enabled.
* Demo odds are simulated with noise around latent "true" probabilities, so demo mode shows more value
  candidates than a real, efficient market would.
