from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from app.config import get_settings


def utcnow() -> datetime:
    return datetime.now(UTC)


def local_tz() -> ZoneInfo:
    return ZoneInfo(get_settings().timezone)


def local_now() -> datetime:
    return utcnow().astimezone(local_tz())


def local_day_bounds_utc(day: date) -> tuple[datetime, datetime]:
    """Return the UTC datetimes bounding `day` in the configured local timezone."""
    tz = local_tz()
    start = datetime(day.year, day.month, day.day, tzinfo=tz)
    end = start + timedelta(days=1)
    return start.astimezone(UTC), end.astimezone(UTC)


def age_hours(ts: datetime | None) -> float | None:
    if ts is None:
        return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=UTC)
    return (utcnow() - ts).total_seconds() / 3600.0
