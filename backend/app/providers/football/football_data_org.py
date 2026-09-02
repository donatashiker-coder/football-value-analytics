"""football-data.org v4 provider.

Docs: https://www.football-data.org/documentation/quickstart
Auth: header `X-Auth-Token`. Free tier: 10 requests/minute, 12 competitions (PL, ELC, PD, BL1, SA, FL1,
DED, PPL, CL, EC, WC, BSA), fixtures/results/tables, half-time scores. NO corners, shots, xG, injuries
or odds on the free tier. Used as the fixtures/results source when API-Football is not configured.
"""
from __future__ import annotations

from datetime import UTC, date, datetime

from app.config import get_settings
from app.providers.base import (
    CompetitionDTO,
    FixtureDTO,
    FootballDataProvider,
    PlayerDTO,
    ProviderCapabilities,
    ProviderNotConfigured,
    TeamDTO,
    TeamMatchStatsDTO,
)
from app.providers.http import CachedHttpClient
from app.providers.leagues import LEAGUE_BY_CODE, LEAGUES

STATUS_MAP = {
    "SCHEDULED": "SCHEDULED",
    "TIMED": "SCHEDULED",
    "IN_PLAY": "LIVE",
    "PAUSED": "LIVE",
    "FINISHED": "FINISHED",
    "POSTPONED": "POSTPONED",
    "SUSPENDED": "POSTPONED",
    "CANCELLED": "CANCELLED",
    "AWARDED": "FINISHED",
}


class FootballDataOrgProvider(FootballDataProvider):
    name = "football_data"
    capabilities = ProviderCapabilities(
        fixtures=True,
        results=True,
        half_time_scores=True,
        notes="Free tier: top-flight leagues only; no corners/xG/shots/injuries/odds.",
    )

    def __init__(self, session_factory=None):
        s = get_settings()
        if not s.football_data_api_key:
            raise ProviderNotConfigured("FOOTBALL_DATA_API_KEY is not set")
        self.http = CachedHttpClient(
            self.name, "https://api.football-data.org/v4", headers={"X-Auth-Token": s.football_data_api_key}, default_ttl=1800, session_factory=session_factory
        )

    async def get_competitions(self) -> list[CompetitionDTO]:
        return [
            CompetitionDTO(self.name, lg.football_data, lg.code, lg.name, lg.country, lg.tier)
            for lg in LEAGUES
            if lg.football_data
        ]

    async def get_teams(self, competition_code: str, season_year: int) -> list[TeamDTO]:
        lg = LEAGUE_BY_CODE[competition_code]
        if not lg.football_data:
            return []
        data = await self.http.get_json(f"competitions/{lg.football_data}/teams", {"season": season_year}, ttl=86400)
        return [TeamDTO(self.name, str(t["id"]), t["name"], t.get("shortName"), t.get("area", {}).get("name"), competition_code) for t in data.get("teams", [])]

    def _fixture(self, m: dict, competition_code: str, season_year: int) -> FixtureDTO:
        score = m.get("score", {})
        ft = score.get("fullTime", {}) or {}
        ht = score.get("halfTime", {}) or {}
        status = STATUS_MAP.get(m.get("status", ""), "SCHEDULED")
        return FixtureDTO(
            source=self.name,
            source_id=str(m["id"]),
            competition_code=competition_code,
            season_year=season_year,
            home_team_source_id=str(m["homeTeam"]["id"]),
            away_team_source_id=str(m["awayTeam"]["id"]),
            home_team_name=m["homeTeam"]["name"],
            away_team_name=m["awayTeam"]["name"],
            kickoff_utc=datetime.fromisoformat(m["utcDate"].replace("Z", "+00:00")).astimezone(UTC),
            status=status,
            matchday=m.get("matchday"),
            home_goals=ft.get("home") if status == "FINISHED" else None,
            away_goals=ft.get("away") if status == "FINISHED" else None,
            home_goals_ht=ht.get("home") if status == "FINISHED" else None,
            away_goals_ht=ht.get("away") if status == "FINISHED" else None,
            last_updated_at=datetime.fromisoformat(m["lastUpdated"].replace("Z", "+00:00")) if m.get("lastUpdated") else None,
        )

    async def get_fixtures(self, competition_code: str, season_year: int, date_from: date | None = None, date_to: date | None = None) -> list[FixtureDTO]:
        lg = LEAGUE_BY_CODE[competition_code]
        if not lg.football_data:
            return []
        params: dict = {"season": season_year}
        if date_from:
            params["dateFrom"] = date_from.isoformat()
        if date_to:
            params["dateTo"] = date_to.isoformat()
        data = await self.http.get_json(f"competitions/{lg.football_data}/matches", params, ttl=900)
        return [self._fixture(m, competition_code, season_year) for m in data.get("matches", [])]

    async def get_results(self, competition_code: str, season_year: int) -> list[FixtureDTO]:
        lg = LEAGUE_BY_CODE[competition_code]
        if not lg.football_data:
            return []
        data = await self.http.get_json(f"competitions/{lg.football_data}/matches", {"season": season_year, "status": "FINISHED"}, ttl=3600)
        return [self._fixture(m, competition_code, season_year) for m in data.get("matches", [])]

    async def get_fixture_statistics(self, fixture_source_id: str) -> list[TeamMatchStatsDTO]:
        return []  # not available on this provider: marked unavailable, never fabricated

    async def get_team_statistics(self, team_source_id: str, competition_code: str, season_year: int) -> dict:
        return {}

    async def get_player_information(self, team_source_id: str, season_year: int) -> list[PlayerDTO]:
        data = await self.http.get_json(f"teams/{team_source_id}", ttl=86400)
        return [PlayerDTO(self.name, str(p["id"]), p["name"], team_source_id, p.get("position")) for p in data.get("squad", [])]
