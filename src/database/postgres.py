"""PostgreSQL engine and connectivity helpers."""

from __future__ import annotations

import os

from sqlalchemy import URL, create_engine, text
from sqlalchemy.engine import Engine


def create_postgres_engine() -> Engine:
    """Build a pooled PostgreSQL engine from environment variables."""
    password = os.getenv("POSTGRES_PASSWORD")
    if not password:
        raise ValueError("POSTGRES_PASSWORD is required")
    url = URL.create(
        "postgresql+psycopg",
        username=os.getenv("POSTGRES_USER", "supply_chain"),
        password=password,
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        database=os.getenv("POSTGRES_DB", "supply_chain"),
        query={"sslmode": os.getenv("POSTGRES_SSLMODE", "prefer")},
    )
    return create_engine(url, pool_pre_ping=True)


def check_connection(engine: Engine | None = None) -> bool:
    """Execute a lightweight query and return True when PostgreSQL responds."""
    database = engine or create_postgres_engine()
    with database.connect() as connection:
        return connection.execute(text("SELECT 1")).scalar_one() == 1
