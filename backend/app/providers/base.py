"""Provider interfaces. Every concrete provider (real or demo) implements these.

Data transfer objects are plain dataclasses so providers stay decoupled from the ORM.
Fields a provider cannot supply are left as None: they are NEVER fabricated.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date, datetime


@dataclass
class CompetitionDTO:
    source: str
    source_id: str
    code: str  # internal code, e.g. ENG_PL
    name: str
    country: str
    tier: int = 1
    current_season_year: int | None = None


@dataclass
class TeamDTO:
    source: str
    source_id: str
    name: str
    short_name: str | None = None
    country: str | None = None
    competition_code: str | None = None


@dataclass
class FixtureDTO:
    source: str
    source_id: str
    competition_code: str
    season_year: int
    home_team_source_id: str
    away_team_source_id: str
    home_team_name: str
    away_team_name: str
    kickoff_utc: datetime
    status: str = "SCHEDULED"
    matchday: int | None = None
    venue: str | None = None
    # result (only populated when status == FINISHED)
    home_goals: int | None = None
    away_goals: int | None = None
    home_goals_ht: int | None = None
    away_goals_ht: int | None = None
    last_updated_at: datetime | None = None


@dataclass
class TeamMatchStatsDTO:
    """Post-match statistics for one team in one fixture."""

    source: str
    fixture_source_id: str
    team_source_id: str
    is_home: bool
    goals: int | None = None
    xg: float | None = None
    shots: int | None = None
    shots_on_target: int | None = None
    possession: float | None = None
    corners: int | None = None
    corners_ht: int | None = None
    yellow_cards: int | None = None
    red_cards: int | None = None
    fouls: int | None = None
    first_red_card_minute: int | None = None
    extra: dict = field(default_factory=dict)


@dataclass
class PlayerDTO:
    source: str
    source_id: str
    name: str
    team_source_id: str | None
    position: str | None = None
    minutes: int | None = None
    goals: int | None = None
    assists: int | None = None
    appearances: int | None = None
    xg: float | None = None
    xa: float | None = None


@dataclass
class OddsDTO:
    source: str
    fixture_source_id: str  # provider's fixture id OR a match key (home|away|kickoff) resolved by the service
    bookmaker_key: str
    bookmaker_name: str
    market_key: str  # internal market key
    selection: str
    line: float | None
    decimal_odds: float
    recorded_at: datetime
    home_team_name: str | None = None
    away_team_name: str | None = None
    kickoff_utc: datetime | None = None


@dataclass
class InjuryDTO:
    source: str
    team_source_id: str
    player_name: str
    player_source_id: str | None = None
    reason: str | None = None
    status: str = "out"  # out | doubtful | questionable | suspended
    reported_at: datetime | None = None
    expected_return: date | None = None
    fixture_source_id: str | None = None


@dataclass
class NewsItemDTO:
    source: str
    team_source_id: str
    headline: str
    published_at: datetime
    url: str | None = None
    summary: str | None = None


@dataclass
class WeatherDTO:
    source: str
    fixture_source_id: str
    temperature_c: float | None = None
    rain_mm: float | None = None
    wind_kph: float | None = None
    humidity: float | None = None
    snow: bool | None = None


@dataclass
class ProviderCapabilities:
    """What this provider can actually supply. Unsupported fields are marked unavailable in the UI."""

    fixtures: bool = False
    results: bool = False
    half_time_scores: bool = False
    corners: bool = False
    xg: bool = False
    shots: bool = False
    possession: bool = False
    cards: bool = False
    players: bool = False
    injuries: bool = False
    odds: bool = False
    odds_history: bool = False
    corner_odds: bool = False
    notes: str = ""


class FootballDataProvider(ABC):
    name: str = "base"
    capabilities: ProviderCapabilities = ProviderCapabilities()

    @abstractmethod
    async def get_competitions(self) -> list[CompetitionDTO]: ...

    @abstractmethod
    async def get_teams(self, competition_code: str, season_year: int) -> list[TeamDTO]: ...

    @abstractmethod
    async def get_fixtures(self, competition_code: str, season_year: int, date_from: date | None = None, date_to: date | None = None) -> list[FixtureDTO]: ...

    @abstractmethod
    async def get_results(self, competition_code: str, season_year: int) -> list[FixtureDTO]: ...

    @abstractmethod
    async def get_fixture_statistics(self, fixture_source_id: str) -> list[TeamMatchStatsDTO]: ...

    @abstractmethod
    async def get_team_statistics(self, team_source_id: str, competition_code: str, season_year: int) -> dict: ...

    @abstractmethod
    async def get_player_information(self, team_source_id: str, season_year: int) -> list[PlayerDTO]: ...


class OddsDataProvider(ABC):
    name: str = "base"
    capabilities: ProviderCapabilities = ProviderCapabilities()

    @abstractmethod
    async def get_bookmakers(self) -> list[dict]: ...

    @abstractmethod
    async def get_match_odds(self, competition_code: str, date_from: date | None = None, date_to: date | None = None) -> list[OddsDTO]: ...

    @abstractmethod
    async def get_market_odds(self, competition_code: str, market_keys: list[str], date_from: date | None = None, date_to: date | None = None) -> list[OddsDTO]: ...

    @abstractmethod
    async def get_market_history(self, fixture_source_id: str, market_key: str) -> list[OddsDTO]: ...


class InjuryDataProvider(ABC):
    name: str = "base"

    @abstractmethod
    async def get_team_injuries(self, team_source_id: str, competition_code: str, season_year: int) -> list[InjuryDTO]: ...

    @abstractmethod
    async def get_player_status(self, player_source_id: str) -> InjuryDTO | None: ...


class NewsDataProvider(ABC):
    name: str = "base"

    @abstractmethod
    async def get_team_news(self, team_name: str, days: int = 3) -> list[NewsItemDTO]: ...


class WeatherDataProvider(ABC):
    name: str = "base"

    @abstractmethod
    async def get_fixture_weather(self, fixture_source_id: str, latitude: float, longitude: float, kickoff_utc: datetime) -> WeatherDTO | None: ...


class ProviderNotConfigured(Exception):
    """Raised when production mode is requested without the required API key."""


class ProviderUnavailable(Exception):
    """Raised after retries are exhausted; callers must degrade gracefully."""
