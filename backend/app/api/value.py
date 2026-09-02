from __future__ import annotations

import csv
import io
from datetime import UTC, date, datetime, timedelta

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models import Competition, Fixture, ValueOpportunity
from app.reporting.daily import _opp_dict
from app.utils.time import local_day_bounds_utc

router = APIRouter(tags=["value"])


def _query(db: Session, day: date | None, days: int, min_ev: float | None, min_confidence: float | None, min_quality: float | None, competition: str | None, market_group: str | None, market: str | None, min_odds: float | None, max_odds: float | None, status: str | None, selection: str | None, limit: int):
    day = day or datetime.now(UTC).astimezone().date()
    start, _ = local_day_bounds_utc(day)
    _, end = local_day_bounds_utc(day + timedelta(days=days - 1))
    q = select(ValueOpportunity).join(Fixture, Fixture.id == ValueOpportunity.fixture_id).join(Competition, Competition.id == Fixture.competition_id).where(Fixture.kickoff_utc >= start, Fixture.kickoff_utc < end)
    if status:
        q = q.where(ValueOpportunity.status == status)
    if min_ev is not None:
        q = q.where(ValueOpportunity.expected_value >= min_ev)
    if min_confidence is not None:
        q = q.where(ValueOpportunity.confidence >= min_confidence)
    if min_quality is not None:
        q = q.where(ValueOpportunity.data_quality >= min_quality)
    if competition:
        q = q.where(Competition.code == competition)
    if market_group:
        q = q.where(ValueOpportunity.market_group.in_(market_group.split(",")))
    if market:
        q = q.where(ValueOpportunity.market_key == market)
    if selection:
        q = q.where(ValueOpportunity.selection == selection)
    if min_odds is not None:
        q = q.where(ValueOpportunity.best_odds >= min_odds)
    if max_odds is not None:
        q = q.where(ValueOpportunity.best_odds <= max_odds)
    return day, list(db.scalars(q.order_by(ValueOpportunity.value_score.desc(), ValueOpportunity.expected_value.desc()).limit(limit)))


def _list(db, day, days, min_ev, min_confidence, min_quality, competition, market_group, market, min_odds, max_odds, status, selection, limit, movement=False):
    day, rows = _query(db, day, days, min_ev, min_confidence, min_quality, competition, market_group, market, min_odds, max_odds, status, selection, limit)
    return {"date": day.isoformat(), "days": days, "count": len(rows), "opportunities": [_opp_dict(db, o, movement) for o in rows], "disclaimer": "Statistical analysis is not a guarantee of future results."}


COMMON = dict(day=None, days=Query(1, ge=1, le=7), min_ev=None, min_confidence=None, min_quality=None, competition=None, market=None, min_odds=None, max_odds=None, selection=None, limit=Query(200, le=1000))


@router.get("/value")
def value(day: date | None = None, days: int = Query(1, ge=1, le=7), min_ev: float | None = None, min_confidence: float | None = None, min_quality: float | None = None, competition: str | None = None, market_group: str | None = None, market: str | None = None, min_odds: float | None = None, max_odds: float | None = None, status: str | None = "VALUE_CANDIDATE", selection: str | None = None, limit: int = Query(200, le=1000), movement: bool = False, db: Session = Depends(get_db)):
    return _list(db, day, days, min_ev, min_confidence, min_quality, competition, market_group, market, min_odds, max_odds, status or None, selection, limit, movement)


@router.get("/value/today")
def value_today(limit: int = Query(50, le=500), db: Session = Depends(get_db)):
    from app.services.settings_service import get_setting

    days = int(get_setting(db, "scanner").get("days_ahead", 2))
    return _list(db, None, days, None, None, None, None, None, None, None, None, "VALUE_CANDIDATE", None, limit)


@router.get("/goals")
def goals(day: date | None = None, days: int = Query(1, ge=1, le=7), status: str | None = "VALUE_CANDIDATE", limit: int = Query(200, le=1000), db: Session = Depends(get_db)):
    """High-scoring scanner: over/BTTS-yes markets ranked by value score, plus expected-goals context."""
    return _list(db, day, days, None, None, None, None, "goals,team_goals,btts,first_half", None, None, None, status or None, None, limit)


@router.get("/corners")
def corners(day: date | None = None, days: int = Query(1, ge=1, le=7), status: str | None = "VALUE_CANDIDATE", limit: int = Query(200, le=1000), db: Session = Depends(get_db)):
    return _list(db, day, days, None, None, None, None, "corners,team_corners", None, None, None, status or None, None, limit)


