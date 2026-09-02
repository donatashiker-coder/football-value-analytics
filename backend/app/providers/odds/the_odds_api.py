"""The Odds API v4 provider.

Docs: https://the-odds-api.com/liveapi/guides/v4/
Auth: `apiKey` query parameter. Free tier: 500 requests/month; each region/market combination costs
credits (cost = regions x markets per request). Markets: h2h, spreads, totals (plus alternate_totals,
btts, team_totals, h2h_h1, totals_h1 on paid tiers via the event-odds endpoint). Corner markets are NOT
offered by The Odds API; corner prices must come from API-Football.
Fixtures are matched to our database by (home team name, away team name, kickoff) so the service layer
performs fuzzy name resolution; unmatched prices are logged and discarded.
"""
from __future__ import annotations

from datetime import UTC, date, datetime

from app.config import get_settings
from app.providers.base import OddsDataProvider, OddsDTO, ProviderCapabilities, ProviderNotConfigured
from app.providers.http import CachedHttpClient
from app.providers.leagues import LEAGUE_BY_CODE

MARKET_REQUEST = {"match_result": "h2h", "goals": "totals", "btts": "btts", "team_goals": "team_totals", "first_half": "totals_h1", "handicap": "spreads"}
# The sports/{sport}/odds list endpoint accepts only the featured markets on every plan; btts,
# team_totals and totals_h1 are served solely by the per-event odds endpoint and return 422 here.
FEATURED_MARKETS = {"h2h", "totals", "spreads"}


class TheOddsApiProvider(OddsDataProvider):
    name = "the_odds_api"
    capabilities = ProviderCapabilities(odds=True, odds_history=True, corner_odds=False, notes="No corner markets. Historical odds require a paid plan.")

    def __init__(self, session_factory=None):
        s = get_settings()
        if not s.odds_api_key:
            raise ProviderNotConfigured("ODDS_API_KEY is not set")
        self.key = s.odds_api_key
        self.http = CachedHttpClient(self.name, "https://api.the-odds-api.com/v4", default_ttl=900, session_factory=session_factory, quota_headers=("x-requests-remaining", "x-requests-used"))
        self.regions = "uk,eu"

    async def get_bookmakers(self) -> list[dict]:
        return []  # bookmakers are discovered from odds responses

    def _parse_event(self, ev: dict, now: datetime) -> list[OddsDTO]:
        out: list[OddsDTO] = []
        home, away = ev["home_team"], ev["away_team"]
        kickoff = datetime.fromisoformat(ev["commence_time"].replace("Z", "+00:00")).astimezone(UTC)
        for bm in ev.get("bookmakers", []):
            ts = datetime.fromisoformat(bm["last_update"].replace("Z", "+00:00")).astimezone(UTC) if bm.get("last_update") else now
            for mk in bm.get("markets", []):
                key = mk["key"]
                for o in mk.get("outcomes", []):
                    price = float(o["price"])
                    if price <= 1.0:
                        continue
                    name, point = o["name"], o.get("point")
                    mapped: tuple[str, str, float | None] | None = None
                    if key == "h2h":
                        mapped = ("match_home", "home", None) if name == home else ("match_away", "away", None) if name == away else ("match_draw", "draw", None) if name == "Draw" else None
                    elif key in ("totals", "alternate_totals") and point is not None and float(point) % 1 == 0.5:
                        mapped = (f"goals_{name.lower()}_{float(point)}", name.lower(), float(point))
                    elif key == "totals_h1" and point is not None and float(point) % 1 == 0.5:
                        mapped = (f"1h_goals_{name.lower()}_{float(point)}", name.lower(), float(point))
                    elif key == "btts":
                        mapped = ("btts_yes", "yes", None) if name == "Yes" else ("btts_no", "no", None)
                    elif key == "team_totals" and point is not None and float(point) % 1 == 0.5:
                        side = "home" if o.get("description") == home else "away"
                        mapped = (f"{side}_goals_{name.lower()}_{float(point)}", name.lower(), float(point))
                    elif key == "spreads" and point is not None:
                        p = float(point)
                        if name == home and p in (-1.5, -1.0, -0.5, 0.0, 0.5, 1.0, 1.5):
                            mapped = (f"ah_home_{p:+.1f}", "home", p)
                        elif name == away and p in (-1.5, -1.0, -0.5, 0.0, 0.5, 1.0, 1.5):
                            mapped = (f"ah_away_{p:+.1f}", "away", p)
                    if mapped is None:
                        continue
                    m_key, sel, line = mapped
                    out.append(OddsDTO(self.name, ev["id"], bm["key"], bm["title"], m_key, sel, line, price, ts, home, away, kickoff))
        return out

    async def get_match_odds(self, competition_code: str, date_from: date | None = None, date_to: date | None = None) -> list[OddsDTO]:
        return await self.get_market_odds(competition_code, ["match_result", "goals", "btts"], date_from, date_to)

    async def get_market_odds(self, competition_code: str, market_keys: list[str], date_from: date | None = None, date_to: date | None = None) -> list[OddsDTO]:
        lg = LEAGUE_BY_CODE[competition_code]
        if not lg.the_odds_api:
            return []
        requested = {MARKET_REQUEST[g] for g in market_keys if g in MARKET_REQUEST} & FEATURED_MARKETS
        markets = ",".join(sorted(requested or {"h2h", "totals"}))
        params = {"apiKey": self.key, "regions": self.regions, "markets": markets, "oddsFormat": "decimal", "dateFormat": "iso"}
        if date_from:
            params["commenceTimeFrom"] = f"{date_from.isoformat()}T00:00:00Z"
        if date_to:
            params["commenceTimeTo"] = f"{date_to.isoformat()}T23:59:59Z"
        data = await self.http.get_json(f"sports/{lg.the_odds_api}/odds", params, ttl=900)
        now = datetime.now(UTC)
        out: list[OddsDTO] = []
        for ev in data:
            out.extend(self._parse_event(ev, now))
        return out

    async def get_market_history(self, fixture_source_id: str, market_key: str) -> list[OddsDTO]:
        return []  # historical endpoint is paid-only; movement is tracked from stored snapshots
