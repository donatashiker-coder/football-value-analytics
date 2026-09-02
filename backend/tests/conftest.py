from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

TEST_DB = ROOT / "data" / "test_fva.db"
os.environ["APP_ENV"] = "test"
os.environ["APP_MODE"] = "demo"
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB.as_posix()}"
os.environ["SCHEDULER_ENABLED"] = "false"
os.environ["CACHE_DIR"] = str(ROOT / "data" / "test_cache")


@pytest.fixture(scope="session")
def db_session_factory():
    if TEST_DB.exists():
        TEST_DB.unlink()
    from app.database import SessionLocal, init_db

    init_db()
    return SessionLocal


@pytest.fixture(scope="session")
def demo_db(db_session_factory):
    """Database populated with demo fixtures/results/stats/odds via the real ingestion path."""
    import asyncio

    from app.config import get_settings
    from app.providers.factory import build_providers
    from app.services import ingestion

    s = get_settings()
    providers = build_providers(s)
    with db_session_factory() as db:
        ingestion.seed_reference_data(db, True)
        asyncio.run(ingestion.update_fixtures_and_results(db, providers, seasons_back=2, days_ahead=7))
        asyncio.run(ingestion.update_fixture_statistics(db, providers, limit=None))
        asyncio.run(ingestion.update_odds(db, providers, days_ahead=7, include_historical=False))
        asyncio.run(ingestion.update_historical_odds(db, providers, limit=400))
        asyncio.run(ingestion.update_injuries(db, providers, days_ahead=7))
    return db_session_factory


@pytest.fixture
def db(demo_db):
    s = demo_db()
    try:
        yield s
    finally:
        s.close()


@pytest.fixture(scope="session")
def client(demo_db):
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:
        yield c
