# API reference

Base path `/api`. Interactive docs: `/api/docs` (OpenAPI at `/api/openapi.json`). All responses are JSON unless
noted. Probabilities are fractions (0–1); `expected_value` and `edge` are fractions; `confidence`,
`data_quality`, `value_score` are 0–100. Rate limit: 600 requests/minute per IP.

## Health

| Endpoint | Description |
|---|---|
| `GET /health` | liveness (DB ping), app mode, version |
| `GET /status` | counts, last scan, provider configuration flags (never key values) |
| `GET /data-health` | last odds/fixture update, odds age, API requests in the last 24 h per provider, warnings |
| `GET /model-health` | 30-day calibration metrics + drift status |

## Fixtures

| Endpoint | Description |
|---|---|
| `GET /fixtures/today?day=YYYY-MM-DD&days=1..7&competition=CODE` | fixtures in the window with analysis summary |
| `GET /fixtures/search?q=` | search by team name |
| `GET /fixtures/{id}` | full match page: features, feature snapshot, model probabilities per model, opportunities, odds + movement, form, H2H, team news |

## Value

| Endpoint | Description |
|---|---|
| `GET /value` | filterable value table. Query: `day, days, min_ev, min_confidence, min_quality, competition, market_group (csv), market, min_odds, max_odds, status (VALUE_CANDIDATE default; empty = all), selection, limit, movement` |
| `GET /value/today` | value candidates for the scan window |
| `GET /goals` · `GET /corners` · `GET /low-scoring` | strategy views |
| `GET /scanners/expected` | high-scoring / low-scoring / high-corner scanners (expected totals vs league average) |
| `GET /value/export?fmt=csv\|json` | export |

## Teams and leagues

| Endpoint | Description |
|---|---|
| `GET /teams?q=&competition=` | search |
| `GET /teams/{id}` | statistics (season/home/away/form), Elo, recent matches, injuries, transfers, manager changes |
| `POST /teams/manager-change` | record a manager change; computes before/after performance |
| `GET /leagues` · `GET /leagues/{code}` | league catalogue, averages, computed table |
| `PATCH /leagues/{code}/settings` | enable/disable, min sample, reliability, home advantage |

## Odds

| Endpoint | Description |
|---|---|
| `GET /odds/{fixture_id}` | per-market bookmaker comparison (best/median/min/max, overround, market probability, staleness), history and movement, unavailable markets |
| `GET /bookmakers` · `GET /markets` | reference data |

## Models and performance

| Endpoint | Description |
|---|---|
| `GET /models` | active model versions + registry |
| `GET /models/leaderboard` | Brier / log-loss / ECE / AUC / ROI / CLV per model, version and market group |
| `GET /performance?days&model&market_group` | calibration report, drift, strategy scores |
| `GET /performance/calibration` | reliability bins for charts |

## Backtesting

| Endpoint | Description |
|---|---|
| `GET /backtests?strategy=` | list + strategy names |
| `GET /backtests/comparison` | latest completed backtest per strategy |
| `GET /backtests/{id}` | summary, breakdowns, equity curve, bets |
| `POST /backtests/run` | body: `strategy, competition_codes, start, end, min_ev, min_confidence, min_data_quality, min_odds, max_odds, min_sample_size, stake_method, flat_stake, starting_bankroll, corner_distribution, min_expected_corners, min_expected_goals, exclude_early_red_cards, one_bet_per_fixture` |
| `POST /backtests/corner-thresholds` | ROI by expected-corner threshold × line |

## Paper betting and bankroll

| Endpoint | Description |
|---|---|
| `GET /paper-bets?status=` | list |
| `POST /paper-bets` | `{fixture_id, market_key, selection, odds, stake?, bookmaker_key?, opportunity_id?, notes?, stake_method?}` |
| `POST /paper-bets/settle` | settle open bets from results (adds closing odds + CLV) |
| `GET /paper-bets/stake-preview?probability&odds` | stake under each method (Kelly capped) |
| `GET /bankroll` · `POST /bankroll/snapshot` | bankroll state, equity curve, snapshots |

## Settings, data sources, reports, jobs

| Endpoint | Description |
|---|---|
| `GET /settings` · `GET /settings/{key}` · `PUT /settings/{key}` | groups: `value, form_weights, goal_model, corner_model, staking, bankroll, alerts, scanner` (validated) |
| `GET /data-sources` | provider capabilities and configuration status |
| `GET /reports/daily?day` · `GET /reports/daily/text` | daily report (JSON / text) |
| `GET /dashboard` | dashboard aggregate |
| `POST /scan` | `{scan_date?, days_ahead?, competition_codes?}` run models + value engine |
| `POST /jobs/{name}` | `update-fixtures, update-statistics, update-news, update-odds, settle, report, pipeline` |
| `POST /opportunities/{id}/explain` | optional LLM explanation of stored numbers |

## Opportunity object

```json
{
  "id": "…", "fixture_id": "…", "home_team": "…", "away_team": "…", "competition": "…", "kickoff_utc": "…",
  "market_key": "corners_over_9.5", "market": "Total Corners Over 9.5", "market_group": "corners", "selection": "over", "line": 9.5,
  "model_probability": 0.612, "market_probability": 0.455, "raw_implied_probability": 0.476,
  "best_odds": 2.20, "best_bookmaker": "…", "median_odds": 2.10, "bookmaker_count": 4,
  "fair_odds": 1.63, "edge": 0.157, "expected_value": 0.346, "value_label": "VERY_STRONG",
  "confidence": 82.0, "data_quality": 91.0, "value_score": 78.5,
  "status": "VALUE_CANDIDATE", "no_bet_reasons": [], "key_factors": ["…"], "risk_factors": ["…"],
  "explanation": "Model probability is 61.2%, compared with a normalised market probability of 45.5% …",
  "model_version": "corners-nb-1.0", "odds_recorded_at": "…", "scan_date": "…", "is_demo": false
}
```
