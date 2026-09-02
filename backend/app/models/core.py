from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.mixins import Sourced, Timestamped, UTCDateTime, UUIDPk


class Competition(UUIDPk, Timestamped, Sourced, Base):
    __tablename__ = "competitions"
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)  # e.g. ENG_PL
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    country: Mapped[str] = mapped_column(String(60), nullable=False)
    tier: Mapped[int] = mapped_column(Integer, default=1)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    provider_ids: Mapped[dict] = mapped_column(JSON, default=dict)  # {"api_football": 39, "football_data": "PL"}

    seasons: Mapped[list[Season]] = relationship(back_populates="competition")


class Season(UUIDPk, Timestamped, Base):
    __tablename__ = "seasons"
    __table_args__ = (UniqueConstraint("competition_id", "year", name="uq_season"),)
    competition_id: Mapped[str] = mapped_column(ForeignKey("competitions.id", ondelete="CASCADE"), index=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False)  # starting year: 2025 means 2025/26
    label: Mapped[str] = mapped_column(String(20))
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    is_current: Mapped[bool] = mapped_column(Boolean, default=False)

    competition: Mapped[Competition] = relationship(back_populates="seasons")


class Team(UUIDPk, Timestamped, Sourced, Base):
    __tablename__ = "teams"
    name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    short_name: Mapped[str | None] = mapped_column(String(40))
    country: Mapped[str | None] = mapped_column(String(60))
    competition_id: Mapped[str | None] = mapped_column(ForeignKey("competitions.id"), index=True)
    provider_ids: Mapped[dict] = mapped_column(JSON, default=dict)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)


class Player(UUIDPk, Timestamped, Sourced, Base):
    __tablename__ = "players"
    name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    team_id: Mapped[str | None] = mapped_column(ForeignKey("teams.id"), index=True)
    position: Mapped[str | None] = mapped_column(String(20))
    importance: Mapped[float | None] = mapped_column(Float)  # 0..1 importance rating
    provider_ids: Mapped[dict] = mapped_column(JSON, default=dict)


class Fixture(UUIDPk, Timestamped, Sourced, Base):
    __tablename__ = "fixtures"
    __table_args__ = (
        Index("ix_fixtures_kickoff", "kickoff_utc"),
        Index("ix_fixtures_comp_kickoff", "competition_id", "kickoff_utc"),
        UniqueConstraint("source", "source_id", name="uq_fixture_source"),
    )
    competition_id: Mapped[str] = mapped_column(ForeignKey("competitions.id"), index=True)
    season_id: Mapped[str | None] = mapped_column(ForeignKey("seasons.id"), index=True)
    home_team_id: Mapped[str] = mapped_column(ForeignKey("teams.id"), index=True)
    away_team_id: Mapped[str] = mapped_column(ForeignKey("teams.id"), index=True)
    kickoff_utc: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="SCHEDULED")  # SCHEDULED|LIVE|FINISHED|POSTPONED|CANCELLED
    matchday: Mapped[int | None] = mapped_column(Integer)
    venue: Mapped[str | None] = mapped_column(String(120))
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)

    competition: Mapped[Competition] = relationship()
    home_team: Mapped[Team] = relationship(foreign_keys=[home_team_id])
    away_team: Mapped[Team] = relationship(foreign_keys=[away_team_id])
    result: Mapped[Result | None] = relationship(back_populates="fixture", uselist=False)
    statistics: Mapped[list[FixtureStatistic]] = relationship(back_populates="fixture")


