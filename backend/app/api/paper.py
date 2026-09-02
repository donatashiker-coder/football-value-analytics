from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.betting.paper import bankroll_state, place_paper_bet, settle_open_bets, snapshot_bankroll
from app.betting.staking import StakeConfig, calculate_stake, kelly_fraction
from app.models import BankrollSnapshot, Bet, Fixture
from app.schemas import PaperBetCreate
from app.services.settings_service import stake_config

router = APIRouter(tags=["paper-betting"])


def _bet(db: Session, b: Bet) -> dict:
    fx = db.get(Fixture, b.fixture_id)
    return {"id": b.id, "fixture_id": b.fixture_id, "home_team": fx.home_team.name if fx else None, "away_team": fx.away_team.name if fx else None, "competition": fx.competition.name if fx else None, "kickoff_utc": fx.kickoff_utc.isoformat() if fx else None, "market_key": b.market_key, "selection": b.selection, "line": b.line, "bookmaker_key": b.bookmaker_key, "odds": b.odds, "stake": b.stake, "stake_method": b.stake_method, "model_probability": b.model_probability, "expected_value": b.expected_value, "placed_at": b.placed_at.isoformat(), "status": b.status, "profit": b.profit, "settled_at": b.settled_at.isoformat() if b.settled_at else None, "closing_odds": b.closing_odds, "clv": b.clv, "is_paper": b.is_paper, "notes": b.notes}


@router.get("/paper-bets")
def list_bets(status: str | None = None, limit: int = Query(200, le=2000), db: Session = Depends(get_db)):
    q = select(Bet).where(Bet.is_paper.is_(True)).order_by(Bet.placed_at.desc()).limit(limit)
    if status:
        q = q.where(Bet.status == status)
    return [_bet(db, b) for b in db.scalars(q)]


@router.post("/paper-bets", status_code=201)
def create_bet(body: PaperBetCreate, db: Session = Depends(get_db)):
    try:
        b = place_paper_bet(db, body.fixture_id, body.market_key, body.selection, body.odds, body.stake, body.bookmaker_key, body.opportunity_id, body.notes, body.stake_method)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return _bet(db, b)


@router.post("/paper-bets/settle")
def settle(db: Session = Depends(get_db)):
    return settle_open_bets(db)


@router.get("/paper-bets/stake-preview")
def stake_preview(probability: float = Query(gt=0, lt=1), odds: float = Query(gt=1), method: str | None = None, db: Session = Depends(get_db)):
    cfg = stake_config(db)
    state = bankroll_state(db)
    out = {}
    for m in ("flat", "percentage", "quarter_kelly", "half_kelly", "full_kelly"):
        out[m] = calculate_stake(probability, odds, state["current_bankroll"], StakeConfig(**{**cfg.__dict__, "method": m}))
    return {"kelly_fraction": kelly_fraction(probability, odds), "stakes": out, "default_method": method or cfg.method, "bankroll": state["current_bankroll"], "max_stake_fraction": cfg.max_stake_fraction}


@router.get("/bankroll")
def bankroll(db: Session = Depends(get_db)):
    state = bankroll_state(db)
    snaps = list(db.scalars(select(BankrollSnapshot).order_by(BankrollSnapshot.as_of.desc()).limit(100)))
    state["snapshots"] = [{"as_of": s.as_of.isoformat(), "bankroll": s.current_bankroll, "profit": s.profit, "roi": s.roi, "max_drawdown": s.max_drawdown} for s in reversed(snaps)]
    state["note"] = "Paper trading only. No real bets are placed by this application."
    return state


@router.post("/bankroll/snapshot")
def snapshot(db: Session = Depends(get_db)):
    s = snapshot_bankroll(db)
    return {"as_of": s.as_of.isoformat(), "bankroll": s.current_bankroll}
