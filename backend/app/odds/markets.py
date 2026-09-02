"""Market registry. Adding a market means adding one MarketDef here (plus provider mapping if priced).

market_key convention: <group>_<selection>_<line>; the probability key maps into the goal / corner
model output dictionaries so the value engine is generic across market groups.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MarketDef:
    key: str
    group: str  # match_result | goals | btts | team_goals | corners | team_corners | first_half | handicap
    name: str
    selection: str
    line: float | None
    prob_key: str  # key in the model probability dict
    outcome_set: str  # id of the complete outcome set used for overround removal
    period: str = "FT"
    strategy: str = "VALUE_ONLY"  # default strategy family


def _ou(group: str, prefix: str, lines: tuple[float, ...], prob_prefix: str, name: str, strategy_over: str, strategy_under: str, period: str = "FT") -> list[MarketDef]:
    out: list[MarketDef] = []
    for line in lines:
        oset = f"{prefix}_{line}"
        out.append(MarketDef(f"{prefix}_over_{line}", group, f"{name} Over {line}", "over", line, f"{prob_prefix}over_{line}", oset, period, strategy_over))
        out.append(MarketDef(f"{prefix}_under_{line}", group, f"{name} Under {line}", "under", line, f"{prob_prefix}under_{line}", oset, period, strategy_under))
    return out


MARKETS: list[MarketDef] = [
    MarketDef("match_home", "match_result", "Home Win", "home", None, "home", "1x2", strategy="MATCH_RESULT"),
    MarketDef("match_draw", "match_result", "Draw", "draw", None, "draw", "1x2", strategy="MATCH_RESULT"),
    MarketDef("match_away", "match_result", "Away Win", "away", None, "away", "1x2", strategy="MATCH_RESULT"),
    MarketDef("dc_home_draw", "match_result", "Double Chance 1X", "home_draw", None, "dc_home_draw", "dc", strategy="MATCH_RESULT"),
    MarketDef("dc_home_away", "match_result", "Double Chance 12", "home_away", None, "dc_home_away", "dc", strategy="MATCH_RESULT"),
    MarketDef("dc_draw_away", "match_result", "Double Chance X2", "draw_away", None, "dc_draw_away", "dc", strategy="MATCH_RESULT"),
    MarketDef("dnb_home", "match_result", "Draw No Bet Home", "home", None, "dnb_home", "dnb", strategy="MATCH_RESULT"),
    MarketDef("dnb_away", "match_result", "Draw No Bet Away", "away", None, "dnb_away", "dnb", strategy="MATCH_RESULT"),
    MarketDef("btts_yes", "btts", "Both Teams To Score Yes", "yes", None, "btts_yes", "btts", strategy="BTTS"),
    MarketDef("btts_no", "btts", "Both Teams To Score No", "no", None, "btts_no", "btts", strategy="BTTS"),
    *_ou("goals", "goals", (0.5, 1.5, 2.5, 3.5, 4.5), "", "Total Goals", "GOALS_OVER", "GOALS_UNDER"),
    *_ou("team_goals", "home_goals", (0.5, 1.5, 2.5), "home_", "Home Team Goals", "TEAM_GOALS", "TEAM_GOALS"),
    *_ou("team_goals", "away_goals", (0.5, 1.5, 2.5), "away_", "Away Team Goals", "TEAM_GOALS", "TEAM_GOALS"),
    *_ou("corners", "corners", (7.5, 8.5, 9.5, 10.5, 11.5, 12.5), "corners_", "Total Corners", "CORNERS_OVER", "CORNERS_UNDER"),
    *_ou("team_corners", "home_corners", (3.5, 4.5, 5.5, 6.5), "home_corners_", "Home Team Corners", "CORNERS_OVER", "CORNERS_UNDER"),
    *_ou("team_corners", "away_corners", (2.5, 3.5, 4.5, 5.5), "away_corners_", "Away Team Corners", "CORNERS_OVER", "CORNERS_UNDER"),
    *_ou("first_half", "1h_goals", (0.5, 1.5), "1h_", "First Half Goals", "FIRST_HALF", "FIRST_HALF", period="1H"),
    MarketDef("1h_btts_yes", "first_half", "First Half BTTS Yes", "yes", None, "1h_btts_yes", "1h_btts", "1H", "FIRST_HALF"),
    *_ou("first_half", "1h_corners", (3.5, 4.5, 5.5), "1h_corners_", "First Half Corners", "FIRST_HALF", "FIRST_HALF", period="1H"),
]
for _h in (-1.5, -1.0, -0.5, 0.0, 0.5, 1.0, 1.5):
    MARKETS.append(MarketDef(f"ah_home_{_h:+.1f}", "handicap", f"Asian Handicap Home {_h:+.1f}", "home", _h, f"ah_home_{_h:+.1f}", f"ah_{_h:+.1f}", strategy="MATCH_RESULT"))
    MARKETS.append(MarketDef(f"ah_away_{-_h:+.1f}", "handicap", f"Asian Handicap Away {-_h:+.1f}", "away", -_h, f"ah_away_{-_h:+.1f}", f"ah_{_h:+.1f}", strategy="MATCH_RESULT"))

MARKET_BY_KEY: dict[str, MarketDef] = {m.key: m for m in MARKETS}


def outcome_set_members(outcome_set: str) -> list[MarketDef]:
    return [m for m in MARKETS if m.outcome_set == outcome_set]


def markets_for_group(group: str) -> list[MarketDef]:
    return [m for m in MARKETS if m.group == group]


STRATEGIES = [
    "GOALS_OVER",
    "GOALS_UNDER",
    "BTTS",
    "CORNERS_OVER",
    "CORNERS_UNDER",
    "MATCH_RESULT",
    "TEAM_GOALS",
    "FIRST_HALF",
    "VALUE_ONLY",
]


def markets_for_strategy(strategy: str) -> list[MarketDef]:
    if strategy == "VALUE_ONLY":
        return list(MARKETS)
    return [m for m in MARKETS if m.strategy == strategy]
