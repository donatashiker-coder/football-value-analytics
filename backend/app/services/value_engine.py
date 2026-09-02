"""Value engine: model probability vs bookmaker market -> edge, EV, confidence, ranking, NO-BET, explanation."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.betting.value import ConfidenceInputs, NoBetCheck, ValueConfig, confidence_score, expected_value, fair_odds, no_bet_reasons, value_label, value_score
from app.models import Fixture, Odds
from app.odds.markets import MARKET_BY_KEY, MarketDef, outcome_set_members
from app.odds.math import BookmakerPrice, MarketComparison, market_probability_for_selection
from app.services.features import FixtureFeatures
from app.services.prediction import FixturePrediction, model_disagreement
from app.utils.time import age_hours


@dataclass
class MarketOdds:
    comparisons: dict[str, MarketComparison]  # selection market_key -> comparison (per outcome set)

    def for_market(self, m: MarketDef) -> MarketComparison | None:
        return self.comparisons.get(m.key)


def load_current_odds(db: Session, fixture_id: str) -> dict[str, MarketComparison]:
    rows = db.scalars(select(Odds).where(Odds.fixture_id == fixture_id, Odds.is_current.is_(True), Odds.status == "open"))
    comps: dict[str, MarketComparison] = {}
    for o in rows:
        comp = comps.setdefault(o.market_key, MarketComparison(o.selection))
        comp.prices.append(BookmakerPrice(o.bookmaker_key, o.decimal_odds, o.recorded_at))
    return comps


def opening_and_closing(db: Session, fixture_id: str, market_key: str) -> tuple[float | None, float | None]:
    """Median opening (earliest snapshot) and latest odds for movement display."""
    rows = list(db.scalars(select(Odds).where(Odds.fixture_id == fixture_id, Odds.market_key == market_key).order_by(Odds.recorded_at)))
    if not rows:
        return None, None
    first_ts = rows[0].recorded_at
    opening = [r.decimal_odds for r in rows if (r.recorded_at - first_ts).total_seconds() < 3600]
    current = [r.decimal_odds for r in rows if r.is_current]
    import statistics

    return (statistics.median(opening) if opening else None), (statistics.median(current) if current else None)


@dataclass
class ValueResult:
    market: MarketDef
    model_probability: float
    market_probability: float | None
    raw_implied: float | None
    best_odds: float | None
    best_bookmaker: str | None
    median_odds: float | None
    bookmaker_count: int
    fair_odds: float
    edge: float | None
    ev: float | None
    label: str
    confidence: float
    confidence_components: dict
    data_quality: float
    score: float
    status: str
    no_bet_reasons: list[str]
    key_factors: list[str]
    risk_factors: list[str]
    explanation: str
    odds_recorded_at: datetime | None
    model_agreement: float | None


def _pct(x: float | None) -> str:
    return "n/a" if x is None else f"{x * 100:.1f}%"


def explain(m: MarketDef, ff: FixtureFeatures, pred: FixturePrediction, model_p: float, market_p: float | None, best: float | None, ev: float | None, agreement: float | None) -> tuple[list[str], list[str], str]:
    """Build key factors / risks strictly from stored features. Never invents anything."""
    f = ff.features
    hs, as_ = f["home_stats"], f["away_stats"]
    lg = f["league"]
    key: list[str] = []
    risk: list[str] = []
    total = pred.home_lambda + pred.away_lambda
    if m.group in ("goals", "btts", "team_goals", "first_half") and not m.key.startswith("1h_corners"):
        key.append(f"Model expected goals {pred.home_lambda:.2f} + {pred.away_lambda:.2f} = {total:.2f} (league average {lg['home_goals'] + lg['away_goals']:.2f})")
        if hs.get("xg_for_avg") is not None and as_.get("xg_for_avg") is not None:
            key.append(f"Season xG per match: home {hs['xg_for_avg']:.2f} for / {hs['xg_against_avg']:.2f} against; away {as_['xg_for_avg']:.2f} for / {as_['xg_against_avg']:.2f} against")
        if hs.get("over_2.5_last_5") is not None and as_.get("over_2.5_last_5") is not None:
            key.append(f"Over 2.5 in last 5: home {_pct(hs['over_2.5_last_5'])}, away {_pct(as_['over_2.5_last_5'])}")
        if hs.get("btts_last_10") is not None and m.group == "btts":
            key.append(f"BTTS last 10: home {_pct(hs['btts_last_10'])}, away {_pct(as_['btts_last_10'])}")
        if m.selection == "under" or m.key == "btts_no":
            if hs.get("clean_sheet_pct") is not None:
                key.append(f"Clean sheets: home {_pct(hs['clean_sheet_pct'])}, away {_pct(as_['clean_sheet_pct'])}")
    elif m.group in ("corners", "team_corners") or m.key.startswith("1h_corners"):
        if pred.home_corners is not None:
            lt = (lg.get("home_corners") or 0) + (lg.get("away_corners") or 0)
            key.append(f"Expected corners {pred.home_corners:.1f} + {pred.away_corners:.1f} = {pred.home_corners + pred.away_corners:.1f} (league average {lt:.1f})")
        if hs.get("home_corners_for_avg") is not None:
            key.append(f"Home side averages {hs['home_corners_for_avg']:.1f} corners for / {hs['home_corners_against_avg']:.1f} against at home")
        if as_.get("away_corners_for_avg") is not None:
            key.append(f"Away side averages {as_['away_corners_for_avg']:.1f} corners for / {as_['away_corners_against_avg']:.1f} against away")
        if hs.get("corners_for_last_5") is not None and as_.get("corners_for_last_5") is not None:
            key.append(f"Recent corners for (last 5): home {hs['corners_for_last_5']:.1f}, away {as_['corners_for_last_5']:.1f}")
        if pred.corner_distribution:
            key.append(f"Corner distribution: {pred.corner_distribution.replace('_', ' ')}")
    else:
        key.append(f"Elo ratings: home {f['home_elo']:.0f} vs away {f['away_elo']:.0f} (diff {f['elo_diff']:+.0f})")
        key.append(f"Points per game: home {hs.get('points_per_game') or 0:.2f}, away {as_.get('points_per_game') or 0:.2f}")
        key.append(f"Model expected goals {pred.home_lambda:.2f} vs {pred.away_lambda:.2f}")
    if agreement is not None:
        key.append("Model agreement is strong" if agreement > 0.8 else "Models broadly agree" if agreement > 0.5 else "Models disagree on this market")
    # risks
    if f["sample_size"] < f.get("min_sample_size", 6):
        risk.append(f"Small current-season sample ({f['sample_size']} matches); estimates shrunk towards league average")
    for side, news in (("Home", f["home_news"]), ("Away", f["away_news"])):
        if not news.get("available"):
            risk.append(f"{side} team news unavailable")
        elif (news.get("injuries_doubtful") or 0) > 0:
            risk.append(f"{side}: {news['injuries_doubtful']} player(s) doubtful")
        elif (news.get("injuries_out") or 0) >= 2:
            risk.append(f"{side}: {news['injuries_out']} player(s) reported out")
    if f["volatility"] > 0.6:
        risk.append("High recent scoring volatility")
    if lg.get("fallback"):
        risk.append("League averages are fallback defaults")
    if m.group in ("corners", "team_corners") and lg.get("corner_coverage", 1) < 0.8:
        risk.append("Incomplete corner data in this league")
    if (hs.get("days_since_last_match") or 7) < 3.5 or (as_.get("days_since_last_match") or 7) < 3.5:
        risk.append("Short rest for at least one team")
    for w in ff.warnings[:3]:
        if w not in risk:
            risk.append(w)
    text = f"Model probability is {model_p * 100:.1f}%"
    if market_p is not None:
        text += f", compared with a normalised market probability of {market_p * 100:.1f}%"
    if best is not None and ev is not None:
        text += f". Best available odds {best:.2f} against fair odds {1 / model_p:.2f} imply an expected value of {ev * 100:+.1f}%"
    else:
        text += ". Odds are unavailable for this market, so no value calculation is possible"
    text += ". " + " ".join(k + "." for k in key[:3])
    if risk:
        text += " Risks: " + "; ".join(risk[:3]) + "."
    return key, risk, text


def evaluate_market(
    m: MarketDef, ff: FixtureFeatures, pred: FixturePrediction, comps: dict[str, MarketComparison], cfg: ValueConfig, now: datetime, strategy_performance: float | None = None, calibration_score: float | None = None
) -> ValueResult:
    p = pred.probabilities[m.prob_key]
    p = min(max(p, 0.001), 0.999)
    f = ff.features
    comp = comps.get(m.key)
    set_comps = {mm.key: comps[mm.key] for mm in outcome_set_members(m.outcome_set) if mm.key in comps}
    best = comp.best if comp and comp.available else None
    best_odds = best.odds if best else None
    market_p, raw = market_probability_for_selection(m.key, set_comps, required_outcomes=len(outcome_set_members(m.outcome_set))) if comp and comp.available else (None, None)
    ev = expected_value(p, best_odds) if best_odds else None
    edge_v = (p - market_p) if market_p is not None else None
    odds_age = age_hours(comp.latest_timestamp) if comp and comp.available else None
    agreement = pred.market_agreement(m)
    disagreement = model_disagreement(pred, m)
    conf, conf_comp = confidence_score(
        ConfidenceInputs(
            sample_size=f["sample_size_with_prior"], data_completeness=ff.data_quality / 100, calibration_score=calibration_score, league_reliability=f["league_reliability"],
            bookmaker_count=comp.count if comp else 0, model_agreement=agreement, volatility=f["volatility"], injury_uncertainty=f["news_uncertainty"], odds_age_hours=odds_age,
            historical_strategy_score=strategy_performance,
        )
    )
    sample_rel = min(f["sample_size_with_prior"] / 20, 1.0)
    reasons = no_bet_reasons(NoBetCheck(ev, conf, ff.data_quality, best_odds, f["sample_size_with_prior"], odds_age, disagreement, comp.count if comp else 0, f["news_uncertainty"]), cfg)
    label = value_label(ev, cfg)
    score = value_score(ev, conf, ff.data_quality, agreement, strategy_performance, sample_rel, cfg) if not reasons else 0.0
    if best_odds is None:
        status = "ODDS_UNAVAILABLE"
    elif reasons:
        status = "NO_BET"
    else:
        status = "VALUE_CANDIDATE"
    key, risk, text = explain(m, ff, pred, p, market_p, best_odds, ev, agreement)
    return ValueResult(
        m, p, market_p, raw, best_odds, best.bookmaker if best else None, comp.median if comp and comp.available else None, comp.count if comp else 0, fair_odds(p), edge_v, ev, label, conf, conf_comp,
        ff.data_quality, score, status, reasons, key, risk, text, comp.latest_timestamp if comp else None, agreement,
    )


def fixture_odds_bookmaker_count(comps: dict[str, MarketComparison]) -> int:
    bks: set[str] = set()
    for c in comps.values():
        bks.update(p.bookmaker for p in c.prices)
    return len(bks)


def utcnow() -> datetime:
    return datetime.now(UTC)


def fixture_display(fx: Fixture) -> dict:
    return {
        "fixture_id": fx.id,
        "home_team": fx.home_team.name,
        "away_team": fx.away_team.name,
        "competition": fx.competition.name,
        "competition_code": fx.competition.code,
        "kickoff_utc": fx.kickoff_utc.isoformat(),
        "status": fx.status,
        "is_demo": fx.is_demo,
    }


def market_def(key: str) -> MarketDef | None:
    return MARKET_BY_KEY.get(key)
