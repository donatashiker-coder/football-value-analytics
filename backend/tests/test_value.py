import pytest

from app.betting.value import ConfidenceInputs, NoBetCheck, ValueConfig, confidence_score, edge, expected_value, fair_odds, no_bet_reasons, value_label, value_score


def test_expected_value_known_examples():
    assert expected_value(0.50, 2.00) == pytest.approx(0.0)
    assert expected_value(0.60, 2.00) == pytest.approx(0.20)
    assert expected_value(0.56, 2.10) == pytest.approx(0.176)
    assert expected_value(0.612, 2.20) == pytest.approx(0.3464, rel=1e-3)


def test_fair_odds_and_edge():
    assert fair_odds(0.5) == 2.0
    assert fair_odds(0.25) == 4.0
    assert edge(0.612, 0.455) == pytest.approx(0.157)


def test_value_labels_configurable():
    cfg = ValueConfig()
    assert value_label(0.01, cfg) == "IGNORE"
    assert value_label(0.03, cfg) == "WEAK"
    assert value_label(0.06, cfg) == "INTERESTING"
    assert value_label(0.10, cfg) == "STRONG"
    assert value_label(0.15, cfg) == "VERY_STRONG"
    assert value_label(None, cfg) == "UNAVAILABLE"
    custom = ValueConfig.from_dict({"ev_very_strong": 0.30})
    assert value_label(0.15, custom) == "STRONG"


def test_confidence_independent_of_ev():
    strong = ConfidenceInputs(30, 0.95, 0.9, 0.95, 6, 0.9, 0.2, 0.0, 1.0, 0.7)
    weak = ConfidenceInputs(3, 0.4, None, 0.6, 1, 0.2, 0.8, 0.6, 20.0, None)
    cs, comps = confidence_score(strong)
    cw, _ = confidence_score(weak)
    assert 0 <= cw < 45 < cs <= 100
    assert set(comps) >= {"sample", "data", "calibration", "odds_freshness"}
    assert confidence_score(ConfidenceInputs(30, 1, 1, 1, 10, 1, 0, 0, 0, 1))[0] == 100.0


def test_ranking_prefers_calibrated_model_over_raw_ev():
    cfg = ValueConfig()
    weak_high_ev = value_score(0.20, confidence=30, data_quality=40, model_agreement=0.3, strategy_performance=0.4, sample_reliability=0.2, cfg=cfg)
    strong_modest_ev = value_score(0.08, confidence=85, data_quality=90, model_agreement=0.9, strategy_performance=0.7, sample_reliability=0.9, cfg=cfg)
    assert strong_modest_ev > weak_high_ev
    assert value_score(None, 90, 90, 1, 1, 1, cfg) == 0.0
    # weights are configurable
    ev_only = ValueConfig.from_dict({"w_ev": 1.0, "w_confidence": 0, "w_data_quality": 0, "w_model_agreement": 0, "w_strategy_performance": 0, "w_sample_reliability": 0})
    assert value_score(0.25, 0, 0, 0, 0, 0, ev_only) == 100.0


def test_no_bet_reasons():
    cfg = ValueConfig()
    ok = NoBetCheck(ev=0.08, confidence=70, data_quality=80, odds=2.1, sample_size=15, odds_age_hours=1, model_disagreement=0.03, bookmaker_count=4)
    assert no_bet_reasons(ok, cfg) == []
    bad = NoBetCheck(ev=0.01, confidence=30, data_quality=40, odds=8.0, sample_size=2, odds_age_hours=30, model_disagreement=0.2, bookmaker_count=0, injury_uncertainty=0.7)
    reasons = no_bet_reasons(bad, cfg)
    joined = " ".join(reasons)
    for expected in ("Edge too small", "confidence too low", "quality too low", "above maximum", "Insufficient sample", "Stale odds", "disagreement", "Too few bookmakers", "team-news"):
        assert expected in joined
    assert no_bet_reasons(NoBetCheck(None, 90, 90, None, 20, None, None, 0), cfg) == ["Odds unavailable"]
    assert "implausibly high" in no_bet_reasons(NoBetCheck(0.9, 90, 90, 2.0, 20, 1, 0.0, 3), cfg)[0]
