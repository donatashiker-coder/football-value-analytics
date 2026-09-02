"""Persisted, editable system settings (value thresholds, ranking weights, form weights, staking, model params)."""
from __future__ import annotations

from dataclasses import asdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.betting.staking import StakeConfig
from app.betting.value import ValueConfig
from app.models import SystemSetting
from app.models_ml.corner_model import CornerModelParams
from app.models_ml.goal_model import GoalModelParams
from app.statistics.shrinkage import FormWeights

DEFAULTS: dict[str, tuple[dict, str]] = {
    "value": (ValueConfig().as_dict(), "EV thresholds, NO-BET gates and ranking weights"),
    "form_weights": (asdict(FormWeights()), "Recent-form window weights"),
    "goal_model": (asdict(GoalModelParams()), "Goal model parameters (Dixon-Coles rho, home advantage)"),
    "corner_model": (asdict(CornerModelParams()), "Corner model parameters (distribution, dispersion)"),
    "staking": (asdict(StakeConfig()), "Stake sizing for paper bets"),
    "bankroll": ({"starting_bankroll": 1000.0, "currency": "GBP"}, "Paper bankroll"),
    "alerts": ({"min_ev": 0.08, "min_confidence": 60, "min_data_quality": 60, "max_odds_age_hours": 6}, "Notification thresholds"),
    "scanner": ({"days_ahead": 2, "enabled_market_groups": ["match_result", "goals", "btts", "team_goals", "corners", "team_corners", "first_half", "handicap"], "exclude_early_red_cards": False, "prior_strength": 8.0}, "Daily scan options"),
}


def get_setting(db: Session, key: str) -> dict:
    row = db.get(SystemSetting, key)
    base = dict(DEFAULTS.get(key, ({}, ""))[0])
    if row is not None:
        base.update(row.value or {})
    return base


def set_setting(db: Session, key: str, value: dict) -> dict:
    row = db.get(SystemSetting, key)
    merged = get_setting(db, key)
    merged.update({k: v for k, v in value.items() if k in merged or key not in DEFAULTS})
    if row is None:
        row = SystemSetting(key=key, value=merged, description=DEFAULTS.get(key, ({}, ""))[1])
        db.add(row)
    else:
        row.value = merged
    db.commit()
    return merged


def all_settings(db: Session) -> dict[str, dict]:
    out = {k: get_setting(db, k) for k in DEFAULTS}
    for row in db.scalars(select(SystemSetting)):
        if row.key not in out:
            out[row.key] = row.value
    return out


def value_config(db: Session) -> ValueConfig:
    return ValueConfig.from_dict(get_setting(db, "value"))


def form_weights(db: Session) -> FormWeights:
    return FormWeights(**{k: float(v) for k, v in get_setting(db, "form_weights").items()})


def goal_params(db: Session) -> GoalModelParams:
    return GoalModelParams(**get_setting(db, "goal_model"))


def corner_params(db: Session) -> CornerModelParams:
    return CornerModelParams(**get_setting(db, "corner_model"))


def stake_config(db: Session) -> StakeConfig:
    return StakeConfig(**get_setting(db, "staking"))
