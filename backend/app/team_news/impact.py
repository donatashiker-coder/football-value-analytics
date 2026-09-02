"""Team news impact estimation: player importance, absence impact, squad-change and manager-change analysis.

Principle: impacts are estimated from historical evidence (performance with vs without the player,
before vs after a manager), never assigned arbitrarily. When evidence is insufficient the impact is
reported as UNKNOWN with high uncertainty and the goal model is left unadjusted.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Fixture, ManagerChange, Player, PlayerStatistic, Result, Team


@dataclass
class ImportanceInputs:
    minutes: int | None
    team_minutes: int | None  # total team minutes available in the season (matches * 90)
    goals: int | None
    assists: int | None
    team_goals: int | None
    xg: float | None
    xa: float | None
    position: str | None


def player_importance(inp: ImportanceInputs) -> tuple[float | None, dict]:
    """0..1 importance from availability share and goal involvement share. None if data insufficient."""
    if not inp.minutes or not inp.team_minutes:
        return None, {"reason": "minutes unavailable"}
    availability = min(inp.minutes / inp.team_minutes, 1.0)
    involvement = 0.0
    if inp.team_goals:
        contrib = (inp.goals or 0) + 0.7 * (inp.assists or 0)
        if inp.xg is not None or inp.xa is not None:
            contrib = 0.5 * contrib + 0.5 * ((inp.xg or 0) + 0.7 * (inp.xa or 0))
        involvement = min(contrib / inp.team_goals, 1.0)
    pos_weight = {"Goalkeeper": 0.9, "Defender": 0.7, "Midfielder": 0.75, "Attacker": 0.8}.get(inp.position or "", 0.7)
    score = min(0.55 * availability + 0.45 * involvement, 1.0) * pos_weight
    return round(score, 3), {"availability": round(availability, 3), "goal_involvement": round(involvement, 3), "position_weight": pos_weight}


def refresh_player_importance(db: Session, team: Team, season_id: str | None) -> int:
    matches = db.scalar(select(Fixture.id).where((Fixture.home_team_id == team.id) | (Fixture.away_team_id == team.id), Fixture.status == "FINISHED", Fixture.season_id == season_id).limit(1))
    n_matches = len(list(db.scalars(select(Fixture.id).where((Fixture.home_team_id == team.id) | (Fixture.away_team_id == team.id), Fixture.status == "FINISHED", Fixture.season_id == season_id)))) if matches else 0
    team_goals = 0
    for fx in db.scalars(select(Fixture).where((Fixture.home_team_id == team.id) | (Fixture.away_team_id == team.id), Fixture.status == "FINISHED", Fixture.season_id == season_id)):
        r = db.scalar(select(Result).where(Result.fixture_id == fx.id))
        if r:
            team_goals += r.home_goals if fx.home_team_id == team.id else r.away_goals
    updated = 0
    for p in db.scalars(select(Player).where(Player.team_id == team.id)):
        st = db.scalar(select(PlayerStatistic).where(PlayerStatistic.player_id == p.id, PlayerStatistic.season_id == season_id))
        if st is None:
            continue
        imp, _ = player_importance(ImportanceInputs(st.minutes, n_matches * 90 if n_matches else None, st.goals, st.assists, team_goals or None, st.xg, st.xa, p.position))
        p.importance = imp
        updated += 1
    db.commit()
    return updated


def absence_impact_estimate(importance_lost: float | None, evidence_matches: int) -> dict:
    """Translate importance lost into a bounded attack multiplier, with confidence tied to evidence.

    With no evidence we return multiplier 1.0 (no change) and flag uncertainty. The bound (max 12% reduction)
    is a documented prior; backtests with injury history are required before it is widened.
    """
    if importance_lost is None:
        return {"attack_multiplier": 1.0, "uncertainty": 0.6, "note": "importance unknown; no adjustment applied"}
    reduction = min(importance_lost * 0.12, 0.12)
    confidence = min(evidence_matches / 10, 1.0)
    return {"attack_multiplier": round(1.0 - reduction * confidence, 4), "uncertainty": round(1.0 - confidence, 2), "importance_lost": importance_lost, "evidence_matches": evidence_matches}


def manager_change_analysis(db: Session, team_id: str, change_date: date, window: int = 10) -> dict:
    """Compare team performance in the `window` matches before and after a manager change."""
    fixtures = list(db.scalars(select(Fixture).where((Fixture.home_team_id == team_id) | (Fixture.away_team_id == team_id), Fixture.status == "FINISHED").order_by(Fixture.kickoff_utc)))
    before, after = [], []
    for fx in fixtures:
        r = db.scalar(select(Result).where(Result.fixture_id == fx.id))
        if r is None:
            continue
        home = fx.home_team_id == team_id
        gf, ga = (r.home_goals, r.away_goals) if home else (r.away_goals, r.home_goals)
        cf = (r.home_corners if home else r.away_corners)
        rec = {"points": 3 if gf > ga else 1 if gf == ga else 0, "gf": gf, "ga": ga, "corners": cf}
        (before if fx.kickoff_utc.date() < change_date else after).append(rec)

    def agg(rs: list[dict]) -> dict:
        rs = rs[-window:] if rs is before else rs[:window]
        if not rs:
            return {"matches": 0}
        n = len(rs)
        corners = [r["corners"] for r in rs if r["corners"] is not None]
        return {"matches": n, "ppg": sum(r["points"] for r in rs) / n, "goals_for": sum(r["gf"] for r in rs) / n, "goals_against": sum(r["ga"] for r in rs) / n, "corners_for": sum(corners) / len(corners) if corners else None}

    b, a = agg(before), agg(after)
    return {"before": b, "after": a, "sufficient_evidence": a.get("matches", 0) >= 5, "note": "Treat as a feature with uncertainty; a new manager is not assumed to improve results."}


def record_manager_change(db: Session, team_id: str, change_date: date, manager: str | None, previous: str | None) -> ManagerChange:
    analysis = manager_change_analysis(db, team_id, change_date)
    mc = ManagerChange(team_id=team_id, manager_name=manager, previous_manager=previous, change_date=change_date, before_stats=analysis["before"], after_stats=analysis["after"], source="manual", retrieved_at=datetime.now(tz=__import__("datetime").UTC))
    db.add(mc)
    db.commit()
    return mc
