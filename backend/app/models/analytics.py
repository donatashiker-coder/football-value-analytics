from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.mixins import Timestamped, UTCDateTime, UUIDPk


class ModelVersion(UUIDPk, Timestamped, Base):
    __tablename__ = "model_versions"
    __table_args__ = (UniqueConstraint("name", "version", name="uq_model_version"),)
    name: Mapped[str] = mapped_column(String(60), index=True)  # poisson | dixon_coles | corners_nb | ensemble
    version: Mapped[str] = mapped_column(String(30))
    feature_version: Mapped[str] = mapped_column(String(30), default="1")
    parameters: Mapped[dict] = mapped_column(JSON, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    trained_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    metrics: Mapped[dict] = mapped_column(JSON, default=dict)
    notes: Mapped[str | None] = mapped_column(Text)


class FeatureSnapshot(UUIDPk, Timestamped, Base):
    """Exact features a prediction was built from: the reproducibility record."""

    __tablename__ = "feature_snapshots"
    fixture_id: Mapped[str] = mapped_column(ForeignKey("fixtures.id", ondelete="CASCADE"), index=True)
    feature_version: Mapped[str] = mapped_column(String(30))
    data_timestamp: Mapped[datetime] = mapped_column(UTCDateTime)
    features: Mapped[dict] = mapped_column(JSON, default=dict)
    data_quality: Mapped[float] = mapped_column(Float, default=0.0)
    warnings: Mapped[list] = mapped_column(JSON, default=list)


class ModelPrediction(UUIDPk, Timestamped, Base):
    __tablename__ = "model_predictions"
    __table_args__ = (
        Index("ix_pred_fixture_market", "fixture_id", "market_key", "selection"),
        Index("ix_pred_model", "model_name", "model_version"),
    )
    fixture_id: Mapped[str] = mapped_column(ForeignKey("fixtures.id", ondelete="CASCADE"), index=True)
    feature_snapshot_id: Mapped[str | None] = mapped_column(ForeignKey("feature_snapshots.id"))
    model_name: Mapped[str] = mapped_column(String(60))
    model_version: Mapped[str] = mapped_column(String(30))
    feature_version: Mapped[str] = mapped_column(String(30), default="1")
    market_key: Mapped[str] = mapped_column(String(60))
    selection: Mapped[str] = mapped_column(String(40))
    line: Mapped[float | None] = mapped_column(Float)
    probability: Mapped[float] = mapped_column(Float)
    fair_odds: Mapped[float | None] = mapped_column(Float)
    expected_home: Mapped[float | None] = mapped_column(Float)  # expected home goals / corners
    expected_away: Mapped[float | None] = mapped_column(Float)
    data_timestamp: Mapped[datetime] = mapped_column(UTCDateTime)
    prediction_timestamp: Mapped[datetime] = mapped_column(UTCDateTime)
    # settlement (filled after result)
    settled: Mapped[bool] = mapped_column(Boolean, default=False)
    outcome: Mapped[int | None] = mapped_column(Integer)  # 1 won, 0 lost, None push/void
    best_odds_at_prediction: Mapped[float | None] = mapped_column(Float)
    closing_odds: Mapped[float | None] = mapped_column(Float)
    clv: Mapped[float | None] = mapped_column(Float)


class ValueOpportunity(UUIDPk, Timestamped, Base):
    __tablename__ = "value_opportunities"
    __table_args__ = (
        Index("ix_value_fixture", "fixture_id", "market_key", "selection"),
        Index("ix_value_score", "value_score"),
    )
    fixture_id: Mapped[str] = mapped_column(ForeignKey("fixtures.id", ondelete="CASCADE"), index=True)
    prediction_id: Mapped[str | None] = mapped_column(ForeignKey("model_predictions.id"))
    market_key: Mapped[str] = mapped_column(String(60))
    market_group: Mapped[str] = mapped_column(String(30))
    selection: Mapped[str] = mapped_column(String(40))
    line: Mapped[float | None] = mapped_column(Float)
    model_probability: Mapped[float] = mapped_column(Float)  # raw statistical model probability
    blended_probability: Mapped[float | None] = mapped_column(Float)  # model shrunk towards the market; used for EV
    market_probability: Mapped[float | None] = mapped_column(Float)  # overround-normalised
    raw_implied_probability: Mapped[float | None] = mapped_column(Float)
    best_odds: Mapped[float | None] = mapped_column(Float)
    best_bookmaker: Mapped[str | None] = mapped_column(String(50))
    median_odds: Mapped[float | None] = mapped_column(Float)
    bookmaker_count: Mapped[int] = mapped_column(Integer, default=0)
    fair_odds: Mapped[float] = mapped_column(Float)
    edge: Mapped[float | None] = mapped_column(Float)  # model_prob - market_prob
    expected_value: Mapped[float | None] = mapped_column(Float)
    value_label: Mapped[str] = mapped_column(String(20), default="IGNORE")
    confidence: Mapped[float] = mapped_column(Float, default=0.0)  # 0..100
    data_quality: Mapped[float] = mapped_column(Float, default=0.0)  # 0..100
    value_score: Mapped[float] = mapped_column(Float, default=0.0)  # 0..100
    status: Mapped[str] = mapped_column(String(30), default="NO_BET")  # VALUE_CANDIDATE | NO_BET | ODDS_UNAVAILABLE
    no_bet_reasons: Mapped[list] = mapped_column(JSON, default=list)
    key_factors: Mapped[list] = mapped_column(JSON, default=list)
    risk_factors: Mapped[list] = mapped_column(JSON, default=list)
    explanation: Mapped[str | None] = mapped_column(Text)
    llm_explanation: Mapped[str | None] = mapped_column(Text)
    model_version: Mapped[str | None] = mapped_column(String(60))
    odds_recorded_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    scan_date: Mapped[datetime] = mapped_column(UTCDateTime, index=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)

    fixture = relationship("Fixture")


class TeamRating(UUIDPk, Timestamped, Base):
    """Elo-style rating history."""

    __tablename__ = "team_ratings"
    __table_args__ = (Index("ix_rating_team_time", "team_id", "as_of"),)
    team_id: Mapped[str] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"), index=True)
    as_of: Mapped[datetime] = mapped_column(UTCDateTime)
    elo: Mapped[float] = mapped_column(Float)
    attack: Mapped[float | None] = mapped_column(Float)
    defence: Mapped[float | None] = mapped_column(Float)
    matches: Mapped[int] = mapped_column(Integer, default=0)
    model_version: Mapped[str] = mapped_column(String(30), default="elo-1")


class Backtest(UUIDPk, Timestamped, Base):
    __tablename__ = "backtests"
    strategy: Mapped[str] = mapped_column(String(40), index=True)
    name: Mapped[str] = mapped_column(String(120))
    parameters: Mapped[dict] = mapped_column(JSON, default=dict)
    start_date: Mapped[datetime | None] = mapped_column(UTCDateTime)
    end_date: Mapped[datetime | None] = mapped_column(UTCDateTime)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    summary: Mapped[dict] = mapped_column(JSON, default=dict)
    breakdowns: Mapped[dict] = mapped_column(JSON, default=dict)
    equity_curve: Mapped[list] = mapped_column(JSON, default=list)
    bets: Mapped[list] = mapped_column(JSON, default=list)
    model_version: Mapped[str | None] = mapped_column(String(60))
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)


