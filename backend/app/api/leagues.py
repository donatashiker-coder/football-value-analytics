from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models import Backtest, Competition, Fixture, LeagueSetting, Result, Season, Team
from app.providers.leagues import LEAGUE_BY_CODE
from app.statistics.engine import MatchHistory, compute_team_stats

router = APIRouter(prefix="/leagues", tags=["leagues"])


class LeagueSettingUpdate(BaseModel):
    enabled: bool | None = None
    min_sample_size: int | None = None
    reliability: float | None = None
    home_advantage: float | None = None


@router.get("")
def list_leagues(db: Session = Depends(get_db)):
    out = []
    for c in db.scalars(select(Competition).order_by(Competition.country, Competition.tier)):
        ls = db.scalar(select(LeagueSetting).where(LeagueSetting.competition_id == c.id))
        n_fix = db.scalar(select(func.count(Fixture.id)).where(Fixture.competition_id == c.id))
        n_res = db.scalar(select(func.count(Result.id)).join(Fixture, Fixture.id == Result.fixture_id).where(Fixture.competition_id == c.id))
        lg = LEAGUE_BY_CODE.get(c.code)
        out.append({"id": c.id, "code": c.code, "name": c.name, "country": c.country, "tier": c.tier, "enabled": c.enabled, "provider_ids": c.provider_ids, "fixtures": n_fix, "results": n_res, "settings": {"min_sample_size": ls.min_sample_size if ls else 6, "reliability": ls.reliability if ls else (lg.reliability if lg else 0.8), "home_advantage": ls.home_advantage if ls else None}, "is_demo": c.source == "demo"})
    return out


@router.get("/{code}")
def league_detail(code: str, db: Session = Depends(get_db)):
    c = db.scalar(select(Competition).where(Competition.code == code))
    if c is None:
        raise HTTPException(404, "league not found")
    now = datetime.now(UTC)
    season = db.scalar(select(Season).where(Season.competition_id == c.id).order_by(Season.year.desc()))
    year = season.year if season else now.year
    hist = MatchHistory.load(db, [c.id], before=now)
    league = hist.league_averages(c.id, year, now)
    ratings = hist.elo_ratings(c.id, now)
    teams = list(db.scalars(select(Team).where(Team.competition_id == c.id)))
    table = []
    for t in teams:
        ts = compute_team_stats(hist, t.id, c.id, year, now, league)
        s = ts.stats
        table.append({"team_id": t.id, "team": t.name, "matches": ts.matches, "points": round((s.get("points_per_game") or 0) * ts.matches), "ppg": s.get("points_per_game"), "goals_for": s.get("goals_for_avg"), "goals_against": s.get("goals_against_avg"), "xg_for": s.get("xg_for_avg"), "xg_against": s.get("xg_against_avg"), "corners_for": s.get("corners_for_avg"), "corners_against": s.get("corners_against_avg"), "btts_pct": s.get("btts_pct"), "over_2_5_pct": s.get("over_2.5_pct"), "clean_sheet_pct": s.get("clean_sheet_pct"), "elo": ratings.get(t.id), "home_attack": s.get("home_attack"), "away_attack": s.get("away_attack")})
    table.sort(key=lambda r: (-(r["points"] or 0), -(r["ppg"] or 0)))
    for i, r in enumerate(table, 1):
        r["position"] = i
    backtests = [{"strategy": b.strategy, "league_rows": [r for r in b.breakdowns.get("by_league", []) if r["key"] == code]} for b in db.scalars(select(Backtest).where(Backtest.status == "completed").order_by(Backtest.created_at.desc()).limit(10))]
    return {"id": c.id, "code": c.code, "name": c.name, "country": c.country, "season_year": year, "averages": league.as_dict(), "table": table, "backtests": [b for b in backtests if b["league_rows"]], "is_demo": c.source == "demo"}


@router.patch("/{code}/settings")
def update_league(code: str, body: LeagueSettingUpdate, db: Session = Depends(get_db)):
    c = db.scalar(select(Competition).where(Competition.code == code))
    if c is None:
        raise HTTPException(404, "league not found")
    ls = db.scalar(select(LeagueSetting).where(LeagueSetting.competition_id == c.id))
    if ls is None:
        ls = LeagueSetting(competition_id=c.id)
        db.add(ls)
    if body.enabled is not None:
        c.enabled = body.enabled
        ls.enabled = body.enabled
    if body.min_sample_size is not None:
        ls.min_sample_size = max(0, body.min_sample_size)
    if body.reliability is not None:
        ls.reliability = min(max(body.reliability, 0.0), 1.0)
    if body.home_advantage is not None:
        ls.home_advantage = min(max(body.home_advantage, 0.5), 1.5)
    db.commit()
    return {"code": code, "enabled": c.enabled, "min_sample_size": ls.min_sample_size, "reliability": ls.reliability, "home_advantage": ls.home_advantage}
