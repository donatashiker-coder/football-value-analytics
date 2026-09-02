from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.backtesting.engine import BacktestParams, corner_threshold_analysis, run_backtest
from app.betting.staking import StakeConfig
from app.models import Backtest
from app.odds.markets import STRATEGIES
from app.schemas import BacktestRequest
from app.services.settings_service import corner_params, form_weights, goal_params

router = APIRouter(prefix="/backtests", tags=["backtests"])


def _row(b: Backtest, full: bool = False) -> dict:
    d = {"id": b.id, "strategy": b.strategy, "name": b.name, "status": b.status, "parameters": b.parameters, "summary": b.summary, "created_at": b.created_at.isoformat(), "model_version": b.model_version, "is_demo": b.is_demo}
    if full:
        d.update({"breakdowns": b.breakdowns, "equity_curve": b.equity_curve, "bets": b.bets[-500:]})
    return d


@router.get("")
def list_backtests(strategy: str | None = None, limit: int = Query(50, le=200), db: Session = Depends(get_db)):
    q = select(Backtest).order_by(Backtest.created_at.desc()).limit(limit)
    if strategy:
        q = q.where(Backtest.strategy == strategy)
    return {"strategies": STRATEGIES, "backtests": [_row(b) for b in db.scalars(q)]}


@router.get("/comparison")
def comparison(db: Session = Depends(get_db)):
    """Latest completed backtest per strategy. Numbers come from actual backtests, never hard-coded."""
    seen: dict[str, dict] = {}
    for b in db.scalars(select(Backtest).where(Backtest.status == "completed").order_by(Backtest.created_at.desc())):
        if b.strategy not in seen:
            s = b.summary
            seen[b.strategy] = {"strategy": b.strategy, "backtest_id": b.id, "bets": s.get("bets", 0), "strike_rate": s.get("strike_rate"), "roi": s.get("roi"), "clv": s.get("average_clv"), "max_drawdown": s.get("max_drawdown"), "average_odds": s.get("average_odds"), "created_at": b.created_at.isoformat(), "is_demo": b.is_demo}
    return list(seen.values())


@router.get("/{backtest_id}")
def get_backtest(backtest_id: str, db: Session = Depends(get_db)):
    b = db.get(Backtest, backtest_id)
    if b is None:
        raise HTTPException(404, "backtest not found")
    return _row(b, full=True)


@router.post("/run")
def run(body: BacktestRequest, db: Session = Depends(get_db)):
    if body.strategy not in STRATEGIES:
        raise HTTPException(400, f"unknown strategy; choose from {STRATEGIES}")
    params = BacktestParams(
        strategy=body.strategy, competition_codes=body.competition_codes, start=body.start, end=body.end, min_ev=body.min_ev, min_confidence=body.min_confidence, min_data_quality=body.min_data_quality,
        min_odds=body.min_odds, max_odds=body.max_odds, min_sample_size=body.min_sample_size, stake=StakeConfig(method=body.stake_method, flat_stake=body.flat_stake), starting_bankroll=body.starting_bankroll,
        corner_distribution=body.corner_distribution, min_expected_corners=body.min_expected_corners, min_expected_goals=body.min_expected_goals, exclude_early_red_cards=body.exclude_early_red_cards, one_bet_per_fixture=body.one_bet_per_fixture,
    )
    bt = run_backtest(db, params, goal_params(db), corner_params(db), form_weights(db))
    return _row(bt, full=True)


@router.post("/corner-thresholds")
def corner_thresholds(competition_codes: list[str] | None = None, db: Session = Depends(get_db)):
    return corner_threshold_analysis(db, competition_codes=competition_codes)
