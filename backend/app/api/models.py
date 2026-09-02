from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models import ModelVersion
from app.services.evaluation import calibration_curve, drift_report, model_leaderboard, model_performance, strategy_performance_scores
from app.services.prediction import MODEL_VERSIONS

router = APIRouter(tags=["models"])


@router.get("/models")
def models(db: Session = Depends(get_db)):
    registered = [{"name": m.name, "version": m.version, "feature_version": m.feature_version, "is_active": m.is_active, "trained_at": m.trained_at, "metrics": m.metrics, "parameters": m.parameters, "notes": m.notes} for m in db.scalars(select(ModelVersion))]
    return {"active": MODEL_VERSIONS, "registry": registered, "methodology": "docs/MODELS.md"}


@router.get("/models/leaderboard")
def leaderboard(db: Session = Depends(get_db)):
    return model_leaderboard(db)


@router.get("/performance")
def performance(days: int | None = Query(30, ge=1, le=3650), model: str | None = None, market_group: str | None = None, db: Session = Depends(get_db)):
    return {"performance": model_performance(db, days, model, market_group), "drift": drift_report(db, model or "dixon_coles"), "strategy_scores": strategy_performance_scores(db), "note": "Informational; historical performance is not proof of future profitability."}


@router.get("/performance/calibration")
def calibration(model: str = "dixon_coles", market_group: str | None = None, days: int | None = None, db: Session = Depends(get_db)):
    return calibration_curve(db, model, market_group, days)
