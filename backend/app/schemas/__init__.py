"""Pydantic request/response schemas."""
from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str
    app_mode: str
    version: str
    database: str
    time_utc: datetime


class PaperBetCreate(BaseModel):
    fixture_id: str
    market_key: str
    selection: str
    odds: float = Field(gt=1.0, le=1000)
    stake: float | None = Field(default=None, gt=0, le=1_000_000)
    bookmaker_key: str | None = None
    opportunity_id: str | None = None
    notes: str | None = Field(default=None, max_length=500)
    stake_method: str | None = None


class BacktestRequest(BaseModel):
    strategy: str = "VALUE_ONLY"
    competition_codes: list[str] | None = None
    start: datetime | None = None
    end: datetime | None = None
    min_ev: float = Field(default=0.03, ge=-1, le=1)
    min_confidence: float = Field(default=0.0, ge=0, le=100)
    min_data_quality: float = Field(default=0.0, ge=0, le=100)
    min_odds: float = Field(default=1.30, ge=1.01)
    max_odds: float = Field(default=6.0, le=1000)
    min_sample_size: int = Field(default=6, ge=0)
    stake_method: str = "flat"
    flat_stake: float = Field(default=1.0, gt=0)
    starting_bankroll: float = Field(default=100.0, gt=0)
    corner_distribution: str | None = None
    min_expected_corners: float | None = None
    min_expected_goals: float | None = None
    exclude_early_red_cards: bool = False
    one_bet_per_fixture: bool = True


class SettingsUpdate(BaseModel):
    value: dict


class ScanRequest(BaseModel):
    scan_date: date | None = None
    days_ahead: int | None = Field(default=None, ge=1, le=7)
    competition_codes: list[str] | None = None


class ManagerChangeCreate(BaseModel):
    team_id: str
    change_date: date
    manager_name: str | None = None
    previous_manager: str | None = None
