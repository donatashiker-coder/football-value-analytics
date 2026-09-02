"""Command-line interface: python -m app <command>."""
from __future__ import annotations

import json
from datetime import date, datetime

import typer
from rich import print as rprint

from app.config import get_settings
from app.utils.logging import configure_logging

cli = typer.Typer(help="Football Value Analytics CLI", no_args_is_help=True)


@cli.callback()
def _init():
    configure_logging(get_settings().log_level)


def _out(obj) -> None:
    rprint(json.dumps(obj, indent=2, default=str))


@cli.command()
def init_db():
    """Create tables (SQLite/dev) and seed reference data."""
    from app.database import SessionLocal
    from app.database import init_db as _init_db
    from app.services.ingestion import seed_reference_data

    _init_db()
    with SessionLocal() as db:
        seed_reference_data(db, get_settings().is_demo)
    rprint("[green]database initialised[/green]")


@cli.command()
def update_data(seasons_back: int = 2, days_ahead: int = 7, stats_limit: int | None = None):
    """Refresh fixtures, results, per-match statistics and injuries."""
    from app.tasks import jobs

    _out({"fixtures": jobs.job_update_fixtures(seasons_back, days_ahead), "statistics": jobs.job_update_statistics(stats_limit), "news": jobs.job_update_news()})


@cli.command()
def update_odds(days_ahead: int = 3):
    from app.tasks import jobs

    _out(jobs.job_update_odds(days_ahead))


@cli.command()
def scan(date_: str | None = typer.Option(None, "--date", help="YYYY-MM-DD"), days: int | None = None, league: list[str] | None = typer.Option(None, "--league"), refresh: bool = typer.Option(False, help="run data + odds refresh first")):
    """Run the model scan and value engine for a day."""
    from app.tasks import jobs

    day = date.fromisoformat(date_) if date_ else None
    if refresh:
        jobs.job_update_fixtures()
        jobs.job_update_statistics()
        jobs.job_update_news()
        jobs.job_update_odds()
    jobs.job_settle()
    _out(jobs.job_run_models(day, days, league or None))


@cli.command()
def backtest(strategy: str = "VALUE_ONLY", league: list[str] | None = typer.Option(None, "--league"), min_ev: float = 0.03, min_odds: float = 1.3, max_odds: float = 6.0, start: str | None = None, end: str | None = None, corner_distribution: str | None = None, min_expected_corners: float | None = None):
    """Run a walk-forward backtest for a strategy."""
    from app.backtesting.engine import BacktestParams, run_backtest
    from app.database import SessionLocal

    strategy = strategy.upper()
    if strategy == "CORNERS":
        strategy = "CORNERS_OVER"
    if strategy == "GOALS":
        strategy = "GOALS_OVER"
    with SessionLocal() as db:
        bt = run_backtest(db, BacktestParams(strategy=strategy, competition_codes=league or None, min_ev=min_ev, min_odds=min_odds, max_odds=max_odds, start=datetime.fromisoformat(start) if start else None, end=datetime.fromisoformat(end) if end else None, corner_distribution=corner_distribution, min_expected_corners=min_expected_corners))
        _out({"id": bt.id, "strategy": bt.strategy, "summary": bt.summary, "by_league": bt.breakdowns.get("by_league"), "by_odds_range": bt.breakdowns.get("by_odds_range")})


@cli.command()
def evaluate_model(days: int | None = 30, model: str = "dixon_coles"):
    """Settle predictions and print calibration metrics, leaderboard and drift status."""
    from app.database import SessionLocal
    from app.services.evaluation import drift_report, model_leaderboard, model_performance, settle_predictions

    with SessionLocal() as db:
        _out({"settled": settle_predictions(db), "performance": model_performance(db, days, model), "leaderboard": model_leaderboard(db), "drift": drift_report(db, model)})


@cli.command()
def generate_report(date_: str | None = typer.Option(None, "--date"), send: bool = False):
    from app.tasks import jobs

    out = jobs.job_generate_report(date.fromisoformat(date_) if date_ else None, send)
    rprint(out["text"])
    if send:
        _out(out["alerts"])


@cli.command()
def pipeline(date_: str | None = typer.Option(None, "--date")):
    """Full morning routine: refresh data, odds, settle, scan, report."""
    from app.tasks import jobs

    _out(jobs.job_full_pipeline(date.fromisoformat(date_) if date_ else None))


@cli.command()
def scheduler():
    """Run the scheduler process (blocking)."""
    from app.tasks.scheduler import run_forever

    run_forever()


@cli.command()
def check_config():
    """Validate configuration: providers, database connectivity, mode."""
    from sqlalchemy import text

    from app.database import engine

    s = get_settings()
    status = s.production_provider_status()
    ok = True
    try:
        with engine.connect() as c:
            c.execute(text("SELECT 1"))
        db_ok = True
    except Exception as exc:
        db_ok, ok = False, False
        rprint(f"[red]database error: {exc.__class__.__name__}[/red]")
    if not s.is_demo and not (status["api_football"] or status["football_data"]):
        ok = False
        rprint("[red]Production data provider not configured.[/red] Set API_FOOTBALL_KEY or FOOTBALL_DATA_API_KEY, or APP_MODE=demo.")
    if not s.is_demo and not status["the_odds_api"] and s.odds_provider == "the_odds_api":
        rprint("[yellow]Odds provider not configured: value calculations will show ODDS UNAVAILABLE.[/yellow]")
    _out({"mode": s.app_mode, "database_ok": db_ok, "providers": status, "timezone": s.timezone, "valid": ok})
    raise typer.Exit(0 if ok else 1)


if __name__ == "__main__":
    cli()
