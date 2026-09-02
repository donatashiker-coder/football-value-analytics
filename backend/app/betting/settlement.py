"""Settle a market selection against a final result. Returns won | lost | push | half_won | half_lost | void.

Only markets whose rules are known are settled; anything else returns "unsettled".
"""
from __future__ import annotations

from dataclasses import dataclass

from app.odds.markets import MARKET_BY_KEY


@dataclass
class ResultData:
    home_goals: int
    away_goals: int
    home_goals_ht: int | None = None
    away_goals_ht: int | None = None
    home_corners: int | None = None
    away_corners: int | None = None
    home_corners_ht: int | None = None
    away_corners_ht: int | None = None


def _ou(value: int | None, line: float, selection: str) -> str:
    if value is None:
        return "unsettled"
    if value > line:
        return "won" if selection == "over" else "lost"
    if value < line:
        return "lost" if selection == "over" else "won"
    return "push"


def _ah(diff: int, hcap: float, from_home: bool) -> str:
    # quarter lines (e.g. -0.75) are split bets: not in the registry, so only whole/half handled.
    adj = diff + hcap if from_home else -diff + hcap
    if adj > 0:
        return "won"
    if adj < 0:
        return "lost"
    return "push"


def settle_market(market_key: str, r: ResultData) -> str:
    m = MARKET_BY_KEY.get(market_key)
    if m is None:
        return "unsettled"
    hg, ag = r.home_goals, r.away_goals
    total = hg + ag
    sel, line = m.selection, m.line
    if m.group == "match_result":
        out = "H" if hg > ag else "A" if ag > hg else "D"
        if market_key.startswith("match_"):
            return "won" if {"home": "H", "draw": "D", "away": "A"}[sel] == out else "lost"
        if market_key.startswith("dc_"):
            allowed = {"home_draw": "HD", "home_away": "HA", "draw_away": "DA"}[sel]
            return "won" if out in allowed else "lost"
        if market_key.startswith("dnb_"):
            if out == "D":
                return "push"
            return "won" if (sel == "home") == (out == "H") else "lost"
    if m.group == "handicap":
        return _ah(hg - ag, line, from_home=(sel == "home"))
    if m.group == "btts":
        both = hg > 0 and ag > 0
        return "won" if (sel == "yes") == both else "lost"
    if m.group == "goals":
        return _ou(total, line, sel)
    if m.group == "team_goals":
        return _ou(hg if market_key.startswith("home_") else ag, line, sel)
    if m.group == "corners":
        if r.home_corners is None or r.away_corners is None:
            return "unsettled"
        return _ou(r.home_corners + r.away_corners, line, sel)
    if m.group == "team_corners":
        v = r.home_corners if market_key.startswith("home_") else r.away_corners
        return _ou(v, line, sel)
    if m.group == "first_half":
        if market_key.startswith("1h_goals"):
            if r.home_goals_ht is None or r.away_goals_ht is None:
                return "unsettled"
            return _ou(r.home_goals_ht + r.away_goals_ht, line, sel)
        if market_key == "1h_btts_yes":
            if r.home_goals_ht is None or r.away_goals_ht is None:
                return "unsettled"
            return "won" if r.home_goals_ht > 0 and r.away_goals_ht > 0 else "lost"
        if market_key.startswith("1h_corners"):
            if r.home_corners_ht is None or r.away_corners_ht is None:
                return "unsettled"
            return _ou(r.home_corners_ht + r.away_corners_ht, line, sel)
    return "unsettled"


def outcome_to_binary(outcome: str) -> int | None:
    """1 for won, 0 for lost, None for push/void/unsettled (excluded from calibration)."""
    if outcome == "won":
        return 1
    if outcome == "lost":
        return 0
    return None
