"""APScheduler-based daily automation. Times are configurable and interpreted in the configured timezone
(Europe/London by default), so daylight saving is handled by the zoneinfo database."""
from __future__ import annotations

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.config import get_settings
from app.tasks import jobs
from app.utils.logging import get_logger
from app.utils.time import local_tz

log = get_logger(__name__)


def _hm(text: str) -> tuple[int, int]:
    h, m = text.split(":")
    return int(h), int(m)


def build_scheduler() -> BackgroundScheduler:
    s = get_settings()
    tz = local_tz()
    sched = BackgroundScheduler(timezone=tz, job_defaults={"coalesce": True, "max_instances": 1, "misfire_grace_time": 3600})
    for name, when, fn in (
        ("update_fixtures", s.schedule_update_fixtures, jobs.job_update_fixtures),
        ("update_statistics", s.schedule_update_stats, jobs.job_update_statistics),
        ("update_news", s.schedule_update_news, jobs.job_update_news),
        ("update_odds", s.schedule_update_odds, jobs.job_update_odds),
        ("run_models", s.schedule_run_models, lambda: (jobs.job_settle(), jobs.job_run_models())),
        ("daily_report", s.schedule_report, jobs.job_generate_report),
    ):
        h, m = _hm(when)
        sched.add_job(fn, CronTrigger(hour=h, minute=m, timezone=tz), id=name, name=name, replace_existing=True)
    # periodic odds refresh + rescan (pre-match refresh); final refresh is the last interval before kickoff
    sched.add_job(lambda: (jobs.job_update_odds(), jobs.job_run_models()), IntervalTrigger(minutes=max(s.odds_refresh_minutes, 15), timezone=tz), id="odds_refresh", name="odds_refresh", replace_existing=True)
    sched.add_job(jobs.job_settle, IntervalTrigger(hours=3, timezone=tz), id="settle", name="settle", replace_existing=True)
    return sched


def run_forever() -> None:  # pragma: no cover - process entrypoint
    import time

    sched = build_scheduler()
    sched.start()
    log.info("scheduler started with jobs: %s", [j.id for j in sched.get_jobs()])
    try:
        while True:
            time.sleep(60)
    except (KeyboardInterrupt, SystemExit):
        sched.shutdown()
