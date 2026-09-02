"""API-Football (api-sports.io) v3 provider.

Docs: https://www.api-football.com/documentation-v3
Auth: header `x-apisports-key`. Free tier: 100 requests/day, seasons limited (typically current -2..current),
and no odds/injuries on free. Paid tiers add per-fixture statistics (corners, shots, possession, xG on
some competitions), injuries, players, pre-match odds from ~15 bookmakers (Over/Under, corners markets).

Field mapping (see docs/DATA_PROVIDERS.md):
  fixtures/results/HT scores -> /fixtures
  corners, shots, SOT, possession, xG (expected_goals) -> /fixtures/statistics
  injuries -> /injuries
  squads/players -> /players
  odds -> /odds (bet ids: 1 Match Winner, 5 Goals O/U, 8 BTTS, 45 Corners O/U, 12 Double Chance,
                 10 Draw No Bet, 4 Asian Handicap, 6 Goals O/U 1st Half, 16 Home Goals O/U, 17 Away Goals O/U)
"""
from __future__ import annotations

from datetime import UTC, date, datetime

from app.config import get_settings
from app.providers.base import (
    CompetitionDTO,
    FixtureDTO,
    FootballDataProvider,
    InjuryDataProvider,
    InjuryDTO,
    OddsDataProvider,
    OddsDTO,
    PlayerDTO,
    ProviderCapabilities,
    ProviderNotConfigured,
    TeamDTO,
    TeamMatchStatsDTO,
)
from app.providers.http import CachedHttpClient
from app.providers.leagues import LEAGUE_BY_CODE, LEAGUES

STATUS_MAP = {
    "TBD": "SCHEDULED", "NS": "SCHEDULED", "1H": "LIVE", "HT": "LIVE", "2H": "LIVE", "ET": "LIVE", "BT": "LIVE",
    "P": "LIVE", "SUSP": "POSTPONED", "INT": "POSTPONED", "FT": "FINISHED", "AET": "FINISHED", "PEN": "FINISHED",
    "PST": "POSTPONED", "CANC": "CANCELLED", "ABD": "CANCELLED", "AWD": "FINISHED", "WO": "FINISHED", "LIVE": "LIVE",
}

# API-Football bet id -> (internal market prefix builder)
BET_IDS = {1: "match", 5: "goals", 8: "btts", 45: "corners", 12: "dc", 10: "dnb", 6: "1h_goals", 16: "home_goals", 17: "away_goals"}


def _num(v):
    if v is None:
        return None
    if isinstance(v, str):
        v = v.replace("%", "").strip()
        if v == "":
            return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _int(v):
    n = _num(v)
    return int(n) if n is not None else None


def map_odds_value(bet_id: int, value: str) -> tuple[str, str, float | None] | None:
    """Translate an API-Football (bet id, value label) into (market_key, selection, line)."""
    v = value.strip()
    if bet_id == 1:
        return {"Home": ("match_home", "home", None), "Draw": ("match_draw", "draw", None), "Away": ("match_away", "away", None)}.get(v)
    if bet_id == 8:
        return ("btts_yes", "yes", None) if v == "Yes" else ("btts_no", "no", None) if v == "No" else None
    if bet_id == 12:
        return {"Home/Draw": ("dc_home_draw", "home_draw", None), "Home/Away": ("dc_home_away", "home_away", None), "Draw/Away": ("dc_draw_away", "draw_away", None)}.get(v)
    if bet_id == 10:
        return {"Home": ("dnb_home", "home", None), "Away": ("dnb_away", "away", None)}.get(v)
    prefix = {5: "goals", 45: "corners", 6: "1h_goals", 16: "home_goals", 17: "away_goals"}.get(bet_id)
    if prefix and (v.startswith("Over ") or v.startswith("Under ")):
        sel, line_s = v.split(" ", 1)
        try:
            line = float(line_s)
        except ValueError:
            return None
        if line != int(line) + 0.5:
            return None  # whole/quarter lines are not in the registry
        return (f"{prefix}_{sel.lower()}_{line}", sel.lower(), line)
    return None


