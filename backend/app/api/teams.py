from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models import Fixture, Injury, ManagerChange, Season, Team, Transfer
from app.schemas import ManagerChangeCreate
from app.services.settings_service import form_weights
from app.statistics.engine import MatchHistory, compute_team_stats
from app.team_news.impact import record_manager_change

router = APIRouter(prefix="/teams", tags=["teams"])


@router.get("")
def list_teams(q: str | None = Query(None, max_length=60), competition: str | None = None, limit: int = Query(100, le=500), db: Session = Depends(get_db)):
    from app.models import Competition

    query = select(Team)
    if q:
        query = query.where(Team.name.ilike(f"%{q}%"))
    if competition:
        query = query.join(Competition, Competition.id == Team.competition_id).where(Competition.code == competition)
    teams = list(db.scalars(query.order_by(Team.name).limit(limit)))
    return [{"id": t.id, "name": t.name, "short_name": t.short_name, "country": t.country, "competition_id": t.competition_id, "is_demo": t.is_demo, "source": t.source} for t in teams]


@router.get("/{team_id}")
def team_detail(team_id: str, db: Session = Depends(get_db)):
    team = db.get(Team, team_id)
    if team is None:
        raise HTTPException(404, "team not found")
    now = datetime.now(UTC)
    if not team.competition_id:
        return {"id": team.id, "name": team.name, "stats": None, "warning": "team has no competition"}
    hist = MatchHistory.load(db, [team.competition_id], before=now)
    season = db.scalar(select(Season).where(Season.competition_id == team.competition_id).order_by(Season.year.desc()))
    season_year = season.year if season else now.year
    league = hist.league_averages(team.competition_id, season_year, now)
    ts = compute_team_stats(hist, team.id, team.competition_id, season_year, now, league, form_weights(db))
    ratings = hist.elo_ratings(team.competition_id, now)
    matches = hist.team_matches(team.id, now, team.competition_id)[-20:]
    upcoming = list(db.scalars(select(Fixture).where((Fixture.home_team_id == team.id) | (Fixture.away_team_id == team.id), Fixture.status == "SCHEDULED").order_by(Fixture.kickoff_utc).limit(5)))
    injuries = list(db.scalars(select(Injury).where(Injury.team_id == team.id, Injury.active.is_(True))))
    transfers = list(db.scalars(select(Transfer).where((Transfer.to_team_id == team.id) | (Transfer.from_team_id == team.id)).order_by(Transfer.transfer_date.desc()).limit(10)))
    managers = list(db.scalars(select(ManagerChange).where(ManagerChange.team_id == team.id).order_by(ManagerChange.change_date.desc())))
    return {
        "id": team.id, "name": team.name, "competition_id": team.competition_id, "is_demo": team.is_demo, "season_year": season_year, "elo": ratings.get(team.id),
        "stats": ts.stats, "warnings": ts.warnings, "league_averages": league.as_dict(),
        "recent_matches": [{"fixture_id": m.fixture_id, "date": m.kickoff.isoformat(), "is_home": m.is_home, "opponent_id": m.opponent_id, "goals_for": m.goals_for, "goals_against": m.goals_against, "xg_for": m.xg_for, "xg_against": m.xg_against, "corners_for": m.corners_for, "corners_against": m.corners_against, "early_red_card": m.early_red_card} for m in matches],
        "upcoming": [{"fixture_id": f.id, "kickoff_utc": f.kickoff_utc.isoformat(), "home_team": f.home_team.name, "away_team": f.away_team.name} for f in upcoming],
        "injuries": [{"player": i.player_name, "reason": i.reason, "status": i.status, "importance": i.player_importance, "source": i.source} for i in injuries],
        "transfers": [{"player": t.player_name, "type": t.transfer_type, "date": t.transfer_date.isoformat() if t.transfer_date else None, "direction": "in" if t.to_team_id == team.id else "out", "importance": t.player_importance, "impact": t.impact_estimate} for t in transfers],
        "manager_changes": [{"date": m.change_date.isoformat(), "manager": m.manager_name, "previous": m.previous_manager, "before": m.before_stats, "after": m.after_stats} for m in managers],
    }


@router.post("/manager-change")
def add_manager_change(body: ManagerChangeCreate, db: Session = Depends(get_db)):
    if db.get(Team, body.team_id) is None:
        raise HTTPException(404, "team not found")
    mc = record_manager_change(db, body.team_id, body.change_date, body.manager_name, body.previous_manager)
    return {"id": mc.id, "before": mc.before_stats, "after": mc.after_stats}
