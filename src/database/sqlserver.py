"""SQL Server engine and connectivity helpers."""

from __future__ import annotations

import os

from sqlalchemy import URL, create_engine, text
from sqlalchemy.engine import Engine


def create_sqlserver_engine() -> Engine:
    """Build a pooled SQL Server engine from environment variables."""
    password = os.getenv("SQLSERVER_PASSWORD")
    if not password:
        raise ValueError("SQLSERVER_PASSWORD is required")
    url = URL.create(
        "mssql+pyodbc",
        username=os.getenv("SQLSERVER_USER", "sa"),
        password=password,
        host=os.getenv("SQLSERVER_HOST", "localhost"),
        port=int(os.getenv("SQLSERVER_PORT", "1433")),
        database=os.getenv("SQLSERVER_DATABASE", "supply_chain"),
        query={
            "driver": os.getenv("SQLSERVER_DRIVER", "ODBC Driver 18 for SQL Server"),
            "Encrypt": os.getenv("SQLSERVER_ENCRYPT", "yes"),
            "TrustServerCertificate": os.getenv("SQLSERVER_TRUST_SERVER_CERTIFICATE", "yes"),
        },
    )
    return create_engine(url, pool_pre_ping=True)


def check_connection(engine: Engine | None = None) -> bool:
    """Execute a lightweight query and return True when SQL Server responds."""
    database = engine or create_sqlserver_engine()
    with database.connect() as connection:
        return connection.execute(text("SELECT 1")).scalar_one() == 1
