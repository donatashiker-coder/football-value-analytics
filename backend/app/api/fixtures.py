from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models import Competition, FeatureSnapshot, Fixture, Injury, ModelPrediction, Result, Suspension, ValueOpportunity
from app.odds.markets import MARKET_BY_KEY
from app.reporting.daily import _opp_dict
from app.services.value_engine import fixture_display, load_current_odds, opening_and_closing
from app.statistics.engine import MatchHistory
from app.utils.time import local_day_bounds_utc

router = APIRouter(prefix="/fixtures", tags=["fixtures"])


def _fixture_summary(db: Session, fx: Fixture) -> dict:
    opps = list(db.scalars(select(ValueOpportunity).where(ValueOpportunity.fixture_id == fx.id).order_by(ValueOpportunity.value_score.desc())))
    best = next((o for o in opps if o.status == "VALUE_CANDIDATE"), None)
    snap = db.scalar(select(FeatureSnapshot).where(FeatureSnapshot.fixture_id == fx.id).order_by(FeatureSnapshot.created_at.desc()))
    pred = db.scalar(select(ModelPrediction).where(ModelPrediction.fixture_id == fx.id, ModelPrediction.market_key == "goals_over_2.5", ModelPrediction.model_name == "dixon_coles"))
    corner = db.scalar(select(ModelPrediction).where(ModelPrediction.fixture_id == fx.id, ModelPrediction.market_key == "corners_over_9.5", ModelPrediction.model_name == "corners"))
    res = fx.result
    return {
        **fixture_display(fx),
        "analysed": snap is not None,
        "data_quality": snap.data_quality if snap else None,
        "value_candidates": sum(1 for o in opps if o.status == "VALUE_CANDIDATE"),
        "markets_evaluated": len(opps),
        "best_opportunity": _opp_dict(db, best) if best else None,
        "expected_goals": {"home": pred.expected_home, "away": pred.expected_away} if pred else None,
        "expected_corners": {"home": corner.expected_home, "away": corner.expected_away} if corner else None,
        "result": {"home_goals": res.home_goals, "away_goals": res.away_goals, "home_corners": res.home_corners, "away_corners": res.away_corners} if res else None,
    }


@router.get("/today")
def fixtures_today(day: date | None = None, days: int = Query(1, ge=1, le=7), competition: str | None = None, db: Session = Depends(get_db)):
    day = day or datetime.now(UTC).astimezone().date()
    start, _ = local_day_bounds_utc(day)
    _, end = local_day_bounds_utc(day + timedelta(days=days - 1))
    q = select(Fixture).join(Competition, Competition.id == Fixture.competition_id).where(Fixture.kickoff_utc >= start, Fixture.kickoff_utc < end)
    if competition:
        q = q.where(Competition.code == competition)
    fixtures = list(db.scalars(q.order_by(Fixture.kickoff_utc)))
    return {"date": day.isoformat(), "count": len(fixtures), "fixtures": [_fixture_summary(db, f) for f in fixtures]}


@router.get("/search")
def search_fixtures(q: str = Query(min_length=2, max_length=60), limit: int = Query(25, le=100), db: Session = Depends(get_db)):
    from app.models import Team

    like = f"%{q}%"
    teams = [t.id for t in db.scalars(select(Team).where(Team.name.ilike(like)))]
    if not teams:
        return {"fixtures": []}
    fixtures = list(db.scalars(select(Fixture).where((Fixture.home_team_id.in_(teams)) | (Fixture.away_team_id.in_(teams))).order_by(Fixture.kickoff_utc.desc()).limit(limit)))
    return {"fixtures": [fixture_display(f) for f in fixtures]}


