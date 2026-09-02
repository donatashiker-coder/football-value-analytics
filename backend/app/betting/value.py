"""Value engine: fair odds, edge, EV, value labels, confidence, ranking and the NO-BET filter.

Every threshold and weight is configurable via ValueConfig (persisted in system_settings).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.odds.math import fair_odds as _fair_odds


@dataclass
class ValueConfig:
    # EV thresholds (fractions); label boundaries are inclusive lower bounds
    ev_weak: float = 0.02
    ev_interesting: float = 0.05
    ev_strong: float = 0.08
    ev_very_strong: float = 0.12
    # NO-BET gates
    min_ev: float = 0.03
    min_confidence: float = 45.0
    min_data_quality: float = 50.0
    min_odds: float = 1.30
    max_odds: float = 6.00
    min_sample_size: int = 6
    max_odds_age_hours: float = 12.0
    max_model_disagreement: float = 0.10  # absolute probability spread across models
    min_bookmakers: int = 1
    max_ev_sanity: float = 0.60  # EV above this is treated as suspicious (likely data error)
    # ranking weights (sum to 1)
    w_ev: float = 0.35
    w_confidence: float = 0.20
    w_data_quality: float = 0.15
    w_model_agreement: float = 0.10
    w_strategy_performance: float = 0.10
    w_sample_reliability: float = 0.10
    ev_cap_for_score: float = 0.25  # EV at which the EV component saturates

    def as_dict(self) -> dict:
        return dict(self.__dict__)

    @classmethod
    def from_dict(cls, d: dict | None) -> ValueConfig:
        cfg = cls()
        for k, v in (d or {}).items():
            if hasattr(cfg, k) and v is not None:
                setattr(cfg, k, type(getattr(cfg, k))(v))
        return cfg


def expected_value(probability: float, odds: float) -> float:
    """EV per unit stake: p * O - 1."""
    return probability * odds - 1.0


def edge(model_probability: float, market_probability: float) -> float:
    return model_probability - market_probability


def fair_odds(probability: float) -> float:
    return _fair_odds(probability)


def value_label(ev: float | None, cfg: ValueConfig) -> str:
    if ev is None:
        return "UNAVAILABLE"
    if ev >= cfg.ev_very_strong:
        return "VERY_STRONG"
    if ev >= cfg.ev_strong:
        return "STRONG"
    if ev >= cfg.ev_interesting:
        return "INTERESTING"
    if ev >= cfg.ev_weak:
        return "WEAK"
    return "IGNORE"


@dataclass
class ConfidenceInputs:
    sample_size: int  # matches available for the smaller-sample team
    data_completeness: float  # 0..1
    calibration_score: float | None  # 0..1 (1 = perfectly calibrated historical performance), None unknown
    league_reliability: float  # 0..1
    bookmaker_count: int
    model_agreement: float | None  # 0..1 (1 = models agree), None if single model
    volatility: float  # 0..1 recent performance volatility of the teams (1 = very volatile)
    injury_uncertainty: float  # 0..1
    odds_age_hours: float | None
    historical_strategy_score: float | None  # 0..1 from backtests, None unknown


def confidence_score(inp: ConfidenceInputs) -> tuple[float, dict[str, float]]:
    """Confidence 0..100, independent of EV. Returns (score, component breakdown)."""
    comp: dict[str, float] = {}
    comp["sample"] = min(inp.sample_size / 20.0, 1.0)
    comp["data"] = inp.data_completeness
    comp["calibration"] = inp.calibration_score if inp.calibration_score is not None else 0.5
    comp["league"] = inp.league_reliability
    comp["liquidity"] = min(inp.bookmaker_count / 5.0, 1.0)
    comp["agreement"] = inp.model_agreement if inp.model_agreement is not None else 0.6
    comp["stability"] = 1.0 - inp.volatility
    comp["team_news"] = 1.0 - inp.injury_uncertainty
    if inp.odds_age_hours is None:
        comp["odds_freshness"] = 0.0
    else:
        comp["odds_freshness"] = max(0.0, 1.0 - inp.odds_age_hours / 24.0)
    comp["history"] = inp.historical_strategy_score if inp.historical_strategy_score is not None else 0.5
    weights = {
        "sample": 0.15,
        "data": 0.15,
        "calibration": 0.15,
        "league": 0.10,
        "liquidity": 0.08,
        "agreement": 0.12,
        "stability": 0.07,
        "team_news": 0.08,
        "odds_freshness": 0.05,
        "history": 0.05,
    }
    score = sum(comp[k] * w for k, w in weights.items()) * 100.0
    return round(min(max(score, 0.0), 100.0), 1), comp


def value_score(
    ev: float | None,
    confidence: float,
    data_quality: float,
    model_agreement: float | None,
    strategy_performance: float | None,
    sample_reliability: float,
    cfg: ValueConfig,
) -> float:
    """Composite ranking score 0..100. A high EV from a weak model ranks below a modest EV from a strong one."""
    if ev is None:
        return 0.0
    ev_component = min(max(ev, 0.0) / cfg.ev_cap_for_score, 1.0)
    agreement = model_agreement if model_agreement is not None else 0.6
    strategy = strategy_performance if strategy_performance is not None else 0.5
    score = (
        cfg.w_ev * ev_component
        + cfg.w_confidence * confidence / 100.0
        + cfg.w_data_quality * data_quality / 100.0
        + cfg.w_model_agreement * agreement
        + cfg.w_strategy_performance * strategy
        + cfg.w_sample_reliability * sample_reliability
    )
    return round(score * 100.0, 1)


@dataclass
class NoBetCheck:
    ev: float | None
    confidence: float
    data_quality: float
    odds: float | None
    sample_size: int
    odds_age_hours: float | None
    model_disagreement: float | None
    bookmaker_count: int
    injury_uncertainty: float = 0.0
    extra_reasons: list[str] = field(default_factory=list)


def no_bet_reasons(chk: NoBetCheck, cfg: ValueConfig) -> list[str]:
    reasons: list[str] = list(chk.extra_reasons)
    if chk.odds is None:
        reasons.append("Odds unavailable")
        return reasons
    if chk.ev is None:
        reasons.append("Market probability unavailable")
    elif chk.ev < cfg.min_ev:
        reasons.append(f"Edge too small (EV {chk.ev * 100:+.1f}% < {cfg.min_ev * 100:.1f}%)")
    elif chk.ev > cfg.max_ev_sanity:
        reasons.append(f"EV implausibly high ({chk.ev * 100:+.0f}%); possible data error")
    if chk.confidence < cfg.min_confidence:
        reasons.append(f"Model confidence too low ({chk.confidence:.0f} < {cfg.min_confidence:.0f})")
    if chk.data_quality < cfg.min_data_quality:
        reasons.append(f"Data quality too low ({chk.data_quality:.0f} < {cfg.min_data_quality:.0f})")
    if chk.odds < cfg.min_odds:
        reasons.append(f"Odds below minimum ({chk.odds:.2f} < {cfg.min_odds:.2f})")
    if chk.odds > cfg.max_odds:
        reasons.append(f"Odds above maximum ({chk.odds:.2f} > {cfg.max_odds:.2f}); high variance")
    if chk.sample_size < cfg.min_sample_size:
        reasons.append(f"Insufficient sample ({chk.sample_size} matches < {cfg.min_sample_size})")
    if chk.odds_age_hours is not None and chk.odds_age_hours > cfg.max_odds_age_hours:
        reasons.append(f"Stale odds ({chk.odds_age_hours:.1f}h old)")
    if chk.model_disagreement is not None and chk.model_disagreement > cfg.max_model_disagreement:
        reasons.append(f"Model disagreement ({chk.model_disagreement * 100:.1f} pts)")
    if chk.bookmaker_count < cfg.min_bookmakers:
        reasons.append("Too few bookmakers pricing this market")
    if chk.injury_uncertainty >= 0.5:
        reasons.append("High team-news uncertainty")
    return reasons
