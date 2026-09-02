"""FastAPI application entrypoint."""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app import __version__
from app.api import backtests, fixtures, health, leagues, models, odds, paper, reports, settings, teams, value
from app.api.deps import limiter
from app.config import get_settings
from app.database import SessionLocal, init_db
from app.utils.logging import configure_logging, get_logger

log = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    s = get_settings()
    configure_logging(s.log_level)
    if s.database_url.startswith("sqlite") or s.app_env == "test":
        init_db()  # PostgreSQL deployments run Alembic migrations instead
    from app.services.ingestion import seed_reference_data

    with SessionLocal() as db:
        try:
            seed_reference_data(db, s.is_demo)
        except Exception as exc:  # database may not be migrated yet
            log.warning("reference seed skipped: %s", exc)
    log.info("Football Value Analytics %s starting in %s mode", __version__, s.app_mode)
    sched = None
    if s.scheduler_in_app and s.scheduler_enabled and s.app_env != "test":
        from app.tasks.scheduler import build_scheduler

        sched = build_scheduler()
        sched.start()
        log.info("in-process scheduler started with jobs: %s", [j.id for j in sched.get_jobs()])
    yield
    if sched is not None:
        sched.shutdown(wait=False)


app = FastAPI(title="Football Value Analytics", version=__version__, lifespan=lifespan, docs_url="/api/docs", openapi_url="/api/openapi.json")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(CORSMiddleware, allow_origins=get_settings().cors_origin_list, allow_credentials=False, allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"], allow_headers=["*"])


@app.middleware("http")
async def secure_headers(request: Request, call_next):
    resp = await call_next(request)
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Referrer-Policy"] = "no-referrer"
    resp.headers["Cache-Control"] = "no-store"
    return resp


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception):
    log.exception("unhandled error on %s", request.url.path)
    return JSONResponse(status_code=500, content={"detail": "internal error", "type": exc.__class__.__name__})


for r in (health.router, fixtures.router, value.router, teams.router, leagues.router, odds.router, models.router, backtests.router, paper.router, settings.router, reports.router):
    app.include_router(r, prefix="/api")


_frontend_dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"

if _frontend_dist.is_dir():
    # Serve the built frontend (npm run build) so one origin covers UI + API.
    @app.get("/{path:path}", include_in_schema=False)
    def frontend(path: str):
        f = (_frontend_dist / path).resolve()
        if path and f.is_file() and f.is_relative_to(_frontend_dist):
            return FileResponse(f)
        return FileResponse(_frontend_dist / "index.html")  # SPA fallback for client-side routes
else:
    @app.get("/")
    def root():
        return {"name": "Football Value Analytics", "version": __version__, "docs": "/api/docs", "disclaimer": "Statistical analysis is not a guarantee of future results."}
