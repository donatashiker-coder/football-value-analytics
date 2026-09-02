"""Job functions shared by the scheduler, CLI and API."""
from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime

from app.betting.paper import settle_open_bets
from app.config import get_settings
from app.database import SessionLocal
from app.notifications.alerts import eligible_alerts, format_alert, send_alerts
from app.providers.factory import build_providers
from app.reporting.daily import _opp_dict, build_daily_report, format_text_report, opportunities_for_day
from app.services import ingestion
from app.services.evaluation import settle_predictions
from app.services.scan import run_scan
from app.utils.logging import get_logger

log = get_logger(__name__)


def _run(coro):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop and loop.is_running():
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(1) as ex:
            return ex.submit(asyncio.run, coro).result()
    return asyncio.run(coro)


def job_update_fixtures(seasons_back: int = 2, days_ahead: int = 7) -> dict:
    s = get_settings()
    with SessionLocal() as db:
        ingestion.seed_reference_data(db, s.is_demo)
        providers = build_providers(s, SessionLocal)
        out = _run(ingestion.update_fixtures_and_results(db, providers, seasons_back, days_ahead))
        log.info("fixtures updated: %s", out)
        return out


def job_update_statistics(limit: int | None = None) -> dict:
    s = get_settings()
    with SessionLocal() as db:
        providers = build_providers(s, SessionLocal)
        out = _run(ingestion.update_fixture_statistics(db, providers, limit))
        log.info("statistics updated: %s", out)
        return out


def job_update_news() -> dict:
    s = get_settings()
    with SessionLocal() as db:
        providers = build_providers(s, SessionLocal)
        out = _run(ingestion.update_injuries(db, providers))
        log.info("injuries updated: %s", out)
        return out


def job_update_odds(days_ahead: int = 3) -> dict:
    s = get_settings()
    with SessionLocal() as db:
        providers = build_providers(s, SessionLocal)
        out = _run(ingestion.update_odds(db, providers, days_ahead))
        log.info("odds updated: %s", out)
        return out


def job_run_models(scan_day: date | None = None, days_ahead: int | None = None, competitions: list[str] | None = None) -> dict:
    s = get_settings()
    with SessionLocal() as db:
        out = run_scan(db, scan_day, days_ahead, competitions, is_demo=s.is_demo)
        log.info("scan complete: %s", out)
        return out


def job_settle() -> dict:
    with SessionLocal() as db:
        a = settle_predictions(db)
        b = settle_open_bets(db)
        return {"predictions": a, "paper_bets": b}


def job_generate_report(day: date | None = None, send: bool = True) -> dict:
    with SessionLocal() as db:
        rep = build_daily_report(db, day)
        text = format_text_report(rep)
        log.info("daily report generated for %s (%d value candidates)", rep["date"], rep["value_candidates"])
        alerts = {}
        if send:
            opps = [_opp_dict(db, o) for o in opportunities_for_day(db, date.fromisoformat(rep["date"]))]
            msgs = [format_alert(o) for o in eligible_alerts(db, opps)]
            alerts = _run(send_alerts(msgs))
        return {"report": rep, "text": text, "alerts": alerts}


def job_full_pipeline(scan_day: date | None = None) -> dict:
    """The complete morning routine in order."""
    out = {"started": datetime.now(UTC).isoformat()}
    out["fixtures"] = job_update_fixtures()
    out["statistics"] = job_update_statistics()
    out["news"] = job_update_news()
    out["odds"] = job_update_odds()
    out["settled"] = job_settle()
    out["scan"] = job_run_models(scan_day)
    out["report"] = {k: v for k, v in job_generate_report(scan_day).items() if k != "text"}
    return out