class Result(UUIDPk, Timestamped, Sourced, Base):
    __tablename__ = "results"
    fixture_id: Mapped[str] = mapped_column(ForeignKey("fixtures.id", ondelete="CASCADE"), unique=True)
    home_goals: Mapped[int] = mapped_column(Integer)
    away_goals: Mapped[int] = mapped_column(Integer)
    home_goals_ht: Mapped[int | None] = mapped_column(Integer)
    away_goals_ht: Mapped[int | None] = mapped_column(Integer)
    home_corners: Mapped[int | None] = mapped_column(Integer)
    away_corners: Mapped[int | None] = mapped_column(Integer)
    home_corners_ht: Mapped[int | None] = mapped_column(Integer)
    away_corners_ht: Mapped[int | None] = mapped_column(Integer)
    home_red_cards: Mapped[int | None] = mapped_column(Integer)
    away_red_cards: Mapped[int | None] = mapped_column(Integer)
    first_red_card_minute: Mapped[int | None] = mapped_column(Integer)
    outcome: Mapped[str | None] = mapped_column(String(1))  # H/D/A
    abnormal_flags: Mapped[dict] = mapped_column(JSON, default=dict)  # {"early_red_card": true, ...}

    fixture: Mapped[Fixture] = relationship(back_populates="result")


class FixtureStatistic(UUIDPk, Timestamped, Sourced, Base):
    """Per-team, per-fixture post-match statistics (used only for fixtures completed before the cutoff)."""

    __tablename__ = "fixture_statistics"
    __table_args__ = (UniqueConstraint("fixture_id", "team_id", name="uq_fixture_stat"),)
    fixture_id: Mapped[str] = mapped_column(ForeignKey("fixtures.id", ondelete="CASCADE"), index=True)
    team_id: Mapped[str] = mapped_column(ForeignKey("teams.id"), index=True)
    is_home: Mapped[bool] = mapped_column(Boolean)
    goals: Mapped[int | None] = mapped_column(Integer)
    xg: Mapped[float | None] = mapped_column(Float)
    shots: Mapped[int | None] = mapped_column(Integer)
    shots_on_target: Mapped[int | None] = mapped_column(Integer)
    possession: Mapped[float | None] = mapped_column(Float)
    corners: Mapped[int | None] = mapped_column(Integer)
    corners_ht: Mapped[int | None] = mapped_column(Integer)
    yellow_cards: Mapped[int | None] = mapped_column(Integer)
    red_cards: Mapped[int | None] = mapped_column(Integer)
    fouls: Mapped[int | None] = mapped_column(Integer)
    extra: Mapped[dict] = mapped_column(JSON, default=dict)

    fixture: Mapped[Fixture] = relationship(back_populates="statistics")


class TeamStatistic(UUIDPk, Timestamped, Base):
    """Aggregated team statistics computed by the platform (cache of statistics engine output)."""

    __tablename__ = "team_statistics"
    __table_args__ = (UniqueConstraint("team_id", "season_id", "as_of", name="uq_team_stat"),)
    team_id: Mapped[str] = mapped_column(ForeignKey("teams.id"), index=True)
    season_id: Mapped[str | None] = mapped_column(ForeignKey("seasons.id"), index=True)
    as_of: Mapped[datetime] = mapped_column(UTCDateTime)
    matches: Mapped[int] = mapped_column(Integer, default=0)
    stats: Mapped[dict] = mapped_column(JSON, default=dict)


class PlayerStatistic(UUIDPk, Timestamped, Sourced, Base):
    __tablename__ = "player_statistics"
    player_id: Mapped[str] = mapped_column(ForeignKey("players.id"), index=True)
    season_id: Mapped[str | None] = mapped_column(ForeignKey("seasons.id"))
    minutes: Mapped[int | None] = mapped_column(Integer)
    goals: Mapped[int | None] = mapped_column(Integer)
    assists: Mapped[int | None] = mapped_column(Integer)
    xg: Mapped[float | None] = mapped_column(Float)
    xa: Mapped[float | None] = mapped_column(Float)
    appearances: Mapped[int | None] = mapped_column(Integer)
    extra: Mapped[dict] = mapped_column(JSON, default=dict)


