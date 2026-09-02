"""Open-Meteo forecast provider (no API key required). Docs: https://open-meteo.com/en/docs

Weather is stored as information only; it receives model weight only if backtests show it helps.
"""
from __future__ import annotations

from datetime import datetime

from app.providers.base import WeatherDataProvider, WeatherDTO
from app.providers.http import CachedHttpClient


class OpenMeteoProvider(WeatherDataProvider):
    name = "open_meteo"

    def __init__(self, session_factory=None):
        self.http = CachedHttpClient(self.name, "https://api.open-meteo.com/v1", default_ttl=3 * 3600, session_factory=session_factory)

    async def get_fixture_weather(self, fixture_source_id: str, latitude: float, longitude: float, kickoff_utc: datetime) -> WeatherDTO | None:
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "hourly": "temperature_2m,precipitation,wind_speed_10m,relative_humidity_2m,snowfall",
            "start_date": kickoff_utc.date().isoformat(),
            "end_date": kickoff_utc.date().isoformat(),
            "timezone": "UTC",
        }
        data = await self.http.get_json("forecast", params)
        hourly = data.get("hourly", {})
        times = hourly.get("time", [])
        target = kickoff_utc.strftime("%Y-%m-%dT%H:00")
        if target not in times:
            return None
        i = times.index(target)

        def pick(key):
            vals = hourly.get(key)
            return vals[i] if vals and i < len(vals) else None

        snow = pick("snowfall")
        return WeatherDTO(self.name, fixture_source_id, pick("temperature_2m"), pick("precipitation"), pick("wind_speed_10m"), pick("relative_humidity_2m"), (snow or 0) > 0 if snow is not None else None)