@router.get("/{fixture_id}")
def fixture_detail(fixture_id: str, db: Session = Depends(get_db)):
    fx = db.get(Fixture, fixture_id)
    if fx is None:
        raise HTTPException(404, "fixture not found")
    snap = db.scalar(select(FeatureSnapshot).where(FeatureSnapshot.fixture_id == fx.id).order_by(FeatureSnapshot.created_at.desc()))
    opps = list(db.scalars(select(ValueOpportunity).where(ValueOpportunity.fixture_id == fx.id).order_by(ValueOpportunity.value_score.desc(), ValueOpportunity.expected_value.desc())))
    preds = list(db.scalars(select(ModelPrediction).where(ModelPrediction.fixture_id == fx.id)))
    by_model: dict[str, dict[str, float]] = {}
    for p in preds:
        by_model.setdefault(p.model_name, {})[p.market_key] = p.probability
    primary = next((p for p in preds if p.model_name == "dixon_coles"), None)
    corner = next((p for p in preds if p.model_name == "corners"), None)
    comps = load_current_odds(db, fx.id)
    odds = {k: c.as_dict() for k, c in comps.items()}
    movement = {}
    for key in ("match_home", "match_draw", "match_away", "goals_over_2.5", "goals_under_2.5", "btts_yes", "corners_over_9.5"):
        if key in comps:
            from app.odds.math import odds_movement

            o, c = opening_and_closing(db, fx.id, key)
            movement[key] = odds_movement(o, c)
    feats = snap.features if snap else None
    # recent form from history (last 10 for both teams), as-of now (or kickoff for finished fixtures)
    cutoff = min(datetime.now(UTC), fx.kickoff_utc if fx.kickoff_utc.tzinfo else fx.kickoff_utc.replace(tzinfo=UTC))
    hist = MatchHistory.load(db, [fx.competition_id], before=cutoff + timedelta(days=400))
    form = {}
    for side, tid in (("home", fx.home_team_id), ("away", fx.away_team_id)):
        recs = hist.team_matches(tid, cutoff)[-10:]
        form[side] = [{"fixture_id": r.fixture_id, "date": r.kickoff.isoformat(), "is_home": r.is_home, "goals_for": r.goals_for, "goals_against": r.goals_against, "xg_for": r.xg_for, "xg_against": r.xg_against, "corners_for": r.corners_for, "corners_against": r.corners_against, "result": "W" if r.goals_for > r.goals_against else "D" if r.goals_for == r.goals_against else "L"} for r in recs]
    h2h = [m for m in hist.team_matches(fx.home_team_id, cutoff) if m.opponent_id == fx.away_team_id][-6:]
    news = {}
    for side, tid in (("home", fx.home_team_id), ("away", fx.away_team_id)):
        inj = list(db.scalars(select(Injury).where(Injury.team_id == tid, Injury.active.is_(True))))
        sus = list(db.scalars(select(Suspension).where(Suspension.team_id == tid, Suspension.active.is_(True))))
        news[side] = {"injuries": [{"player": i.player_name, "reason": i.reason, "status": i.status, "importance": i.player_importance, "source": i.source, "retrieved_at": i.retrieved_at.isoformat() if i.retrieved_at else None} for i in inj], "suspensions": [{"player": s.player_name, "reason": s.reason} for s in sus], "available": bool(inj or sus) or (feats or {}).get(f"{side}_news", {}).get("available", False)}
    res = db.scalar(select(Result).where(Result.fixture_id == fx.id))
    return {
        **fixture_display(fx),
        "venue": fx.venue,
        "matchday": fx.matchday,
        "result": {"home_goals": res.home_goals, "away_goals": res.away_goals, "home_goals_ht": res.home_goals_ht, "away_goals_ht": res.away_goals_ht, "home_corners": res.home_corners, "away_corners": res.away_corners} if res else None,
        "features": feats,
        "feature_snapshot": {"id": snap.id, "feature_version": snap.feature_version, "data_timestamp": snap.data_timestamp.isoformat(), "data_quality": snap.data_quality, "warnings": snap.warnings} if snap else None,
        "model": {
            "expected_goals": {"home": primary.expected_home, "away": primary.expected_away} if primary else None,
            "expected_corners": {"home": corner.expected_home, "away": corner.expected_away} if corner else None,
            "probabilities": by_model,
            "versions": sorted({f"{p.model_name}@{p.model_version}" for p in preds}),
            "prediction_timestamp": primary.prediction_timestamp.isoformat() if primary else None,
        },
        "opportunities": [_opp_dict(db, o) for o in opps],
        "odds": odds,
        "odds_movement": movement,
        "form": form,
        "head_to_head": [{"date": m.kickoff.isoformat(), "home_goals": m.goals_for if m.is_home else m.goals_against, "away_goals": m.goals_against if m.is_home else m.goals_for, "home_was": "this_home_team" if m.is_home else "this_away_team"} for m in h2h],
        "team_news": news,
        "markets": {k: {"name": m.name, "group": m.group} for k, m in MARKET_BY_KEY.items()},
    }
