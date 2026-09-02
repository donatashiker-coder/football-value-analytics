from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models import Bookmaker, Fixture, Odds
from app.odds.markets import MARKET_BY_KEY, MARKETS, outcome_set_members
from app.odds.math import market_probability_for_selection, odds_movement, overround
from app.services.value_engine import load_current_odds
from app.utils.time import age_hours

router = APIRouter(tags=["odds"])


@router.get("/bookmakers")
def bookmakers(db: Session = Depends(get_db)):
    return [{"key": b.key, "name": b.name, "enabled": b.enabled, "is_exchange": b.is_exchange, "rules": b.rules} for b in db.scalars(select(Bookmaker).order_by(Bookmaker.name))]


@router.get("/markets")
def markets():
    return [{"key": m.key, "group": m.group, "name": m.name, "selection": m.selection, "line": m.line, "period": m.period, "strategy": m.strategy} for m in MARKETS]


@router.get("/odds/{fixture_id}")
def fixture_odds(fixture_id: str, db: Session = Depends(get_db)):
    fx = db.get(Fixture, fixture_id)
    if fx is None:
        raise HTTPException(404, "fixture not found")
    comps = load_current_odds(db, fixture_id)
    out = []
    for key, comp in comps.items():
        m = MARKET_BY_KEY.get(key)
        set_comps = {mm.key: comps[mm.key] for mm in outcome_set_members(m.outcome_set) if mm.key in comps} if m else {}
        complete = m is not None and len(set_comps) == len(outcome_set_members(m.outcome_set))
        market_p, raw = market_probability_for_selection(key, set_comps) if complete else (None, 1 / comp.median if comp.median else None)
        d = comp.as_dict()
        d.update({"market_key": key, "market": m.name if m else key, "group": m.group if m else None, "raw_implied": raw, "market_probability": market_p, "overround": overround([c.median for c in set_comps.values()]) if complete else None, "age_hours": age_hours(comp.latest_timestamp), "stale": (age_hours(comp.latest_timestamp) or 0) > 4})
        out.append(d)
    history = list(db.scalars(select(Odds).where(Odds.fixture_id == fixture_id).order_by(Odds.recorded_at)))
    movement: dict[str, list[dict]] = {}
    for o in history:
        movement.setdefault(o.market_key, []).append({"t": o.recorded_at.isoformat(), "bookmaker": o.bookmaker_key, "odds": o.decimal_odds, "closing": o.is_closing})
    summary_movement = {}
    for key, rows in movement.items():
        summary_movement[key] = odds_movement(rows[0]["odds"], rows[-1]["odds"])
    return {"fixture_id": fixture_id, "markets": sorted(out, key=lambda d: (d["group"] or "", d["market_key"])), "history": movement, "movement": summary_movement, "unavailable_markets": [m.key for m in MARKETS if m.key not in comps]}