class ApiFootballProvider(FootballDataProvider, OddsDataProvider, InjuryDataProvider):
    name = "api_football"
    capabilities = ProviderCapabilities(
        fixtures=True, results=True, half_time_scores=True, corners=True, xg=True, shots=True, possession=True,
        cards=True, players=True, injuries=True, odds=True, odds_history=False, corner_odds=True,
        notes="Per-fixture statistics, injuries and odds require a paid plan. xG only on selected competitions. HT corners not provided.",
    )

    def __init__(self, session_factory=None):
        s = get_settings()
        if not s.api_football_key:
            raise ProviderNotConfigured("API_FOOTBALL_KEY is not set")
        self.http = CachedHttpClient(self.name, s.api_football_base_url, headers={"x-apisports-key": s.api_football_key}, default_ttl=1800, session_factory=session_factory)

    async def _get(self, path: str, params: dict, ttl: int) -> list:
        data = await self.http.get_json(path, params, ttl=ttl)
        if data.get("errors"):
            from app.providers.base import ProviderUnavailable

            raise ProviderUnavailable(f"api_football error: {data['errors']}")
        return data.get("response", [])

    # --- football -----------------------------------------------------
    async def get_competitions(self) -> list[CompetitionDTO]:
        return [CompetitionDTO(self.name, str(lg.api_football), lg.code, lg.name, lg.country, lg.tier) for lg in LEAGUES if lg.api_football]

    async def get_teams(self, competition_code: str, season_year: int) -> list[TeamDTO]:
        lg = LEAGUE_BY_CODE[competition_code]
        rows = await self._get("teams", {"league": lg.api_football, "season": season_year}, 86400)
        return [TeamDTO(self.name, str(r["team"]["id"]), r["team"]["name"], r["team"].get("code"), r["team"].get("country"), competition_code) for r in rows]

    def _fixture(self, r: dict, competition_code: str, season_year: int) -> FixtureDTO:
        f, t, g, s = r["fixture"], r["teams"], r.get("goals", {}), r.get("score", {})
        status = STATUS_MAP.get(f.get("status", {}).get("short", "NS"), "SCHEDULED")
        ht = s.get("halftime", {}) or {}
        return FixtureDTO(
            source=self.name, source_id=str(f["id"]), competition_code=competition_code, season_year=season_year,
            home_team_source_id=str(t["home"]["id"]), away_team_source_id=str(t["away"]["id"]),
            home_team_name=t["home"]["name"], away_team_name=t["away"]["name"],
            kickoff_utc=datetime.fromtimestamp(f["timestamp"], tz=UTC), status=status,
            matchday=None, venue=(f.get("venue") or {}).get("name"),
            home_goals=g.get("home") if status == "FINISHED" else None, away_goals=g.get("away") if status == "FINISHED" else None,
            home_goals_ht=ht.get("home") if status == "FINISHED" else None, away_goals_ht=ht.get("away") if status == "FINISHED" else None,
        )

    async def get_fixtures(self, competition_code: str, season_year: int, date_from: date | None = None, date_to: date | None = None) -> list[FixtureDTO]:
        lg = LEAGUE_BY_CODE[competition_code]
        params: dict = {"league": lg.api_football, "season": season_year}
        if date_from:
            params["from"] = date_from.isoformat()
        if date_to:
            params["to"] = date_to.isoformat()
        rows = await self._get("fixtures", params, 900)
        return [self._fixture(r, competition_code, season_year) for r in rows]

    async def get_results(self, competition_code: str, season_year: int) -> list[FixtureDTO]:
        lg = LEAGUE_BY_CODE[competition_code]
        rows = await self._get("fixtures", {"league": lg.api_football, "season": season_year, "status": "FT-AET-PEN"}, 3600)
        return [self._fixture(r, competition_code, season_year) for r in rows]

    async def get_fixture_statistics(self, fixture_source_id: str) -> list[TeamMatchStatsDTO]:
        rows = await self._get("fixtures/statistics", {"fixture": fixture_source_id}, 30 * 86400)
        out: list[TeamMatchStatsDTO] = []
        for i, r in enumerate(rows):
            stats = {s["type"]: s["value"] for s in r.get("statistics", [])}
            out.append(
                TeamMatchStatsDTO(
                    source=self.name, fixture_source_id=fixture_source_id, team_source_id=str(r["team"]["id"]), is_home=(i == 0),
                    xg=_num(stats.get("expected_goals")), shots=_int(stats.get("Total Shots")), shots_on_target=_int(stats.get("Shots on Goal")),
                    possession=_num(stats.get("Ball Possession")), corners=_int(stats.get("Corner Kicks")),
                    yellow_cards=_int(stats.get("Yellow Cards")), red_cards=_int(stats.get("Red Cards")), fouls=_int(stats.get("Fouls")),
                )
            )
        return out

    async def get_team_statistics(self, team_source_id: str, competition_code: str, season_year: int) -> dict:
        lg = LEAGUE_BY_CODE[competition_code]
        rows = await self._get("teams/statistics", {"team": team_source_id, "league": lg.api_football, "season": season_year}, 86400)
        return rows if isinstance(rows, dict) else {}

    async def get_player_information(self, team_source_id: str, season_year: int) -> list[PlayerDTO]:
        rows = await self._get("players", {"team": team_source_id, "season": season_year}, 86400)
        out = []
        for r in rows:
            p = r["player"]
            st = (r.get("statistics") or [{}])[0]
            games, goals = st.get("games", {}), st.get("goals", {})
            out.append(PlayerDTO(self.name, str(p["id"]), p["name"], team_source_id, games.get("position"), games.get("minutes"), goals.get("total"), goals.get("assists"), games.get("appearences")))
        return out

    # --- injuries -----------------------------------------------------
    async def get_team_injuries(self, team_source_id: str, competition_code: str, season_year: int) -> list[InjuryDTO]:
        lg = LEAGUE_BY_CODE[competition_code]
        rows = await self._get("injuries", {"team": team_source_id, "league": lg.api_football, "season": season_year}, 6 * 3600)
        out = []
        for r in rows:
            p = r["player"]
            status = "doubtful" if (p.get("type") or "").lower().startswith("questionable") else "out"
            out.append(InjuryDTO(self.name, team_source_id, p["name"], str(p["id"]), p.get("reason"), status, fixture_source_id=str(r["fixture"]["id"]) if r.get("fixture") else None))
        return out

    async def get_player_status(self, player_source_id: str) -> InjuryDTO | None:
        return None

    # --- odds ---------------------------------------------------------
    async def get_bookmakers(self) -> list[dict]:
        rows = await self._get("odds/bookmakers", {}, 7 * 86400)
        return [{"key": f"af_{r['id']}", "name": r["name"]} for r in rows]

    async def get_match_odds(self, competition_code: str, date_from: date | None = None, date_to: date | None = None) -> list[OddsDTO]:
        return await self.get_market_odds(competition_code, [], date_from, date_to)

    async def get_market_odds(self, competition_code: str, market_keys: list[str], date_from: date | None = None, date_to: date | None = None) -> list[OddsDTO]:
        lg = LEAGUE_BY_CODE[competition_code]
        season = date_from.year if date_from and (date_from.month >= 7 or lg.summer_season) else (date_from.year - 1 if date_from else datetime.now(UTC).year)
        out: list[OddsDTO] = []
        page = 1
        while True:
            data = await self.http.get_json("odds", {"league": lg.api_football, "season": season, "page": page}, ttl=900)
            now = datetime.now(UTC)
            for r in data.get("response", []):
                fid = str(r["fixture"]["id"])
                for bm in r.get("bookmakers", []):
                    for bet in bm.get("bets", []):
                        if bet["id"] not in BET_IDS:
                            continue
                        for v in bet.get("values", []):
                            mapped = map_odds_value(bet["id"], str(v["value"]))
                            if not mapped:
                                continue
                            mk, sel, line = mapped
                            if market_keys and mk not in market_keys:
                                continue
                            try:
                                odds = float(v["odd"])
                            except (TypeError, ValueError):
                                continue
                            if odds <= 1.0:
                                continue
                            out.append(OddsDTO(self.name, fid, f"af_{bm['id']}", bm["name"], mk, sel, line, odds, now))
            paging = data.get("paging", {})
            if page >= paging.get("total", 1):
                break
            page += 1
        return out

    async def get_market_history(self, fixture_source_id: str, market_key: str) -> list[OddsDTO]:
        return []  # not provided by the API; movement is tracked from our own stored snapshots
