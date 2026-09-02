"""Daily report: assembled entirely from stored scan output. Text + structured JSON."""
from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.betting.paper import bankroll_state
from app.models import DataQualityLog, Fixture, ValueOpportunity
from app.odds.markets import MARKET_BY_KEY
from app.services.evaluation import model_performance
from app.services.value_engine import fixture_display, opening_and_closing
from app.utils.time import local_day_bounds_utc

DISCLAIMER = "Statistical analysis is not a guarantee of future results. Value candidates are model estimates, not recommendations."


def _opp_dict(db: Session, o: ValueOpportunity, with_movement: bool = False) -> dict:
    m = MARKET_BY_KEY.get(o.market_key)
    d = {
        "id": o.id, **fixture_display(o.fixture), "market_key": o.market_key, "market": m.name if m else o.market_key, "market_group": o.market_group, "selection": o.selection, "line": o.line,
        "best_odds": o.best_odds, "best_bookmaker": o.best_bookmaker, "median_odds": o.median_odds, "bookmaker_count": o.bookmaker_count, "model_probability": o.model_probability, "market_probability": o.market_probability,
        "fair_odds": o.fair_odds, "edge": o.edge, "expected_value": o.expected_value, "value_label": o.value_label, "confidence": o.confidence, "data_quality": o.data_quality, "value_score": o.value_score,
        "status": o.status, "no_bet_reasons": o.no_bet_reasons, "key_factors": o.key_factors, "risk_factors": o.risk_factors, "explanation": o.explanation, "llm_explanation": o.llm_explanation,
        "model_version": o.model_version, "odds_recorded_at": o.odds_recorded_at.isoformat() if o.odds_recorded_at else None, "scan_date": o.scan_date.isoformat(), "is_demo": o.is_demo,
    }
    if with_movement:
        opening, current = opening_and_closing(db, o.fixture_id, o.market_key)
        from app.odds.math import odds_movement

        d["movement"] = odds_movement(opening, current)
    return d


def opportunities_for_day(db: Session, day: date, days: int = 1) -> list[ValueOpportunity]:
    start, _ = local_day_bounds_utc(day)
    _, end = local_day_bounds_utc(day + timedelta(days=days - 1))
    return list(db.scalars(select(ValueOpportunity).join(Fixture, Fixture.id == ValueOpportunity.fixture_id).where(Fixture.kickoff_utc >= start, Fixture.kickoff_utc < end).order_by(ValueOpportunity.value_score.desc())))


def build_daily_report(db: Session, day: date | None = None, top_n: int = 10, days: int | None = None) -> dict:
    """Report over the scan window (scanner.days_ahead, default 2 days) starting at `day`."""
    from app.services.settings_service import get_setting

    day = day or datetime.now(UTC).astimezone().date()
    days = days or int(get_setting(db, "scanner").get("days_ahead", 2))
    opps = opportunities_for_day(db, day, days)
    cands = [o for o in opps if o.status == "VALUE_CANDIDATE"]
    fixtures = {o.fixture_id for o in opps}
    leagues = {o.fixture.competition_id for o in opps}

    def top(group_filter, n=top_n) -> list[dict]:
        return [_opp_dict(db, o) for o in cands if group_filter(o)][:n]

    no_bet_fixtures = sorted({o.fixture_id for o in opps} - {o.fixture_id for o in cands})
    warnings = list(db.scalars(select(DataQualityLog).where(DataQualityLog.fixture_id.in_(list(fixtures))).order_by(DataQualityLog.created_at.desc()).limit(50))) if fixtures else []
    stale = [o for o in opps if o.odds_recorded_at and (datetime.now(UTC) - o.odds_recorded_at).total_seconds() > 4 * 3600]
    return {
        "date": day.isoformat(),
        "window_days": days,
        "generated_at": datetime.now(UTC).isoformat(),
        "fixtures_analysed": len(fixtures),
        "leagues": len(leagues),
        "markets_evaluated": len(opps),
        "value_candidates": len(cands),
        "top_value": top(lambda o: True),
        "top_corners": top(lambda o: o.market_group in ("corners", "team_corners")),
        "top_goals": top(lambda o: o.market_group in ("goals", "team_goals") and o.selection == "over"),
        "top_low_scoring": top(lambda o: (o.market_group == "goals" and o.selection == "under") or o.market_key == "btts_no"),
        "top_btts": top(lambda o: o.market_group == "btts"),
        "no_bet_fixtures": [fixture_display(db.get(Fixture, fid)) for fid in no_bet_fixtures[:30]],
        "data_quality_warnings": [{"fixture_id": w.fixture_id, "component": w.component, "level": w.level, "message": w.message} for w in warnings],
        "stale_odds": len(stale),
        "team_news_warnings": [f"{o.fixture.home_team.name} v {o.fixture.away_team.name}: {r}" for o in cands for r in o.risk_factors if "doubtful" in r or "news unavailable" in r][:20],
        "model_performance_30d": model_performance(db, 30, "dixon_coles"),
        "paper_betting": {k: v for k, v in bankroll_state(db).items() if k != "equity_curve"},
        "disclaimer": DISCLAIMER,
        "is_demo": any(o.is_demo for o in opps),
    }


