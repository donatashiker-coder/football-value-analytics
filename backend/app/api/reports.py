from __future__ import annotations

from datetime import date

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.config import get_settings
from app.llm.explain import explanation_payload, generate_explanation
from app.models import FeatureSnapshot, ValueOpportunity
from app.reporting.daily import _opp_dict, build_daily_report, format_text_report
from app.schemas import ScanRequest
from app.tasks import jobs

router = APIRouter(tags=["reports"])


@router.get("/reports/daily")
def daily_report(day: date | None = None, db: Session = Depends(get_db)):
    return build_daily_report(db, day)


@router.get("/reports/daily/text", response_class=PlainTextResponse)
def daily_report_text(day: date | None = None, db: Session = Depends(get_db)):
    return format_text_report(build_daily_report(db, day))


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db)):
    from app.api.fixtures import fixtures_today

    rep = build_daily_report(db)
    today = fixtures_today(day=None, days=rep["window_days"], competition=None, db=db)
    top = rep["top_value"]
    return {
        "date": rep["date"], "is_demo": rep["is_demo"], "fixtures_today": today["count"], "fixtures_analysed": rep["fixtures_analysed"], "value_candidates": rep["value_candidates"], "markets_evaluated": rep["markets_evaluated"],
        "top_opportunities": top[:10],
        "highest_ev": max(top, key=lambda o: o["expected_value"] or -1, default=None),
        "highest_confidence": max(top, key=lambda o: o["confidence"], default=None),
        "best_corners": rep["top_corners"][:3], "best_goals": rep["top_goals"][:3], "best_low_scoring": rep["top_low_scoring"][:3], "best_btts": rep["top_btts"][:3],
        "model_performance": rep["model_performance_30d"], "paper_betting": rep["paper_betting"], "data_quality_warnings": len(rep["data_quality_warnings"]), "stale_odds": rep["stale_odds"], "disclaimer": rep["disclaimer"],
    }


@router.post("/scan")
def trigger_scan(body: ScanRequest, background: BackgroundTasks):
    """Run the model scan (synchronously for small windows). Data refresh jobs are separate."""
    return jobs.job_run_models(body.scan_date, body.days_ahead, body.competition_codes)


@router.post("/jobs/{name}")
def trigger_job(name: str):
    fn = {"update-fixtures": jobs.job_update_fixtures, "update-statistics": jobs.job_update_statistics, "update-news": jobs.job_update_news, "update-odds": jobs.job_update_odds, "settle": jobs.job_settle, "report": jobs.job_generate_report, "pipeline": jobs.job_full_pipeline}.get(name)
    if fn is None:
        raise HTTPException(404, "unknown job")
    out = fn()
    if isinstance(out, dict) and "text" in out:
        out = {k: v for k, v in out.items() if k != "text"}
    return out


@router.post("/opportunities/{opportunity_id}/explain")
async def explain_opportunity(opportunity_id: str, db: Session = Depends(get_db)):
    o = db.get(ValueOpportunity, opportunity_id)
    if o is None:
        raise HTTPException(404, "opportunity not found")
    s = get_settings()
    if not s.production_provider_status()["llm"]:
        return {"llm_available": False, "explanation": o.explanation, "note": "LLM provider not configured; showing deterministic explanation."}
    snap = db.scalar(select(FeatureSnapshot).where(FeatureSnapshot.fixture_id == o.fixture_id).order_by(FeatureSnapshot.created_at.desc()))
    text = await generate_explanation(explanation_payload(_opp_dict(db, o), snap.features if snap else None))
    if text:
        o.llm_explanation = text
        db.commit()
    return {"llm_available": True, "explanation": text or o.explanation, "generated": text is not None}