class Bet(UUIDPk, Timestamped, Base):
    """Paper bets only. The application never places real bets."""

    __tablename__ = "bets"
    fixture_id: Mapped[str] = mapped_column(ForeignKey("fixtures.id"), index=True)
    opportunity_id: Mapped[str | None] = mapped_column(ForeignKey("value_opportunities.id"))
    market_key: Mapped[str] = mapped_column(String(60))
    selection: Mapped[str] = mapped_column(String(40))
    line: Mapped[float | None] = mapped_column(Float)
    bookmaker_key: Mapped[str | None] = mapped_column(String(50))
    odds: Mapped[float] = mapped_column(Float)
    stake: Mapped[float] = mapped_column(Float)
    stake_method: Mapped[str] = mapped_column(String(20), default="flat")
    model_probability: Mapped[float | None] = mapped_column(Float)
    expected_value: Mapped[float | None] = mapped_column(Float)
    placed_at: Mapped[datetime] = mapped_column(UTCDateTime)
    status: Mapped[str] = mapped_column(String(20), default="open")  # open|won|lost|push|void
    profit: Mapped[float | None] = mapped_column(Float)
    settled_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    closing_odds: Mapped[float | None] = mapped_column(Float)
    clv: Mapped[float | None] = mapped_column(Float)
    is_paper: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[str | None] = mapped_column(Text)


class BankrollSnapshot(UUIDPk, Timestamped, Base):
    __tablename__ = "bankroll_snapshots"
    as_of: Mapped[datetime] = mapped_column(UTCDateTime, index=True)
    starting_bankroll: Mapped[float] = mapped_column(Float)
    current_bankroll: Mapped[float] = mapped_column(Float)
    total_staked: Mapped[float] = mapped_column(Float, default=0.0)
    profit: Mapped[float] = mapped_column(Float, default=0.0)
    roi: Mapped[float | None] = mapped_column(Float)
    max_drawdown: Mapped[float | None] = mapped_column(Float)
    open_bets: Mapped[int] = mapped_column(Integer, default=0)
    settled_bets: Mapped[int] = mapped_column(Integer, default=0)
