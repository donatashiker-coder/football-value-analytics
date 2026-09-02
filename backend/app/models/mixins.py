from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, Float, String, TypeDecorator, func
from sqlalchemy.orm import Mapped, mapped_column


class UTCDateTime(TypeDecorator):
    """Timezone-aware UTC datetime on every backend (SQLite drops tzinfo; this restores it)."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def new_uuid() -> str:
    return str(uuid.uuid4())


class UUIDPk:
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)


class Timestamped:
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )


class Sourced:
    """Provenance for every externally-sourced record."""

    source: Mapped[str] = mapped_column(String(50), nullable=False, default="unknown")
    source_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    retrieved_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    last_updated_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    data_quality: Mapped[float | None] = mapped_column(Float, nullable=True)  # 0..1 confidence in this record
