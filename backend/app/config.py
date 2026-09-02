"""Application configuration. All secrets come from environment variables."""
from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: Literal["development", "production", "test"] = "development"
    app_mode: Literal["demo", "production"] = "demo"
    log_level: str = "INFO"
    secret_key: str = "change-me"
    timezone: str = "Europe/London"
    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    database_url: str = "sqlite:///./data/fva.db"
    redis_url: str | None = None

    football_data_api_key: str | None = None
    api_football_key: str | None = None
    api_football_base_url: str = "https://v3.football.api-sports.io"
    football_provider: Literal["football_data", "api_football"] = "api_football"

    odds_api_key: str | None = None
    odds_provider: Literal["the_odds_api", "api_football"] = "the_odds_api"

    news_api_key: str | None = None
    weather_api_key: str | None = None
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    llm_provider: Literal["none", "anthropic", "openai"] = "none"
    llm_model: str = "claude-sonnet-5"

    scheduler_enabled: bool = True
    # Run the APScheduler inside the API process (single-container hosts such as Render).
    # Default False keeps the separate `python -m app scheduler` process model.
    scheduler_in_app: bool = False
    schedule_update_fixtures: str = "06:00"
    schedule_update_stats: str = "06:15"
    schedule_update_news: str = "06:30"
    schedule_update_odds: str = "06:45"
    schedule_run_models: str = "07:00"
    schedule_report: str = "07:05"
    odds_refresh_minutes: int = 120

    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: str | None = None
    alert_email_to: str | None = None
    telegram_bot_token: str | None = None
    telegram_chat_id: str | None = None
    discord_webhook_url: str | None = None

    http_timeout_seconds: float = 20.0
    http_max_retries: int = 3
    cache_dir: str = "./data/cache"

    @field_validator("cors_origins")
    @classmethod
    def _strip(cls, v: str) -> str:
        return v.strip()

    @field_validator("database_url")
    @classmethod
    def _psycopg_driver(cls, v: str) -> str:
        """Managed Postgres providers hand out `postgres://` / `postgresql://` URLs; SQLAlchemy needs the psycopg driver."""
        v = v.strip()
        for prefix in ("postgres://", "postgresql://"):
            if v.startswith(prefix):
                return "postgresql+psycopg://" + v[len(prefix):]
        return v

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_demo(self) -> bool:
        return self.app_mode == "demo"

    def production_provider_status(self) -> dict[str, bool]:
        """Which production providers are configured (never exposes key values)."""
        return {
            "football_data": bool(self.football_data_api_key),
            "api_football": bool(self.api_football_key),
            "the_odds_api": bool(self.odds_api_key),
            "news": bool(self.news_api_key),
            "llm": self.llm_provider != "none"
            and bool(self.anthropic_api_key if self.llm_provider == "anthropic" else self.openai_api_key),
        }


@lru_cache
def get_settings() -> Settings:
    return Settings()