def format_text_report(rep: dict) -> str:
    line = "=" * 44
    out = [line, "FOOTBALL VALUE ANALYTICS", datetime.fromisoformat(rep["date"]).strftime("%d %B %Y").upper(), line]
    if rep.get("is_demo"):
        out.append("*** DEMO DATA: synthetic fixtures and odds ***")
    out.append(f"Fixtures analysed: {rep['fixtures_analysed']}  Leagues: {rep['leagues']}  Markets: {rep['markets_evaluated']}  Value candidates: {rep['value_candidates']}")
    for o in rep["top_value"]:
        out += [
            line, f"MATCH: {o['home_team']} vs {o['away_team']}", f"LEAGUE: {o['competition']}", f"KICKOFF: {o['kickoff_utc']}", f"MARKET: {o['market']}",
            f"BEST ODDS: {o['best_odds']:.2f}  BOOKMAKER: {o['best_bookmaker']}", f"MODEL PROBABILITY: {o['model_probability'] * 100:.1f}%",
            f"MARKET IMPLIED: {o['market_probability'] * 100:.1f}%" if o["market_probability"] is not None else "MARKET IMPLIED: DATA UNAVAILABLE",
            f"FAIR ODDS: {o['fair_odds']:.2f}", f"EDGE: {o['edge'] * 100:+.1f} percentage points" if o["edge"] is not None else "EDGE: n/a", f"EXPECTED VALUE: {o['expected_value'] * 100:+.1f}%",
            f"MODEL CONFIDENCE: {o['confidence']:.0f}/100", f"DATA QUALITY: {o['data_quality']:.0f}/100", f"VALUE SCORE: {o['value_score']:.0f}", "KEY FACTORS:",
        ]
        out += [f"  * {k}" for k in o["key_factors"]]
        if o["risk_factors"]:
            out.append("RISKS:")
            out += [f"  * {r}" for r in o["risk_factors"]]
        out.append("STATUS: STATISTICAL VALUE CANDIDATE")
    out += [line, f"NO-BET fixtures: {len(rep['no_bet_fixtures'])}", f"Data quality warnings: {len(rep['data_quality_warnings'])}", f"Stale odds: {rep['stale_odds']}"]
    mp = rep.get("model_performance_30d") or {}
    if mp.get("n"):
        out.append(f"Model (30d): n={mp['n']} Brier={mp['brier']:.3f} LogLoss={mp['log_loss']:.3f} ECE={mp['expected_calibration_error']:.3f}")
    out += [line, rep["disclaimer"], line]
    return "\n".join(out)
