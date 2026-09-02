from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.config import get_settings
from app.providers.leagues import LEAGUES
from app.schemas import SettingsUpdate
from app.services.settings_service import DEFAULTS, all_settings, get_setting, set_setting

router = APIRouter(tags=["settings"])


@router.get("/settings")
def read_settings(db: Session = Depends(get_db)):
    return {"settings": all_settings(db), "descriptions": {k: v[1] for k, v in DEFAULTS.items()}, "defaults": {k: v[0] for k, v in DEFAULTS.items()}}


@router.get("/settings/{key}")
def read_setting(key: str, db: Session = Depends(get_db)):
    if key not in DEFAULTS:
        raise HTTPException(404, "unknown setting group")
    return get_setting(db, key)


@router.put("/settings/{key}")
def update_setting(key: str, body: SettingsUpdate, db: Session = Depends(get_db)):
    if key not in DEFAULTS:
        raise HTTPException(404, "unknown setting group")
    # validate through the dataclasses so bad values are rejected
    try:
        if key == "value":
            from app.betting.value import ValueConfig

            ValueConfig.from_dict({**get_setting(db, key), **body.value})
        elif key == "staking":
            from app.betting.staking import StakeConfig

            cfg = StakeConfig(**{**get_setting(db, key), **body.value})
            if cfg.method not in ("flat", "percentage", "quarter_kelly", "half_kelly", "full_kelly"):
                raise ValueError("unknown stake method")
            if not 0 < cfg.max_stake_fraction <= 0.10:
                raise ValueError("max_stake_fraction must be between 0 and 0.10")
        elif key == "goal_model":
            from app.models_ml.goal_model import GoalModelParams

            GoalModelParams(**{**get_setting(db, key), **body.value})
        elif key == "corner_model":
            from app.models_ml.corner_model import CornerModelParams

            c = CornerModelParams(**{**get_setting(db, key), **body.value})
            if c.distribution not in ("poisson", "negative_binomial"):
                raise ValueError("distribution must be poisson or negative_binomial")
        elif key == "form_weights":
            from app.statistics.shrinkage import FormWeights

            FormWeights(**{**get_setting(db, key), **body.value})
    except (TypeError, ValueError) as exc:
        raise HTTPException(400, f"invalid settings: {exc}") from exc
    return set_setting(db, key, body.value)


@router.get("/data-sources")
def data_sources():
    s = get_settings()
    status = s.production_provider_status()
    return {
        "mode": s.app_mode,
        "message": None if s.is_demo or any(status.values()) else "Production data provider not configured.",
        "providers": [
            {"key": "demo", "name": "Demo (synthetic)", "role": "football+odds+injuries", "configured": s.is_demo, "active": s.is_demo, "fields": ["fixtures", "results", "half-time", "corners", "xG", "shots", "cards", "odds", "injuries"], "notes": "Clearly labelled synthetic data; never mixed with production data."},
            {"key": "api_football", "name": "API-Football (api-sports.io)", "role": "football+injuries(+odds)", "configured": status["api_football"], "active": not s.is_demo and status["api_football"] and s.football_provider == "api_football", "fields": ["fixtures", "results", "half-time", "corners", "shots", "shots on target", "possession", "cards", "xG (selected leagues)", "injuries", "players", "odds incl. corners"], "notes": "Per-fixture statistics, injuries and odds require a paid plan."},
            {"key": "football_data", "name": "football-data.org", "role": "football (fallback)", "configured": status["football_data"], "active": not s.is_demo and not status["api_football"] and status["football_data"], "fields": ["fixtures", "results", "half-time"], "notes": "Free tier: 12 competitions, 10 req/min. No corners, xG, shots, injuries or odds."},
            {"key": "the_odds_api", "name": "The Odds API", "role": "odds", "configured": status["the_odds_api"], "active": not s.is_demo and status["the_odds_api"] and s.odds_provider == "the_odds_api", "fields": ["1X2", "totals", "BTTS", "team totals", "spreads", "1H totals"], "notes": "No corner markets. Free tier 500 credits/month."},
            {"key": "open_meteo", "name": "Open-Meteo", "role": "weather", "configured": True, "active": not s.is_demo, "fields": ["temperature", "rain", "wind", "humidity", "snow"], "notes": "No key required. Informational only."},
            {"key": "llm", "name": f"LLM explanations ({s.llm_provider})", "role": "explanation", "configured": status["llm"], "active": status["llm"], "fields": ["natural-language explanation of stored numbers"], "notes": "Cannot change probabilities or odds."},
        ],
        "leagues": [{"code": lg.code, "name": lg.name, "country": lg.country, "api_football": lg.api_football, "football_data": lg.football_data, "the_odds_api": lg.the_odds_api} for lg in LEAGUES],
    }
