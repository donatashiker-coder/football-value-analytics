"""Copy every table from a SQLite database into an (already migrated) PostgreSQL database.

Usage (from backend/, with the venv active):
    python ../scripts/copy_sqlite_to_postgres.py sqlite:///./data/fva_prod.db "postgresql://user:pass@host/db?sslmode=require"

Run `alembic upgrade head` against the target first. Tables are copied in foreign-key order, existing
target rows are deleted first, and PostgreSQL identity sequences are re-synced afterwards.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from sqlalchemy import create_engine, func, select, text  # noqa: E402

import app.models  # noqa: E402,F401  (registers tables)
from app.config import Settings  # noqa: E402
from app.database import Base  # noqa: E402

BATCH = 1000


def main(src_url: str, dst_url: str) -> None:
    dst_url = Settings.model_validate({"database_url": dst_url}).database_url  # normalise driver prefix
    src = create_engine(src_url)
    dst = create_engine(dst_url)
    tables = [t for t in Base.metadata.sorted_tables if t.name != "alembic_version"]
    with src.connect() as s, dst.begin() as d:
        for t in reversed(tables):
            d.execute(t.delete())
        for t in tables:
            rows = [dict(r._mapping) for r in s.execute(select(t))]
            for i in range(0, len(rows), BATCH):
                d.execute(t.insert(), rows[i : i + BATCH])
            print(f"{t.name}: {len(rows)} rows")
        if dst.dialect.name == "postgresql":
            for t in tables:
                for col in t.primary_key.columns:
                    if col.autoincrement is True or (col.autoincrement == "auto" and col.type.python_type is int and len(t.primary_key.columns) == 1):
                        seq = d.execute(text("SELECT pg_get_serial_sequence(:t, :c)"), {"t": t.name, "c": col.name}).scalar()
                        if seq:
                            max_id = d.execute(select(func.coalesce(func.max(col), 0))).scalar()
                            d.execute(text("SELECT setval(:s, :v, :called)"), {"s": seq, "v": max(max_id, 1), "called": max_id > 0})
    print("done")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
