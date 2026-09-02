from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import JSON, Boolean, Date, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.mixins import Sourced, Timestamped, UTCDateTime, UUIDPk


class Injury(UUIDPk, Timestamped, Sourced, Base):
    __tablename__ = "injuries"
    team_id: Mapped[str] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"), index=True)
    player_id: Mapped[str | None] = mapped_column(ForeignKey("players.id"))
    player_name: Mapped[str] = mapped_column(String(120))
    reason: Mapped[str | None] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(30), default="out")  # out | doubtful | questionable
    reported_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    expected_return: Mapped[date | None] = mapped_column(Date)
    fixture_id: Mapped[str | None] = mapped_column(ForeignKey("fixtures.id"), index=True)
    player_importance: Mapped[float | None] = mapped_column(Float)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Suspension(UUIDPk, Timestamped, Sourced, Base):
    __tablename__ = "suspensions"
    team_id: Mapped[str] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"), index=True)
    player_id: Mapped[str | None] = mapped_column(ForeignKey("players.id"))
    player_name: Mapped[str] = mapped_column(String(120))
    reason: Mapped[str | None] = mapped_column(String(120))
    fixture_id: Mapped[str | None] = mapped_column(ForeignKey("fixtures.id"), index=True)
    player_importance: Mapped[float | None] = mapped_column(Float)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Transfer(UUIDPk, Timestamped, Sourced, Base):
    __tablename__ = "transfers"
    player_id: Mapped[str | None] = mapped_column(ForeignKey("players.id"))
    player_name: Mapped[str] = mapped_column(String(120))
    from_team_id: Mapped[str | None] = mapped_column(ForeignKey("teams.id"), index=True)
    to_team_id: Mapped[str | None] = mapped_column(ForeignKey("teams.id"), index=True)
    transfer_date: Mapped[date | None] = mapped_column(Date)
    transfer_type: Mapped[str | None] = mapped_column(String(30))
    player_importance: Mapped[float | None] = mapped_column(Float)
    impact_estimate: Mapped[dict] = mapped_column(JSON, default=dict)


class ManagerChange(UUIDPk, Timestamped, Sourced, Base):
    __tablename__ = "manager_changes"
    team_id: Mapped[str] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"), index=True)
    manager_name: Mapped[str | None] = mapped_column(String(120))
    previous_manager: Mapped[str | None] = mapped_column(String(120))
    change_date: Mapped[date] = mapped_column(Date)
    before_stats: Mapped[dict] = mapped_column(JSON, default=dict)
    after_stats: Mapped[dict] = mapped_column(JSON, default=dict)
    notes: Mapped[str | None] = mapped_column(Text)
