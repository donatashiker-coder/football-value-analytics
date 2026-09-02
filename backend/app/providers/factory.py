"""Resolve the configured provider set. Demo and production are never mixed."""
from __future__ import annotations

from dataclasses import dataclass

from app.config import Settings, get_settings
from app.providers.base import (
    FootballDataProvider,
    InjuryDataProvider,
    OddsDataProvider,
    ProviderNotConfigured,
    WeatherDataProvider,
)


@dataclass
class ProviderSet:
    mode: str
    football: FootballDataProvider
    odds: OddsDataProvider | None
    injuries: InjuryDataProvider | None
    weather: WeatherDataProvider | None
    warnings: list[str]

    @property
    def is_demo(self) -> bool:
        return self.mode == "demo"


_demo_singleton = None


def get_demo_provider():
    global _demo_singleton
    if _demo_singleton is None:
        from app.providers.football.demo import DemoProvider

        _demo_singleton = DemoProvider()
    return _demo_singleton


def build_providers(settings: Settings | None = None, session_factory=None) -> ProviderSet:
    s = settings or get_settings()
    if s.is_demo:
        demo = get_demo_provider()
        return ProviderSet("demo", demo, demo, demo, None, ["DEMO MODE: all data is synthetic and clearly labelled"])

    warnings: list[str] = []
    football: FootballDataProvider | None = None
    injuries: InjuryDataProvider | None = None
    odds: OddsDataProvider | None = None

    if s.football_provider == "api_football":
        try:
            from app.providers.football.api_football import ApiFootballProvider

            af = ApiFootballProvider(session_factory)
            football, injuries = af, af
            if s.odds_provider == "api_football":
                odds = af
        except ProviderNotConfigured as exc:
            warnings.append(str(exc))
    if football is None:
        try:
            from app.providers.football.football_data_org import FootballDataOrgProvider

            football = FootballDataOrgProvider(session_factory)
            warnings.append("Using football-data.org: corners/xG/shots/injuries unavailable on this provider")
        except ProviderNotConfigured as exc:
            warnings.append(str(exc))
    if football is None:
        raise ProviderNotConfigured("Production data provider not configured. Set API_FOOTBALL_KEY or FOOTBALL_DATA_API_KEY, or use APP_MODE=demo.")

    if odds is None and s.odds_provider == "the_odds_api":
        try:
            from app.providers.odds.the_odds_api import TheOddsApiProvider

            odds = TheOddsApiProvider(session_factory)
        except ProviderNotConfigured as exc:
            warnings.append(str(exc))
    if odds is None:
        warnings.append("Odds provider not configured: value calculation will report ODDS UNAVAILABLE")

    from app.providers.weather.open_meteo import OpenMeteoProvider

    return ProviderSet("production", football, odds, injuries, OpenMeteoProvider(session_factory), warnings)
