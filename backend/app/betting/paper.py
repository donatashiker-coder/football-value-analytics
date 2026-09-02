"""Paper betting and bankroll tracking. No real bets are ever placed."""
from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.betting.settlement import ResultData, settle_market
from app.betting.staking import calculate_stake, settle
from app.models import BankrollSnapshot, Bet, Fixture, Odds, Result, ValueOpportunity
from app.odds.math import closing_line_value
from app.services.settings_service import get_setting, stake_config


def utcnow() -> datetime:
    return datetime.now(UTC)


def bankroll_state(db: Session) -> dict:
    start = float(get_setting(db, "bankroll")["starting_bankroll"])
    bets = list(db.scalars(select(Bet).where(Bet.is_paper.is_(True)).order_by(Bet.placed_at)))
    settled = [b for b in bets if b.status in ("won", "lost", "push", "void")]
    open_bets = [b for b in bets if b.status == "open"]
    profit = sum(b.profit or 0 for b in settled)
    staked = sum(b.stake for b in settled)
    equity, peak, max_dd = start, start, 0.0
    curve = []
    for b in settled:
        equity += b.profit or 0
        peak = max(peak, equity)
        max_dd = max(max_dd, peak - equity)
        curve.append({"t": (b.settled_at or b.placed_at).isoformat(), "equity": round(equity, 2)})
    clvs = [b.clv for b in settled if b.clv is not None]
    return {
        "starting_bankroll": start,
        "current_bankroll": round(start + profit, 2),
        "profit": round(profit, 2),
        "total_staked": round(staked, 2),
        "roi": round(profit / staked, 4) if staked else None,
        "max_drawdown": round(max_dd, 2),
        "open_bets": len(open_bets),
        "open_stake": round(sum(b.stake for b in open_bets), 2),
        "settled_bets": len(settled),
        "wins": sum(1 for b in settled if b.status == "won"),
        "losses": sum(1 for b in settled if b.status == "lost"),
        "pushes": sum(1 for b in settled if b.status in ("push", "void")),
        "strike_rate": round(sum(1 for b in settled if b.status == "won") / max(sum(1 for b in settled if b.status in ("won", "lost")), 1), 4) if settled else None,
        "average_odds": round(sum(b.odds for b in settled) / len(settled), 3) if settled else None,
        "average_clv": round(sum(clvs) / len(clvs), 4) if clvs else None,
        "equity_curve": curve,
    }


def place_paper_bet(db: Session, fixture_id: str, market_key: str, selection: str, odds: float, stake: float | None, bookmaker_key: str | None, opportunity_id: str | None, notes: str | None, stake_method: str | None = None) -> Bet:
    fx = db.get(Fixture, fixture_id)
    if fx is None:
        raise ValueError("fixture not found")
    if fx.status != "SCHEDULED":
        raise ValueError("paper bets can only be recorded on scheduled fixtures")
    if odds <= 1.0:
        raise ValueError("odds must exceed 1.0")
    opp = db.get(ValueOpportunity, opportunity_id) if opportunity_id else None
    cfg = stake_config(db)
    if stake_method:
        cfg.method = stake_method
    state = bankroll_state(db)
    model_p = opp.model_probability if opp else None
    if stake is None:
        stake = calculate_stake(model_p, odds, state["current_bankroll"], cfg)
    if stake <= 0:
        raise ValueError("stake must be positive")
    if stake > state["current_bankroll"] - state["open_stake"]:
        raise ValueError("stake exceeds available paper bankroll")
    bet = Bet(
        fixture_id=fixture_id, opportunity_id=opportunity_id, market_key=market_key, selection=selection, line=opp.line if opp else None, bookmaker_key=bookmaker_key, odds=odds, stake=round(stake, 2),
        stake_method=cfg.method, model_probability=model_p, expected_value=(model_p * odds - 1) if model_p else None, placed_at=utcnow(), status="open", is_paper=True, notes=notes,
    )
    db.add(bet)
    db.commit()
    return bet


def _closing_odds(db: Session, fixture_id: str, market_key: str, selection: str) -> float | None:
    rows = list(db.scalars(select(Odds).where(Odds.fixture_id == fixture_id, Odds.market_key == market_key, Odds.selection == selection, Odds.is_closing.is_(True))))
    if not rows:
        rows = list(db.scalars(select(Odds).where(Odds.fixture_id == fixture_id, Odds.market_key == market_key, Odds.selection == selection, Odds.is_current.is_(True))))
    if not rows:
        return None
    import statistics

    return statistics.median(r.decimal_odds for r in rows)


def settle_open_bets(db: Session) -> dict:
    settled, unsettled = 0, 0
    for bet in db.scalars(select(Bet).where(Bet.status == "open")):
        res = db.scalar(select(Result).where(Result.fixture_id == bet.fixture_id))
        if res is None:
            continue
        outcome = settle_market(bet.market_key, ResultData(res.home_goals, res.away_goals, res.home_goals_ht, res.away_goals_ht, res.home_corners, res.away_corners, res.home_corners_ht, res.away_corners_ht))
        if outcome == "unsettled":
            unsettled += 1
            continue
        bet.status = "push" if outcome in ("push", "void") else "won" if outcome in ("won", "half_won") else "lost"
        bet.profit = settle(bet.stake, bet.odds, outcome)
        bet.settled_at = utcnow()
        closing = _closing_odds(db, bet.fixture_id, bet.market_key, bet.selection)
        if closing:
            bet.closing_odds = closing
            bet.clv = closing_line_value(bet.odds, closing)
        settled += 1
    db.commit()
    if settled:
        snapshot_bankroll(db)
    return {"settled": settled, "awaiting_data": unsettled}


def snapshot_bankroll(db: Session) -> BankrollSnapshot:
    s = bankroll_state(db)
    snap = BankrollSnapshot(as_of=utcnow(), starting_bankroll=s["starting_bankroll"], current_bankroll=s["current_bankroll"], total_staked=s["total_staked"], profit=s["profit"], roi=s["roi"], max_drawdown=s["max_drawdown"], open_bets=s["open_bets"], settled_bets=s["settled_bets"])
    db.add(snap)
    db.commit()
    return snap
