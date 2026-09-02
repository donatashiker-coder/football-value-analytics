"""Daily scanner: fixtures -> features -> predictions -> value -> ranking -> storage."""
from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import Competition, DataQualityLog, FeatureSnapshot, Fixture, ModelPrediction, ValueOpportunity
from app.services.evaluation import strategy_performance_scores
from app.services.features import FEATURE_VERSION, build_features
from app.services.prediction import PRIMARY_MODEL, markets_with_probability, predict_fixture
from app.services.settings_service import corner_params, form_weights, get_setting, goal_params, value_config
from app.services.value_engine import evaluate_market, fixture_odds_bookmaker_count, load_current_odds
from app.statistics.engine import MatchHistory
from app.utils.logging import get_logger
from app.utils.time import local_day_bounds_utc

log = get_logger(__name__)


def utcnow() -> datetime:
    return datetime.now(UTC)


def _season_year(fx: Fixture, db: Session) -> int:
    from app.models import Season

    if fx.season_id:
        s = db.get(Season, fx.season_id)
        if s:
            return s.year
    return fx.kickoff_utc.year if fx.kickoff_utc.month >= 7 else fx.kickoff_utc.year - 1


def fixtures_for_window(db: Session, start: datetime, end: datetime, competition_codes: list[str] | None = None) -> list[Fixture]:
    q = select(Fixture).join(Competition, Competition.id == Fixture.competition_id).where(Fixture.kickoff_utc >= start, Fixture.kickoff_utc < end, Fixture.status == "SCHEDULED", Competition.enabled.is_(True))
    if competition_codes:
        q = q.where(Competition.code.in_(competition_codes))
    return list(db.scalars(q.order_by(Fixture.kickoff_utc)))


def run_scan(db: Session, scan_day: date | None = None, days_ahead: int | None = None, competition_codes: list[str] | None = None, is_demo: bool = False) -> dict:
    """Analyse every scheduled fixture in the window and persist predictions + value opportunities."""
    now = utcnow()
    scanner = get_setting(db, "scanner")
    days = days_ahead if days_ahead is not None else int(scanner.get("days_ahead", 2))
    day = scan_day or now.astimezone().date()
    start, _ = local_day_bounds_utc(day)
    _, end = local_day_bounds_utc(day + timedelta(days=days - 1))
    fixtures = fixtures_for_window(db, start, end, competition_codes)
    cfg = value_config(db)
    fw, gp, cp = form_weights(db), goal_params(db), corner_params(db)
    enabled_groups = set(scanner.get("enabled_market_groups", []))
    exclude_red = bool(scanner.get("exclude_early_red_cards", False))
    prior_strength = float(scanner.get("prior_strength", 8.0))
    strat_scores = strategy_performance_scores(db)
    comp_ids = sorted({f.competition_id for f in fixtures})
    hist = MatchHistory.load(db, comp_ids, before=now) if comp_ids else MatchHistory()
    summary = {"date": day.isoformat(), "fixtures": len(fixtures), "analysed": 0, "value_candidates": 0, "no_bet": 0, "odds_unavailable": 0, "leagues": len(comp_ids), "warnings": []}
    for fx in fixtures:
        cutoff = min(now, fx.kickoff_utc.replace(tzinfo=UTC) if fx.kickoff_utc.tzinfo is None else fx.kickoff_utc)
        comps = load_current_odds(db, fx.id)
        try:
            ff = build_features(db, hist, fx, cutoff, _season_year(fx, db), fw, prior_strength, fixture_odds_bookmaker_count(comps), exclude_red)
            pred = predict_fixture(ff, gp, cp, now)
        except Exception as exc:  # one bad fixture must not stop the scan
            log.exception("scan failed for fixture %s", fx.id)
            db.add(DataQualityLog(fixture_id=fx.id, component="scan", level="error", message=str(exc)[:500]))
            summary["warnings"].append(f"{fx.home_team.name} v {fx.away_team.name}: {exc}")
            continue
        # replace previous snapshot/predictions/opportunities for this fixture (latest scan wins; history kept in backtests)
        db.execute(delete(ValueOpportunity).where(ValueOpportunity.fixture_id == fx.id))
        db.execute(delete(ModelPrediction).where(ModelPrediction.fixture_id == fx.id, ModelPrediction.settled.is_(False)))
        snap = FeatureSnapshot(fixture_id=fx.id, feature_version=FEATURE_VERSION, data_timestamp=cutoff, features=_jsonable(ff.features), data_quality=ff.data_quality, warnings=ff.warnings)
        db.add(snap)
        db.flush()
        for w in ff.warnings:
            db.add(DataQualityLog(fixture_id=fx.id, component="features", level="warning", message=w))
        for m in markets_with_probability(pred):
            if m.group not in enabled_groups:
                continue
            vr = evaluate_market(m, ff, pred, comps, cfg, now, strat_scores.get(m.strategy))
            # store the primary prediction (for later calibration / CLV) and the secondary models
            for model_name, probs in pred.model_probabilities.items():
                if m.prob_key not in probs:
                    continue
                is_primary = model_name in (PRIMARY_MODEL, "corners")
                db.add(
                    ModelPrediction(
                        fixture_id=fx.id, feature_snapshot_id=snap.id, model_name=model_name, model_version=pred.model_versions.get(model_name, pred.model_versions.get("corners", "")), feature_version=FEATURE_VERSION,
                        market_key=m.key, selection=m.selection, line=m.line, probability=probs[m.prob_key], fair_odds=1 / max(probs[m.prob_key], 1e-6),
                        expected_home=pred.home_corners if m.group in ("corners", "team_corners") else pred.home_lambda, expected_away=pred.away_corners if m.group in ("corners", "team_corners") else pred.away_lambda,
                        data_timestamp=cutoff, prediction_timestamp=now, best_odds_at_prediction=vr.best_odds if is_primary else None,
                    )
                )
            db.add(
                ValueOpportunity(
                    fixture_id=fx.id, market_key=m.key, market_group=m.group, selection=m.selection, line=m.line, model_probability=vr.model_probability, market_probability=vr.market_probability,
                    raw_implied_probability=vr.raw_implied, best_odds=vr.best_odds, best_bookmaker=vr.best_bookmaker, median_odds=vr.median_odds, bookmaker_count=vr.bookmaker_count, fair_odds=vr.fair_odds,
                    edge=vr.edge, expected_value=vr.ev, value_label=vr.label, confidence=vr.confidence, data_quality=vr.data_quality, value_score=vr.score, status=vr.status, no_bet_reasons=vr.no_bet_reasons,
                    key_factors=vr.key_factors, risk_factors=vr.risk_factors, explanation=vr.explanation, model_version=pred.model_versions.get("corners" if m.group in ("corners", "team_corners") else PRIMARY_MODEL),
                    odds_recorded_at=vr.odds_recorded_at, scan_date=now, is_demo=is_demo or fx.is_demo,
                )
            )
            summary[{"VALUE_CANDIDATE": "value_candidates", "NO_BET": "no_bet", "ODDS_UNAVAILABLE": "odds_unavailable"}[vr.status]] += 1
        summary["analysed"] += 1
        db.commit()
    db.commit()
    return summary


def _jsonable(obj):
    import math

    if isinstance(obj, dict):
        return {str(k): _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(v) for v in obj]
    if isinstance(obj, float):
        return None if math.isnan(obj) or math.isinf(obj) else obj
    if isinstance(obj, datetime):
        return obj.isoformat()
    if hasattr(obj, "__dict__") and not isinstance(obj, type):
        return _jsonable(vars(obj))
    return obj
