"""Corner model.

Expected corners for each team are built from opponent-adjusted, shrunk corner rates
(for / against, home / away). The total-corner distribution is modelled either as Poisson
or Negative Binomial; the negative binomial is selected when historical corner counts are
over-dispersed (variance > mean), which is the usual case in football. The backtester can
compare both and record which performs better.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from app.models_ml.distributions import negative_binomial_pmf, poisson_pmf, prob_over, prob_under

MODEL_VERSION = "corners-nb-1.0"
CORNER_LINES = (6.5, 7.5, 8.5, 9.5, 10.5, 11.5, 12.5, 13.5)
TEAM_CORNER_LINES = (2.5, 3.5, 4.5, 5.5, 6.5)


@dataclass
class CornerModelParams:
    distribution: str = "negative_binomial"  # or "poisson"
    dispersion: float = 12.0  # NB dispersion for total corners; larger -> closer to Poisson
    team_dispersion: float = 8.0
    home_corner_advantage: float = 1.0  # league-derived; ratio of home to away corner rates already in averages
    max_count: int = 40
    first_half_share: float = 0.46


@dataclass
class CornerModelInput:
    home_corners_for: float  # shrunk rate per match, home venue (1.0 = league average multiplier)
    home_corners_against: float
    away_corners_for: float
    away_corners_against: float
    league_home_corners: float  # league avg corners taken by home teams per match
    league_away_corners: float
    observed_variance_ratio: float | None = None  # var/mean of league total corners, used to pick dispersion
    extras: dict = field(default_factory=dict)


@dataclass
class CornerModelOutput:
    home_expected: float
    away_expected: float
    total_pmf: np.ndarray
    home_pmf: np.ndarray
    away_pmf: np.ndarray
    probabilities: dict[str, float]
    distribution: str
    dispersion: float
    model_version: str = MODEL_VERSION

    @property
    def total_expected(self) -> float:
        return self.home_expected + self.away_expected


def dispersion_from_variance_ratio(ratio: float | None, default: float, mean: float) -> float:
    """Convert an observed variance/mean ratio to an NB dispersion (r) parameter.

    var = mean + mean^2 / r  ->  r = mean^2 / (var - mean) = mean / (ratio - 1).
    """
    if ratio is None or ratio <= 1.02:
        return 1e6  # effectively Poisson
    return max(mean / (ratio - 1.0), 0.5) if mean > 0 else default


def expected_corners(inp: CornerModelInput) -> tuple[float, float]:
    """Opponent-adjusted expectation: home_for x away_conceded rate, scaled by league average."""
    home = inp.league_home_corners * inp.home_corners_for * inp.away_corners_against
    away = inp.league_away_corners * inp.away_corners_for * inp.home_corners_against
    return max(home, 0.2), max(away, 0.2)


def _pmf(mean: float, params: CornerModelParams, dispersion: float) -> np.ndarray:
    if params.distribution == "poisson":
        return poisson_pmf(mean, params.max_count)
    return negative_binomial_pmf(mean, dispersion, params.max_count)


def predict(inp: CornerModelInput, params: CornerModelParams | None = None) -> CornerModelOutput:
    params = params or CornerModelParams()
    h, a = expected_corners(inp)
    total = h + a
    dispersion = params.dispersion
    if params.distribution != "poisson" and inp.observed_variance_ratio is not None:
        dispersion = dispersion_from_variance_ratio(inp.observed_variance_ratio, params.dispersion, total)
    total_pmf = _pmf(total, params, dispersion)
    home_pmf = _pmf(h, params, params.team_dispersion)
    away_pmf = _pmf(a, params, params.team_dispersion)

    probs: dict[str, float] = {}
    for line in CORNER_LINES:
        probs[f"corners_over_{line}"] = prob_over(total_pmf, line)
        probs[f"corners_under_{line}"] = prob_under(total_pmf, line)
    for line in TEAM_CORNER_LINES:
        probs[f"home_corners_over_{line}"] = prob_over(home_pmf, line)
        probs[f"home_corners_under_{line}"] = prob_under(home_pmf, line)
        probs[f"away_corners_over_{line}"] = prob_over(away_pmf, line)
        probs[f"away_corners_under_{line}"] = prob_under(away_pmf, line)
    # first-half corners: scaled expectation, same distribution family
    fh_pmf = _pmf(total * params.first_half_share, params, dispersion * params.first_half_share)
    for line in (3.5, 4.5, 5.5, 6.5):
        probs[f"1h_corners_over_{line}"] = prob_over(fh_pmf, line)
        probs[f"1h_corners_under_{line}"] = prob_under(fh_pmf, line)
    return CornerModelOutput(
        home_expected=h,
        away_expected=a,
        total_pmf=total_pmf,
        home_pmf=home_pmf,
        away_pmf=away_pmf,
        probabilities=probs,
        distribution=params.distribution if dispersion < 1e6 else "poisson",
        dispersion=dispersion,
    )


def compare_distributions(observed_totals: np.ndarray, expected_totals: np.ndarray, dispersion: float) -> dict[str, float]:
    """Log-likelihood of observed corner totals under Poisson vs NB with given expectations.

    Used by the backtester to select the distribution. Higher (less negative) is better.
    """
    from scipy import stats

    obs = observed_totals.astype(int)
    exp = np.clip(expected_totals, 0.1, None)
    ll_pois = float(np.sum(stats.poisson.logpmf(obs, exp)))
    n = dispersion
    p = n / (n + exp)
    ll_nb = float(np.sum(stats.nbinom.logpmf(obs, n, p)))
    return {"poisson_loglik": ll_pois, "negative_binomial_loglik": ll_nb, "preferred": "negative_binomial" if ll_nb > ll_pois else "poisson"}
