"""Supported league catalogue with provider identifiers.

Provider IDs (documented from the public API references, see docs/DATA_PROVIDERS.md):
- api_football: league ids from API-Football v3
- football_data: competition codes from football-data.org v4 (free tier covers only a subset)
- the_odds_api: sport keys from The Odds API v4

Leagues are seeded into the `competitions` table and can be enabled/disabled from the database.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LeagueDef:
    code: str
    name: str
    country: str
    tier: int
    api_football: int | None
    football_data: str | None
    the_odds_api: str | None
    reliability: float = 0.8  # prior data/model reliability used by the confidence engine
    summer_season: bool = False  # calendar-year leagues


LEAGUES: list[LeagueDef] = [
    LeagueDef("ENG_PL", "Premier League", "England", 1, 39, "PL", "soccer_epl", 0.95),
    LeagueDef("ENG_CH", "Championship", "England", 2, 40, "ELC", "soccer_efl_champ", 0.9),
    LeagueDef("ENG_L1", "League One", "England", 3, 41, None, "soccer_england_league1", 0.8),
    LeagueDef("ENG_L2", "League Two", "England", 4, 42, None, "soccer_england_league2", 0.75),
    LeagueDef("SCO_PR", "Scottish Premiership", "Scotland", 1, 179, None, "soccer_spl", 0.8),
    LeagueDef("ESP_L1", "La Liga", "Spain", 1, 140, "PD", "soccer_spain_la_liga", 0.95),
    LeagueDef("ESP_L2", "Segunda Division", "Spain", 2, 141, None, "soccer_spain_segunda_division", 0.8),
    LeagueDef("GER_BL", "Bundesliga", "Germany", 1, 78, "BL1", "soccer_germany_bundesliga", 0.95),
    LeagueDef("GER_B2", "2. Bundesliga", "Germany", 2, 79, None, "soccer_germany_bundesliga2", 0.85),
    LeagueDef("ITA_SA", "Serie A", "Italy", 1, 135, "SA", "soccer_italy_serie_a", 0.95),
    LeagueDef("ITA_SB", "Serie B", "Italy", 2, 136, None, "soccer_italy_serie_b", 0.8),
    LeagueDef("FRA_L1", "Ligue 1", "France", 1, 61, "FL1", "soccer_france_ligue_one", 0.95),
    LeagueDef("FRA_L2", "Ligue 2", "France", 2, 62, None, "soccer_france_ligue_two", 0.8),
    LeagueDef("NED_ER", "Eredivisie", "Netherlands", 1, 88, "DED", "soccer_netherlands_eredivisie", 0.9),
    LeagueDef("POR_PL", "Primeira Liga", "Portugal", 1, 94, "PPL", "soccer_portugal_primeira_liga", 0.85),
    LeagueDef("BEL_PL", "Belgian Pro League", "Belgium", 1, 144, None, "soccer_belgium_first_div", 0.85),
    LeagueDef("TUR_SL", "Super Lig", "Turkey", 1, 203, None, "soccer_turkey_super_league", 0.8),
    LeagueDef("GRE_SL", "Super League", "Greece", 1, 197, None, "soccer_greece_super_league", 0.75),
    LeagueDef("AUT_BL", "Austrian Bundesliga", "Austria", 1, 218, None, "soccer_austria_bundesliga", 0.8),
    LeagueDef("SUI_SL", "Swiss Super League", "Switzerland", 1, 207, None, "soccer_switzerland_superleague", 0.8),
    LeagueDef("DEN_SL", "Superliga", "Denmark", 1, 119, None, "soccer_denmark_superliga", 0.8),
    LeagueDef("NOR_EL", "Eliteserien", "Norway", 1, 103, None, "soccer_norway_eliteserien", 0.8, True),
    LeagueDef("SWE_AS", "Allsvenskan", "Sweden", 1, 113, None, "soccer_sweden_allsvenskan", 0.8, True),
    LeagueDef("USA_MLS", "MLS", "USA", 1, 253, None, "soccer_usa_mls", 0.75, True),
]

LEAGUE_BY_CODE = {lg.code: lg for lg in LEAGUES}


def league_by_provider_id(provider: str, value) -> LeagueDef | None:
    for lg in LEAGUES:
        if getattr(lg, provider, None) == value:
            return lg
    return None
