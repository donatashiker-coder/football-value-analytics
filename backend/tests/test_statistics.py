import numpy as np
import pytest

from app.models_ml.calibration import brier_score, calibration_bins, detect_drift, evaluate, log_loss, roc_auc
from app.models_ml.elo import EloParams, expected_score, goal_difference_multiplier, update, win_probabilities
from app.statistics.shrinkage import FormWeights, blend_seasons, shrink, volatility, weighted_form, window_mean


def test_window_mean_and_weighted_form():
    vals = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    assert window_mean(vals, 3) == 9.0
    assert window_mean(vals, None) == 5.5
    assert window_mean([], 5) is None
    wf = weighted_form(vals, FormWeights(last_5=0.5, last_10=0.3, season=0.2))
    assert wf == pytest.approx(0.5 * 8 + 0.3 * 5.5 + 0.2 * 5.5)
    # weights are normalised, so scaling them does not change the result
    assert weighted_form(vals, FormWeights(last_5=5, last_10=3, season=2)) == pytest.approx(wf)


def test_shrinkage_protects_small_samples():
    # 3 matches at 12 corners in a 9.5-corner league, prior strength 10 -> ~10.1
    assert shrink(12.0, 3, 9.5, 10.0) == pytest.approx((3 * 12 + 10 * 9.5) / 13)
    assert shrink(12.0, 100, 9.5, 10.0) > 11.5
    assert shrink(None, 0, 9.5, 10.0) == 9.5


def test_blend_seasons_decays_previous_weight():
    v0, info0 = blend_seasons(None, 0, 2.0, 1.4)
    assert info0["current_weight"] == 0.0 and v0 == pytest.approx(0.7 * 2.0 + 0.3 * 1.4)
    v6, info6 = blend_seasons(1.0, 6, 2.0, 1.4)
    assert info6["current_weight"] == 0.5
    v12, info12 = blend_seasons(1.0, 12, 2.0, 1.4)
    assert info12["current_weight"] == 1.0 and v12 == 1.0
    assert v0 > v6 > v12


def test_volatility_bounds():
    assert volatility([2, 2, 2, 2, 2]) == 0.0
    assert 0 < volatility([0, 5, 0, 6, 1, 7]) <= 1.0
    assert volatility([1]) == 0.5


def test_calibration_metrics():
    probs = np.array([0.9, 0.8, 0.2, 0.1])
    outs = np.array([1, 1, 0, 0])
    assert brier_score(probs, outs) == pytest.approx(np.mean([0.01, 0.04, 0.04, 0.01]))
    assert log_loss(probs, outs) == pytest.approx(-np.mean(np.log([0.9, 0.8, 0.8, 0.9])))
    assert roc_auc(probs, outs) == 1.0
    rep = evaluate(probs, outs, n_bins=5)
    assert rep.n == 4 and rep.expected_calibration_error is not None
    bins = calibration_bins(np.array([0.05, 0.15, 0.95]), np.array([0, 0, 1]), 10)
    assert [b.count for b in bins] == [1, 1, 1]
    assert evaluate([], []).brier is None


def test_drift_detection():
    assert detect_drift(0.25, 0.20, 500)["drift_detected"] is True
    assert detect_drift(0.21, 0.20, 500)["drift_detected"] is False
    assert detect_drift(0.30, 0.20, 10)["drift_detected"] is False


def test_elo():
    assert expected_score(1500, 1500) == 0.5
    assert expected_score(1700, 1500) > 0.75
    h, a = update(1500, 1500, 3, 0, EloParams(k=20, home_advantage=0))
    assert h > 1500 > a and h - 1500 == pytest.approx(1500 - a)
    assert goal_difference_multiplier(1) == 1.0 and goal_difference_multiplier(2) == 1.5 and goal_difference_multiplier(4) > goal_difference_multiplier(3)
    p = win_probabilities(1600, 1500)
    assert sum(p.values()) == pytest.approx(1.0) and p["home"] > p["away"]
