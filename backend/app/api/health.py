from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app import __version__
from app.api.deps import get_db
from app.config import get_settings
from app.models import ApiRequest, Fixture, ModelPrediction, Odds, Result, ValueOpportunity
from app.services.evaluation import drift_report, model_performance

router = APIRouter(tags=["health"])


@router.get("/health")
def health(db: Session = Depends(get_db)):
    s = get_settings()
    try:
        db.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception as exc:  # pragma: no cover
        db_status = f"error: {exc.__class__.__name__}"
    return {"status": "ok" if db_status == "ok" else "degraded", "app_mode": s.app_mode, "version": __version__, "database": db_status, "time_utc": datetime.now(UTC).isoformat()}


@router.get("/status")
def status(db: Session = Depends(get_db)):
    s = get_settings()
    now = datetime.now(UTC)
    return {
        "app_mode": s.app_mode,
        "demo": s.is_demo,
        "providers_configured": s.production_provider_status(),
        "fixtures": db.scalar(select(func.count(Fixture.id))),
        "results": db.scalar(select(func.count(Result.id))),
        "upcoming_fixtures": db.scalar(select(func.count(Fixture.id)).where(Fixture.kickoff_utc >= now, Fixture.status == "SCHEDULED")),
        "opportunities": db.scalar(select(func.count(ValueOpportunity.id))),
        "predictions": db.scalar(select(func.count(ModelPrediction.id))),
        "last_scan": (lambda v: v.isoformat() if v else None)(db.scalar(select(func.max(ValueOpportunity.scan_date)))),
        "scheduler_enabled": s.scheduler_enabled,
        "timezone": s.timezone,
        "disclaimer": "Statistical analysis is not a guarantee of future results.",
    }


@router.get("/data-health")
def data_health(db: Session = Depends(get_db)):
    now = datetime.now(UTC)
    last_odds = db.scalar(select(func.max(Odds.recorded_at)))
    last_fixture_update = db.scalar(select(func.max(Fixture.retrieved_at)))
    recent_requests = db.execute(select(ApiRequest.provider, func.count(ApiRequest.id), func.sum(func.cast(ApiRequest.cached, __import__("sqlalchemy").Integer)), func.count(ApiRequest.error)).where(ApiRequest.created_at >= now - timedelta(hours=24)).group_by(ApiRequest.provider)).all()
    odds_age = (now - last_odds).total_seconds() / 3600 if last_odds else None
    warnings = []
    if odds_age is None:
        warnings.append("No odds data stored")
    elif odds_age > 4:
        warnings.append(f"Odds data {odds_age:.1f} hours old")
    if last_fixture_update is None or (now - last_fixture_update).total_seconds() > 36 * 3600:
        warnings.append("Fixture data not refreshed in the last 36 hours")
    s = get_settings()
    if not s.is_demo and not any(s.production_provider_status().values()):
        warnings.append("Production data provider not configured.")
    return {
        "status": "ok" if not warnings else "warning",
        "last_odds_update": last_odds.isoformat() if last_odds else None,
        "odds_age_hours": odds_age,
        "last_fixture_update": last_fixture_update.isoformat() if last_fixture_update else None,
        "api_requests_24h": [{"provider": p, "requests": n, "cached": int(c or 0), "errors": e} for p, n, c, e in recent_requests],
        "warnings": warnings,
    }


@router.get("/model-health")
def model_health(db: Session = Depends(get_db)):
    perf = model_performance(db, 30, "dixon_coles")
    drift = drift_report(db)
    return {"status": "drift" if drift.get("drift_detected") else "ok", "last_30_days": perf, "drift": drift}
