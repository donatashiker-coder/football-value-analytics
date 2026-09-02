"""Resilient, cached HTTP client shared by all providers.

- timeouts, bounded retries with exponential backoff (tenacity)
- rate-limit (429) awareness via Retry-After
- on-disk JSON response cache keyed by URL+params with TTL (request deduplication / cost control)
- every call is logged to `api_requests` when a session factory is supplied
- API keys are only ever sent as headers/params and never logged
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import time
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.config import get_settings
from app.providers.base import ProviderUnavailable
from app.utils.logging import get_logger

log = get_logger(__name__)


class RateLimited(Exception):
    def __init__(self, retry_after: float):
        self.retry_after = retry_after


class CachedHttpClient:
    def __init__(self, provider: str, base_url: str, headers: dict[str, str] | None = None, default_ttl: int = 3600, session_factory: Callable | None = None, quota_headers: tuple[str, str] | None = None):
        """`quota_headers` = (remaining-header, used-header): when the provider reports its quota in response
        headers, the latest values are persisted (see settings_service.record_provider_quota)."""
        s = get_settings()
        self.provider = provider
        self.base_url = base_url.rstrip("/")
        self.headers = headers or {}
        self.default_ttl = default_ttl
        self.cache_dir = os.path.join(s.cache_dir, provider)
        os.makedirs(self.cache_dir, exist_ok=True)
        self.timeout = s.http_timeout_seconds
        self.max_retries = s.http_max_retries
        self.session_factory = session_factory
        self.quota_headers = quota_headers
        self.transport: httpx.AsyncBaseTransport | None = None  # tests inject httpx.MockTransport
        self._sem = asyncio.Semaphore(4)

    # ---- cache -------------------------------------------------------
    def _cache_path(self, path: str, params: dict | None) -> str:
        key = hashlib.sha256(f"{path}|{json.dumps(params or {}, sort_keys=True)}".encode()).hexdigest()
        return os.path.join(self.cache_dir, f"{key}.json")

    def _read_cache(self, path: str, params: dict | None, ttl: int) -> Any | None:
        fp = self._cache_path(path, params)
        if not os.path.exists(fp):
            return None
        if time.time() - os.path.getmtime(fp) > ttl:
            return None
        try:
            with open(fp, encoding="utf-8") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            return None

    def _write_cache(self, path: str, params: dict | None, data: Any) -> None:
        try:
            with open(self._cache_path(path, params), "w", encoding="utf-8") as f:
                json.dump(data, f)
        except OSError:  # pragma: no cover
            log.warning("cache write failed for %s", path)

    # ---- logging -----------------------------------------------------
    def _log_request(self, endpoint: str, status: int | None, duration_ms: float, cached: bool, error: str | None = None) -> None:
        if self.session_factory is None:
            return
        try:
            from app.models import ApiRequest

            with self.session_factory() as db:
                db.add(ApiRequest(provider=self.provider, endpoint=endpoint[:200], status_code=status, duration_ms=duration_ms, cached=cached, error=error))
                db.commit()
        except Exception as exc:  # pragma: no cover - logging must never break a request
            log.debug("api request log failed: %s", exc)

    def _record_quota(self, headers: httpx.Headers) -> None:
        if self.quota_headers is None or self.session_factory is None:
            return
        remaining_h, used_h = self.quota_headers
        if remaining_h not in headers and used_h not in headers:
            return

        def _int(name: str) -> int | None:
            try:
                return int(float(headers[name])) if name in headers else None
            except ValueError:
                return None

        try:
            from app.services.settings_service import record_provider_quota

            with self.session_factory() as db:
                record_provider_quota(db, self.provider, _int(remaining_h), _int(used_h))
        except Exception as exc:  # pragma: no cover - bookkeeping must never break a request
            log.debug("quota record failed: %s", exc)

    # ---- request -----------------------------------------------------
    async def get_json(self, path: str, params: dict | None = None, ttl: int | None = None, use_cache: bool = True) -> Any:
        ttl = self.default_ttl if ttl is None else ttl
        if use_cache and ttl > 0:
            cached = self._read_cache(path, params, ttl)
            if cached is not None:
                self._log_request(path, 200, 0.0, True)
                return cached
        try:
            data = await self._get_with_retry(path, params)
        except RateLimited as exc:
            self._log_request(path, 429, 0.0, False, "rate limited")
            raise ProviderUnavailable(f"{self.provider} rate limited; retry after {exc.retry_after}s") from exc
        except (httpx.HTTPError, httpx.InvalidURL) as exc:
            self._log_request(path, None, 0.0, False, str(exc)[:200])
            raise ProviderUnavailable(f"{self.provider}: {exc}") from exc
        if use_cache and ttl > 0:
            self._write_cache(path, params, data)
        return data

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=20),
        retry=retry_if_exception_type((httpx.TransportError, RateLimited)),
        reraise=True,
    )
    async def _get_with_retry(self, path: str, params: dict | None) -> Any:
        url = f"{self.base_url}/{path.lstrip('/')}"
        started = time.perf_counter()
        async with self._sem, httpx.AsyncClient(timeout=self.timeout, headers=self.headers, transport=self.transport) as client:
            resp = await client.get(url, params=params)
        duration = (time.perf_counter() - started) * 1000
        self._record_quota(resp.headers)
        if resp.status_code == 429:
            retry_after = float(resp.headers.get("Retry-After", "5") or 5)
            log.warning("%s rate limited on %s (retry after %.0fs)", self.provider, path, retry_after)
            await asyncio.sleep(min(retry_after, 30))
            raise RateLimited(retry_after)
        self._log_request(path, resp.status_code, duration, False, None if resp.is_success else resp.text[:200])
        if resp.status_code >= 500:
            raise httpx.TransportError(f"server error {resp.status_code}")
        resp.raise_for_status()
        return resp.json()


def utc_now() -> datetime:
    return datetime.now(UTC)