class Bookmaker(UUIDPk, Timestamped, Base):
    __tablename__ = "bookmakers"
    key: Mapped[str] = mapped_column(String(50), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    is_exchange: Mapped[bool] = mapped_column(Boolean, default=False)
    rules: Mapped[dict] = mapped_column(JSON, default=dict)  # void rules, push handling etc.


class Market(UUIDPk, Timestamped, Base):
    __tablename__ = "markets"
    key: Mapped[str] = mapped_column(String(60), unique=True)  # e.g. goals_over_2.5
    group: Mapped[str] = mapped_column(String(30))  # match_result | goals | corners | first_half | team_goals
    name: Mapped[str] = mapped_column(String(100))
    line: Mapped[float | None] = mapped_column(Float)
    period: Mapped[str] = mapped_column(String(10), default="FT")  # FT | 1H
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    outcomes: Mapped[list] = mapped_column(JSON, default=list)  # complete outcome set for overround calc


class Odds(UUIDPk, Timestamped, Sourced, Base):
    __tablename__ = "odds"
    __table_args__ = (
        Index("ix_odds_fixture_market", "fixture_id", "market_key", "selection"),
        Index("ix_odds_fixture_time", "fixture_id", "recorded_at"),
    )
    fixture_id: Mapped[str] = mapped_column(ForeignKey("fixtures.id", ondelete="CASCADE"), index=True)
    bookmaker_key: Mapped[str] = mapped_column(String(50), index=True)
    market_key: Mapped[str] = mapped_column(String(60))
    selection: Mapped[str] = mapped_column(String(40))  # home|draw|away|over|under|yes|no
    line: Mapped[float | None] = mapped_column(Float)
    decimal_odds: Mapped[float] = mapped_column(Float)
    recorded_at: Mapped[datetime] = mapped_column(UTCDateTime, index=True)  # first time this price was observed
    last_seen_at: Mapped[datetime | None] = mapped_column(UTCDateTime)  # last refresh confirming the same price
    is_current: Mapped[bool] = mapped_column(Boolean, default=True)
    is_closing: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(20), default="open")
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)


class Weather(UUIDPk, Timestamped, Sourced, Base):
    __tablename__ = "weather"
    fixture_id: Mapped[str] = mapped_column(ForeignKey("fixtures.id", ondelete="CASCADE"), unique=True)
    temperature_c: Mapped[float | None] = mapped_column(Float)
    rain_mm: Mapped[float | None] = mapped_column(Float)
    wind_kph: Mapped[float | None] = mapped_column(Float)
    humidity: Mapped[float | None] = mapped_column(Float)
    snow: Mapped[bool | None] = mapped_column(Boolean)


class DataQualityLog(UUIDPk, Timestamped, Base):
    __tablename__ = "data_quality_logs"
    fixture_id: Mapped[str | None] = mapped_column(ForeignKey("fixtures.id", ondelete="CASCADE"), index=True)
    component: Mapped[str] = mapped_column(String(50))
    level: Mapped[str] = mapped_column(String(10), default="warning")
    message: Mapped[str] = mapped_column(Text)
    details: Mapped[dict] = mapped_column(JSON, default=dict)


class ApiRequest(UUIDPk, Timestamped, Base):
    __tablename__ = "api_requests"
    provider: Mapped[str] = mapped_column(String(50), index=True)
    endpoint: Mapped[str] = mapped_column(String(200))
    status_code: Mapped[int | None] = mapped_column(Integer)
    duration_ms: Mapped[float | None] = mapped_column(Float)
    cached: Mapped[bool] = mapped_column(Boolean, default=False)
    error: Mapped[str | None] = mapped_column(Text)


class LeagueSetting(UUIDPk, Timestamped, Base):
    __tablename__ = "league_settings"
    competition_id: Mapped[str] = mapped_column(ForeignKey("competitions.id", ondelete="CASCADE"), unique=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    min_sample_size: Mapped[int] = mapped_column(Integer, default=6)
    reliability: Mapped[float] = mapped_column(Float, default=0.8)  # 0..1 league data/model reliability
    home_advantage: Mapped[float | None] = mapped_column(Float)
    settings: Mapped[dict] = mapped_column(JSON, default=dict)


class SystemSetting(Timestamped, Base):
    __tablename__ = "system_settings"
    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    value: Mapped[dict] = mapped_column(JSON, default=dict)
    description: Mapped[str | None] = mapped_column(Text)