@router.get("/low-scoring")
def low_scoring(day: date | None = None, days: int = Query(1, ge=1, le=7), status: str | None = "VALUE_CANDIDATE", limit: int = Query(200, le=1000), db: Session = Depends(get_db)):
    _, rows = _query(db, day, days, None, None, None, None, None, None, None, None, status or None, None, limit * 3)
    rows = [o for o in rows if (o.market_group in ("goals", "team_goals") and o.selection == "under") or o.market_key == "btts_no"][:limit]
    return {"count": len(rows), "opportunities": [_opp_dict(db, o) for o in rows]}


@router.get("/scanners/expected")
def expected_scanner(day: date | None = None, days: int = Query(1, ge=1, le=7), db: Session = Depends(get_db)):
    """High-corner / high-scoring / low-scoring scanners based on expected totals vs league average (no odds required)."""
    from app.models import FeatureSnapshot, ModelPrediction

    day = day or datetime.now(UTC).astimezone().date()
    start, _ = local_day_bounds_utc(day)
    _, end = local_day_bounds_utc(day + timedelta(days=days - 1))
    fixtures = list(db.scalars(select(Fixture).where(Fixture.kickoff_utc >= start, Fixture.kickoff_utc < end)))
    out = []
    for fx in fixtures:
        snap = db.scalar(select(FeatureSnapshot).where(FeatureSnapshot.fixture_id == fx.id).order_by(FeatureSnapshot.created_at.desc()))
        g = db.scalar(select(ModelPrediction).where(ModelPrediction.fixture_id == fx.id, ModelPrediction.model_name == "dixon_coles", ModelPrediction.market_key == "goals_over_2.5"))
        c = db.scalar(select(ModelPrediction).where(ModelPrediction.fixture_id == fx.id, ModelPrediction.model_name == "corners", ModelPrediction.market_key == "corners_over_9.5"))
        if not snap or not g:
            continue
        lg = snap.features.get("league", {})
        lg_goals = (lg.get("home_goals") or 0) + (lg.get("away_goals") or 0)
        lg_corners = ((lg.get("home_corners") or 0) + (lg.get("away_corners") or 0)) or None
        eg = g.expected_home + g.expected_away
        ec = (c.expected_home + c.expected_away) if c else None
        out.append({"fixture_id": fx.id, "home_team": fx.home_team.name, "away_team": fx.away_team.name, "competition": fx.competition.name, "kickoff_utc": fx.kickoff_utc.isoformat(), "expected_goals": round(eg, 2), "league_goals": round(lg_goals, 2), "goals_ratio": round(eg / lg_goals, 3) if lg_goals else None, "expected_corners": round(ec, 2) if ec else None, "league_corners": round(lg_corners, 2) if lg_corners else None, "corners_ratio": round(ec / lg_corners, 3) if ec and lg_corners else None, "p_over_2_5": g.probability, "p_corners_over_9_5": c.probability if c else None, "data_quality": snap.data_quality})
    return {"high_scoring": sorted([o for o in out if o["goals_ratio"]], key=lambda o: -o["goals_ratio"])[:20], "low_scoring": sorted([o for o in out if o["goals_ratio"]], key=lambda o: o["goals_ratio"])[:20], "high_corners": sorted([o for o in out if o["corners_ratio"]], key=lambda o: -o["corners_ratio"])[:20]}


@router.get("/value/export")
def export(day: date | None = None, days: int = Query(1, ge=1, le=7), fmt: str = Query("csv", pattern="^(csv|json)$"), status: str | None = "VALUE_CANDIDATE", db: Session = Depends(get_db)):
    _, rows = _query(db, day, days, None, None, None, None, None, None, None, None, status or None, None, 5000)
    data = [_opp_dict(db, o) for o in rows]
    if fmt == "json":
        return data
    buf = io.StringIO()
    cols = ["home_team", "away_team", "competition", "kickoff_utc", "market", "selection", "best_odds", "best_bookmaker", "model_probability", "market_probability", "fair_odds", "edge", "expected_value", "value_score", "confidence", "data_quality", "status", "is_demo"]
    w = csv.DictWriter(buf, fieldnames=cols, extrasaction="ignore")
    w.writeheader()
    w.writerows(data)
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=value.csv"})
