from __future__ import annotations

from collections.abc import Generator

from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session

from app.database import SessionLocal

limiter = Limiter(key_func=get_remote_address, default_limits=["600/minute"])


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def client_ip(request: Request) -> str:
    return get_remote_address(request)
