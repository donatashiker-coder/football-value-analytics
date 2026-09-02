import math

import numpy as np
import pytest

from app.models_ml import corner_model, goal_model
from app.models_ml.distributions import (
    dixon_coles_tau,
    matrix_probabilities,
    negative_binomial_pmf,
    poisson_pmf,
    prob_over,
    prob_under,
    score_matrix,
    total_goals_pmf,
)


def test_poisson_pmf_known_values():
    pmf = poisson_pmf(1.0, 10)
    assert pmf[0] == pytest.approx(math.exp(-1), rel=1e-6)
    assert pmf[1] == pytest.approx(math.exp(-1), rel=1e-6)
    assert pmf[2] == pytest.approx(math.exp(-1) / 2, rel=1e-6)
    assert pmf.sum() == pytest.approx(1.0)


def test_negative_binomial_matches_poisson_at_large_dispersion():
    p = poisson_pmf(9.5, 40)
    nb = negative_binomial_pmf(9.5, 1e7, 40)
    assert np.allclose(p, nb, atol=1e-6)


def test_negative_binomial_is_overdispersed():
    mean, r = 10.0, 5.0
    pmf = negative_binomial_pmf(mean, r, 80)
    k = np.arange(81)
    m = float((k * pmf).sum())
    var = float(((k - m) ** 2 * pmf).sum())
    assert m == pytest.approx(mean, rel=1e-3)
    assert var == pytest.approx(mean + mean**2 / r, rel=1e-2)


def test_over_under_complement():
    pmf = poisson_pmf(2.7, 10)
    assert prob_over(pmf, 2.5) + prob_under(pmf, 2.5) == pytest.approx(1.0)
    assert prob_over(pmf, 2.5) == pytest.approx(1 - pmf[0] - pmf[1] - pmf[2])


def test_score_matrix_independent_poisson():
    m = score_matrix(1.5, 1.0, rho=0.0)
    assert m.sum() == pytest.approx(1.0)
    assert m[0, 0] == pytest.approx(math.exp(-1.5) * math.exp(-1.0), rel=1e-4)
    p = matrix_probabilities(m)
    assert p["home"] + p["draw"] + p["away"] == pytest.approx(1.0)
    assert p["over_2.5"] + p["under_2.5"] == pytest.approx(1.0)
    assert p["btts_yes"] + p["btts_no"] == pytest.approx(1.0)
    assert p["dc_home_draw"] == pytest.approx(p["home"] + p["draw"])
    assert p["dnb_home"] == pytest.approx(p["home"] / (p["home"] + p["away"]))
    # total pmf consistent with independent Poisson(2.5)
    total = total_goals_pmf(m)
    assert total[0] == pytest.approx(math.exp(-2.5), rel=1e-3)


def test_dixon_coles_tau_and_adjustment():
    assert dixon_coles_tau(0, 0, 1.2, 1.0, -0.1) == pytest.approx(1 + 0.12)
    assert dixon_coles_tau(1, 1, 1.2, 1.0, -0.1) == pytest.approx(1.1)
    assert dixon_coles_tau(2, 1, 1.2, 1.0, -0.1) == 1.0
    base = score_matrix(1.4, 1.1, rho=0.0)
    dc = score_matrix(1.4, 1.1, rho=-0.08)
    assert dc.sum() == pytest.approx(1.0)
    assert dc[0, 0] > base[0, 0]  # negative rho inflates 0-0 and 1-1
    assert dc[1, 1] > base[1, 1]
    assert dc[1, 0] < base[1, 0]


def test_goal_model_expected_goals_formula():
    inp = goal_model.GoalModelInput(home_attack=1.2, home_defence=0.9, away_attack=0.8, away_defence=1.1, league_home_goals=1.5, league_away_goals=1.2, home_advantage=1.0)
    out = goal_model.predict(inp, goal_model.GoalModelParams(rho=0.0))
    assert out.home_lambda == pytest.approx(1.5 * 1.2 * 1.1)
    assert out.away_lambda == pytest.approx(1.2 * 0.8 * 0.9)
    assert 0 < out.probabilities["over_2.5"] < 1
    assert out.top_scores(1)[0][2] == out.matrix.max()


def test_asian_handicap_push_mass():
    m = score_matrix(1.3, 1.3, 0.0)
    p = matrix_probabilities(m)
    assert p["ah_home_+0.0_push"] == pytest.approx(p["draw"])
    assert p["ah_home_+0.0"] == pytest.approx(p["home"])
    assert p["ah_home_-0.5"] == pytest.approx(p["home"])
    assert p["ah_home_+0.5"] == pytest.approx(p["home"] + p["draw"])


def test_corner_model_expectation_and_probabilities():
    inp = corner_model.CornerModelInput(home_corners_for=1.1, home_corners_against=0.9, away_corners_for=1.0, away_corners_against=1.2, league_home_corners=5.5, league_away_corners=4.5, observed_variance_ratio=1.8)
    out = corner_model.predict(inp)
    assert out.home_expected == pytest.approx(5.5 * 1.1 * 1.2)
    assert out.away_expected == pytest.approx(4.5 * 1.0 * 0.9)
    assert out.probabilities["corners_over_9.5"] + out.probabilities["corners_under_9.5"] == pytest.approx(1.0)
    assert out.probabilities["corners_over_7.5"] > out.probabilities["corners_over_10.5"]
    assert out.distribution == "negative_binomial"
    pois = corner_model.predict(inp, corner_model.CornerModelParams(distribution="poisson"))
    assert pois.distribution == "poisson"
    # NB has fatter tails than Poisson for the same mean
    assert out.probabilities["corners_over_13.5"] > pois.probabilities["corners_over_13.5"]


def test_dispersion_from_variance_ratio():
    assert corner_model.dispersion_from_variance_ratio(None, 12.0, 10.0) == 1e6
    assert corner_model.dispersion_from_variance_ratio(2.0, 12.0, 10.0) == pytest.approx(10.0)


def test_fit_rho_recovers_sign():
    rng = np.random.default_rng(1)
    n = 3000
    lh, la = np.full(n, 1.4), np.full(n, 1.1)
    hg = rng.poisson(lh)
    ag = rng.poisson(la)
    # inject extra 0-0 and 1-1 draws (negative rho signature)
    idx = rng.choice(n, 200, replace=False)
    hg[idx[:100]], ag[idx[:100]] = 0, 0
    hg[idx[100:]], ag[idx[100:]] = 1, 1
    rho = goal_model.fit_rho(hg, ag, lh, la)
    assert rho < 0
