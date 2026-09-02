# Data providers

All providers implement the interfaces in `backend/app/providers/base.py`. Fields a provider cannot supply are
`None` → stored as `NULL` → shown as **DATA UNAVAILABLE**. Nothing is fabricated. Every stored record carries
`source`, `source_id`, `retrieved_at`, `last_updated_at`. Every HTTP call goes through
`providers/http.py` (timeouts, 3 retries with exponential backoff, 429 handling with Retry-After, on-disk JSON
cache with per-endpoint TTL, logging to `api_requests` without secrets).

Provider selection: `APP_MODE=demo` → demo provider only. `APP_MODE=production` → `FOOTBALL_PROVIDER`
(`api_football` preferred, `football_data` fallback) and `ODDS_PROVIDER` (`the_odds_api` or `api_football`).
Missing keys → `Production data provider not configured.` (no silent fallback to fake data).

## Field → provider mapping

| Field | API-Football | football-data.org | The Odds API | Demo |
|---|---|---|---|---|
| Competitions, seasons | `/leagues` (ids in `providers/leagues.py`) | 12 free competitions (`PL, ELC, PD, BL1, SA, FL1, DED, PPL …`) | sport keys | 2 synthetic leagues |
| Fixtures, results, HT scores | `/fixtures` | `/competitions/{code}/matches` | – | ✔ |
| Corners | `/fixtures/statistics` → `Corner Kicks` (paid) | ✘ | ✘ | ✔ (+ HT corners) |
| Shots / on target / possession / cards / fouls | `/fixtures/statistics` (paid) | ✘ | ✘ | ✔ (no possession) |
| xG | `/fixtures/statistics` → `expected_goals` (selected leagues, paid) | ✘ | ✘ | ✔ |
| Players, minutes, goals, assists | `/players` (paid tiers for full history) | squad list only (`/teams/{id}`) | ✘ | ✘ |
| Injuries / suspensions | `/injuries` (paid) | ✘ | ✘ | ✔ (synthetic) |
| Odds 1X2 / totals / BTTS / DC / DNB / team totals / 1H totals | `/odds` bet ids 1, 5, 8, 12, 10, 16, 17, 6 (paid) | ✘ | `h2h, totals, btts, team_totals, totals_h1, spreads` | ✔ |
| Corner odds | `/odds` bet id 45 (paid) | ✘ | **not offered** | ✔ |
| Odds history / closing | ✘ (platform stores its own snapshots) | ✘ | paid historical endpoint (not wired) | ✔ (opening + closing) |
| Weather | – | – | – | Open-Meteo (no key), informational only |
| Transfers, manager changes | `/transfers`, `/coachs` exist (not wired; manual entry via API) | ✘ | ✘ | ✘ |

## API-Football (api-sports.io) — `providers/football/api_football.py`

* Docs: https://www.api-football.com/documentation-v3 — auth header `x-apisports-key`.
* Free plan: 100 requests/day, limited seasons, no odds/injuries/statistics. Paid plans (Pro/Ultra/Mega) raise
  the limit to 7,500–75,000+/day and unlock per-fixture statistics, injuries, players and pre-match odds from
  ~15 bookmakers including corner O/U.
* Cost control: fixtures per league+season are one request (cached 15 min for upcoming, 1 h for results);
  statistics are fetched **once per finished fixture** and cached 30 days; odds per league+season page cached
  15 min; injuries per team cached 6 h.
* Limitations: xG only for some competitions; no half-time corners; "questionable" injury types are mapped to
  `doubtful`; league availability by plan.

## football-data.org — `providers/football/football_data_org.py`

* Docs: https://www.football-data.org/documentation/quickstart — header `X-Auth-Token`.
* Free tier: 10 requests/min, 12 competitions, fixtures/results/half-time scores/tables. No statistics,
  injuries or odds. Used as fixture/result fallback; the platform will then mark corners/xG/shots unavailable
  and the corner model will not run for those leagues.

## The Odds API — `providers/odds/the_odds_api.py`

* Docs: https://the-odds-api.com/liveapi/guides/v4/ — `apiKey` query parameter.
* Free tier: 500 credits/month; a request costs regions × markets credits. Regions `uk,eu` by default.
* Markets: `h2h`, `totals` (and `alternate_totals`), `btts`, `team_totals`, `totals_h1`, `spreads` (some only
  via the per-event endpoint on paid tiers). **No corner markets.**
* Fixtures are matched by normalised team names + kickoff date; unmatched prices are counted in
  `unmatched` and discarded (logged).

## Open-Meteo — `providers/weather/open_meteo.py`

No key. Hourly temperature, precipitation, wind, humidity, snowfall at kickoff. Stored for information; no
model weight until a backtest justifies it (venue coordinates are not supplied by the football providers'
free tiers, so this is opt-in).

## Demo provider — `providers/football/demo.py`

Deterministic (seeded) synthetic world: 2 leagues (20 and 16 teams), 3 seasons anchored so that "today" is
~12 rounds into the latest season, latent attack/defence/corner strengths, Dixon-Coles-style low-score
correlation, over-dispersed corners, occasional early red cards, half-time splits, xG/shots, synthetic
injuries, 4 bookmakers with margins 2–7 % pricing noisy versions of the latent probabilities (some markets
deliberately unpriced to exercise "MARKET UNAVAILABLE"), opening and closing odds for backtests. Everything is
labelled `source="demo"` / `is_demo=true` and production mode never loads it.

## Adding a provider

1. Implement the relevant interface(s) in `providers/<kind>/<name>.py`, returning DTOs with `None` for
   unsupported fields and an honest `ProviderCapabilities`.
2. Add league ids to `providers/leagues.py`.
3. Register it in `providers/factory.py` and document it here and in `GET /api/data-sources`.
