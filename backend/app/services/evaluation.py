"""Model evaluation: settle stored predictions against results, compute calibration metrics,
model leaderboard, drift detection and per-strategy historical performance scores."""
from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime, timedelta

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.betting.settlement import ResultData, outcome_to_binary, settle_market
from app.models import Backtest, Fixture, ModelPrediction, Odds, Result
from app.models_ml.calibration import detect_drift, evaluate
from app.odds.markets import MARKET_BY_KEY
from app.odds.math import closing_line_value


def utcnow() -> datetime:
    return datetime.now(UTC)


def settle_predictions(db: Session, limit: int = 20000) -> dict:
    """Mark predictions won/lost once results exist; attach closing odds + CLV where available."""
    q = select(ModelPrediction, Result).join(Result, Result.fixture_id == ModelPrediction.fixture_id).where(ModelPrediction.settled.is_(False)).limit(limit)
    settled = 0
    closing_cache: dict[tuple[str, str, str], float | None] = {}
    for pred, res in db.execute(q).all():
        outcome = settle_market(pred.market_key, ResultData(res.home_goals, res.away_goals, res.home_goals_ht, res.away_goals_ht, res.home_corners, res.away_corners, res.home_corners_ht, res.away_corners_ht))
        if outcome == "unsettled":
            continue
        pred.settled = True
        pred.outcome = outcome_to_binary(outcome)
        key = (pred.fixture_id, pred.market_key, pred.selection)
        if key not in closing_cache:
            rows = list(db.scalars(select(Odds).where(Odds.fixture_id == pred.fixture_id, Odds.market_key == pred.market_key, Odds.selection == pred.selection).order_by(Odds.recorded_at.desc())))
            closing = [r.decimal_odds for r in rows if r.is_closing] or [r.decimal_odds for r in rows if r.is_current]
            closing_cache[key] = float(np.median(closing)) if closing else None
        pred.closing_odds = closing_cache[key]
        if pred.closing_odds and pred.best_odds_at_prediction:
            pred.clv = closing_line_value(pred.best_odds_at_prediction, pred.closing_odds)
        settled += 1
    db.commit()
    return {"settled": settled}


def model_performance(db: Session, days: int | None = 30, model_name: str | None = None, market_group: str | None = None) -> dict:
    q = select(ModelPrediction).where(ModelPrediction.settled.is_(True), ModelPrediction.outcome.is_not(None))
    if days:
        q = q.where(ModelPrediction.prediction_timestamp >= utcnow() - timedelta(days=days))
    if model_name:
        q = q.where(ModelPrediction.model_name == model_name)
    preds = list(db.scalars(q))
    if market_group:
        preds = [p for p in preds if MARKET_BY_KEY.get(p.market_key) and MARKET_BY_KEY[p.market_key].group == market_group]
    probs = np.array([p.probability for p in preds])
    outs = np.array([p.outcome for p in preds])
    rep = evaluate(probs, outs).as_dict() if len(preds) else {"n": 0}
    clvs = [p.clv for p in preds if p.clv is not None]
    # paper ROI if every primary signal had been backed at best odds (flat 1 unit)
    backed = [p for p in preds if p.best_odds_at_prediction]
    pl = sum((p.best_odds_at_prediction - 1) if p.outcome == 1 else -1 for p in backed)
    rep.update({"average_clv": float(np.mean(clvs)) if clvs else None, "signals_backed": len(backed), "flat_roi_all_signals": (pl / len(backed)) if backed else None, "period_days": days, "model_name": model_name, "market_group": market_group})
    return rep


def model_leaderboard(db: Session) -> list[dict]:
    preds = list(db.scalars(select(ModelPrediction).where(ModelPrediction.settled.is_(True), ModelPrediction.outcome.is_not(None))))
    groups: dict[tuple[str, str, str], list[ModelPrediction]] = defaultdict(list)
    for p in preds:
        m = MARKET_BY_KEY.get(p.market_key)
        groups[(p.model_name, p.model_version, m.group if m else "unknown")].append(p)
    rows = []
    for (name, version, group), ps in groups.items():
        probs, outs = np.array([p.probability for p in ps]), np.array([p.outcome for p in ps])
        rep = evaluate(probs, outs)
        clvs = [p.clv for p in ps if p.clv is not None]
        backed = [p for p in ps if p.best_odds_at_prediction]
        pl = sum((p.best_odds_at_prediction - 1) if p.outcome == 1 else -1 for p in backed)
        ts = [p.prediction_timestamp for p in ps]
        rows.append({"model": name, "version": version, "market_group": group, "predictions": rep.n, "brier": rep.brier, "log_loss": rep.log_loss, "ece": rep.expected_calibration_error, "roc_auc": rep.roc_auc, "roi": (pl / len(backed)) if backed else None, "clv": float(np.mean(clvs)) if clvs else None, "from": min(ts).isoformat(), "to": max(ts).isoformat()})
    rows.sort(key=lambda r: (r["market_group"], r["brier"] if r["brier"] is not None else 9))
    return rows


def drift_report(db: Session, model_name: str = "dixon_coles", recent_days: int = 30) -> dict:
    recent = model_performance(db, recent_days, model_name)
    historical = model_performance(db, None, model_name)
    return detect_drift(recent.get("brier"), historical.get("brier"), recent.get("n", 0))


def strategy_performance_scores(db: Session) -> dict[str, float]:
    """0..1 score per strategy from the most recent completed backtest (0.5 = no evidence).

    Mapped from ROI: -10% -> 0.2, 0% -> 0.5, +10% -> 0.8, requiring at least 200 bets to count fully.
    """
    scores: dict[str, float] = {}
    for bt in db.scalars(select(Backtest).where(Backtest.status == "completed").order_by(Backtest.created_at.desc())):
        if bt.strategy in scores:
            continue
        s = bt.summary or {}
        n, roi = s.get("bets", 0), s.get("roi")
        if roi is None or n == 0:
            continue
        raw = 0.5 + max(min(roi, 0.10), -0.10) * 3
        weight = min(n / 200, 1.0)
        scores[bt.strategy] = round(0.5 + (raw - 0.5) * weight, 3)
    return scores


def calibration_curve(db: Session, model_name: str | None = None, market_group: str | None = None, days: int | None = None) -> dict:
    return model_performance(db, days, model_name, market_group)


def fixtures_awaiting_results(db: Session) -> int:
    return db.scalar(select(Fixture.id).where(Fixture.status == "SCHEDULED", Fixture.kickoff_utc < utcnow() - timedelta(hours=3)).limit(1)) is not None
