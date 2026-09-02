"""Goal model: Poisson with optional Dixon-Coles adjustment.

Inputs are team attack/defence strengths (already shrunk towards league average by the
statistics engine) plus the league scoring averages. Outputs are expected goals and the
full scoreline matrix, from which every goals/match-result market probability is derived.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from app.models_ml.distributions import matrix_probabilities, most_likely_scores, score_matrix, total_goals_pmf

MODEL_VERSION = "goal-poisson-dc-1.0"


@dataclass
class GoalModelParams:
    rho: float = -0.05  # Dixon-Coles low-score correlation (typical fitted values -0.03 .. -0.13)
    home_advantage: float = 1.0  # multiplicative on home lambda; league-specific value overrides
    use_dixon_coles: bool = True
    max_goals: int = 10
    # optional absence adjustment (fraction of attacking output lost); evidence-based, default none
    home_attack_multiplier: float = 1.0
    away_attack_multiplier: float = 1.0
    home_defence_multiplier: float = 1.0
    away_defence_multiplier: float = 1.0


@dataclass
class GoalModelInput:
    home_attack: float  # home team's home attack strength (1.0 = league average)
    home_defence: float  # home team's home defence strength (1.0 = average; >1 concedes more)
    away_attack: float
    away_defence: float
    league_home_goals: float  # league avg goals scored by home teams per match
    league_away_goals: float
    home_advantage: float | None = None
    extras: dict = field(default_factory=dict)


@dataclass
class GoalModelOutput:
    home_lambda: float
    away_lambda: float
    matrix: np.ndarray
    probabilities: dict[str, float]
    model_version: str = MODEL_VERSION

    @property
    def total_lambda(self) -> float:
        return self.home_lambda + self.away_lambda

    def top_scores(self, n: int = 5) -> list[tuple[int, int, float]]:
        return most_likely_scores(self.matrix, n)

    def total_pmf(self) -> list[float]:
        return [float(x) for x in total_goals_pmf(self.matrix)]


def expected_goals(inp: GoalModelInput, params: GoalModelParams) -> tuple[float, float]:
    """lambda_home = league_home_avg * home_attack * away_defence * home_advantage."""
    ha = inp.home_advantage if inp.home_advantage is not None else params.home_advantage
    home = (
        inp.league_home_goals
        * inp.home_attack
        * params.home_attack_multiplier
        * inp.away_defence
        * params.away_defence_multiplier
        * ha
    )
    away = (
        inp.league_away_goals
        * inp.away_attack
        * params.away_attack_multiplier
        * inp.home_defence
        * params.home_defence_multiplier
    )
    return max(home, 0.05), max(away, 0.05)


def predict(inp: GoalModelInput, params: GoalModelParams | None = None) -> GoalModelOutput:
    params = params or GoalModelParams()
    lh, la = expected_goals(inp, params)
    rho = params.rho if params.use_dixon_coles else 0.0
    m = score_matrix(lh, la, rho=rho, max_goals=params.max_goals)
    return GoalModelOutput(home_lambda=lh, away_lambda=la, matrix=m, probabilities=matrix_probabilities(m))


def predict_from_lambdas(home_lambda: float, away_lambda: float, rho: float = 0.0, max_goals: int = 10) -> GoalModelOutput:
    m = score_matrix(home_lambda, away_lambda, rho=rho, max_goals=max_goals)
    return GoalModelOutput(home_lambda=home_lambda, away_lambda=away_lambda, matrix=m, probabilities=matrix_probabilities(m))


def first_half_probabilities(home_lambda: float, away_lambda: float, first_half_share: float = 0.44) -> dict[str, float]:
    """First-half markets assuming a fixed share of goals arrive before half time.

    `first_half_share` should be estimated from league data (typically 0.42-0.46). Independent Poisson.
    """
    m = score_matrix(home_lambda * first_half_share, away_lambda * first_half_share, rho=0.0, max_goals=8)
    p = matrix_probabilities(m)
    return {
        "1h_over_0.5": p["over_0.5"],
        "1h_over_1.5": p["over_1.5"],
        "1h_under_0.5": p["under_0.5"],
        "1h_under_1.5": p["under_1.5"],
        "1h_btts_yes": p["btts_yes"],
        "1h_home": p["home"],
        "1h_draw": p["draw"],
        "1h_away": p["away"],
    }


def fit_rho(home_goals: np.ndarray, away_goals: np.ndarray, home_lams: np.ndarray, away_lams: np.ndarray) -> float:
    """Maximum-likelihood estimate of the Dixon-Coles rho over historical matches given expected goals.

    Grid search over a bounded range; robust and dependency-free. Returns 0 if data is insufficient.
    """
    if len(home_goals) < 50:
        return 0.0
    from scipy.stats import poisson

    from app.models_ml.distributions import dixon_coles_tau

    base = poisson.logpmf(home_goals, home_lams) + poisson.logpmf(away_goals, away_lams)
    best_rho, best_ll = 0.0, -np.inf
    for rho in np.linspace(-0.2, 0.1, 61):
        tau = np.array(
            [dixon_coles_tau(int(h), int(a), lh, la, rho) for h, a, lh, la in zip(home_goals, away_goals, home_lams, away_lams, strict=True)]
        )
        if np.any(tau <= 0):
            continue
        ll = float(np.sum(base + np.log(tau)))
        if ll > best_ll:
            best_ll, best_rho = ll, float(rho)
    return best_rho
