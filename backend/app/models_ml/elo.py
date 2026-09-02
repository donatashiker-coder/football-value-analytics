"""Elo-style team rating system with goal-difference scaling and home advantage."""
from __future__ import annotations

from dataclasses import dataclass

MODEL_VERSION = "elo-1.0"


@dataclass
class EloParams:
    k: float = 20.0
    home_advantage: float = 60.0  # rating points added to home team when computing expectation
    initial: float = 1500.0
    promoted_penalty: float = 80.0  # applied to teams entering from a lower division (documented assumption)
    season_regression: float = 0.2  # regress towards mean between seasons (avoids stale ratings)


def expected_score(rating_a: float, rating_b: float) -> float:
    return 1.0 / (1.0 + 10 ** ((rating_b - rating_a) / 400.0))


def goal_difference_multiplier(goal_diff: int) -> float:
    """Margin-of-victory scaling (FiveThirtyEight-style, log form)."""
    gd = abs(goal_diff)
    if gd <= 1:
        return 1.0
    if gd == 2:
        return 1.5
    return 1.75 + (gd - 3) / 8.0


def update(home: float, away: float, home_goals: int, away_goals: int, params: EloParams | None = None) -> tuple[float, float]:
    params = params or EloParams()
    exp_home = expected_score(home + params.home_advantage, away)
    actual = 1.0 if home_goals > away_goals else 0.5 if home_goals == away_goals else 0.0
    delta = params.k * goal_difference_multiplier(home_goals - away_goals) * (actual - exp_home)
    return home + delta, away - delta


def regress_to_mean(rating: float, params: EloParams) -> float:
    return rating + (params.initial - rating) * params.season_regression


def win_probabilities(home: float, away: float, params: EloParams | None = None, draw_rate: float = 0.26) -> dict[str, float]:
    """Approximate 1X2 probabilities from Elo: split the non-draw mass by expected score.

    This is a crude secondary model used for ensemble agreement checks, not the primary probability.
    """
    params = params or EloParams()
    e = expected_score(home + params.home_advantage, away)
    # draw probability is higher when teams are close
    closeness = 1.0 - abs(2 * e - 1)
    p_draw = draw_rate * (0.7 + 0.6 * closeness)
    p_draw = min(max(p_draw, 0.10), 0.40)
    rest = 1.0 - p_draw
    return {"home": rest * e, "draw": p_draw, "away": rest * (1 - e)}
