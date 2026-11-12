"""Clean supply-chain CSV files and optionally load them into PostgreSQL."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import MetaData, Table, inspect
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Connection, Engine

from src.data.cleaning import DATA_CONTRACTS, clean_datasets
from src.database.postgres import create_postgres_engine

FILE_NAMES = {name: f"{name}.csv" for name in DATA_CONTRACTS}
TABLE_NAMES = {"orders": "customer_orders", "inventory": "inventory_snapshots"}
LOAD_ORDER = ("suppliers", "products", "inventory", "orders", "sales", "shipments")


def read_csv_datasets(input_dir: Path | str) -> dict[str, pd.DataFrame]:
    """Read all source CSVs with Pandas while preserving raw text values."""
    root = Path(input_dir)
    frames: dict[str, pd.DataFrame] = {}
    for name, filename in FILE_NAMES.items():
        path = root / filename
        if not path.is_file():
            raise FileNotFoundError(f"Required input file not found: {path}")
        frames[name] = pd.read_csv(path, dtype="string", keep_default_na=True)
    return frames


def write_processed_datasets(frames: dict[str, pd.DataFrame], output_dir: Path | str) -> None:
    """Write cleaned CSVs and the quality report directory."""
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    for name, frame in frames.items():
        frame.to_csv(output / FILE_NAMES[name], index=False, date_format="%Y-%m-%d")


def _records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    normalized = frame.copy()
    for column in normalized.select_dtypes(include=["datetime64[ns]", "datetimetz"]).columns:
        normalized[column] = normalized[column].dt.date
    return normalized.astype(object).where(pd.notna(normalized), None).to_dict(orient="records")


def _upsert(connection: Connection, table: Table, frame: pd.DataFrame, keys: list[str]) -> int:
    records = _records(frame)
    if not records:
        return 0
    statement = insert(table).values(records)
    update_columns = {column: getattr(statement.excluded, column) for column in frame.columns if column not in keys}
    connection.execute(statement.on_conflict_do_update(index_elements=keys, set_=update_columns))
    return len(records)


def load_postgres(frames: dict[str, pd.DataFrame], engine: Engine, schema: str = "supply_chain") -> dict[str, int]:
    """Upsert cleaned frames into existing PostgreSQL tables in dependency order."""
    expected_tables = {TABLE_NAMES.get(name, name) for name in LOAD_ORDER}
    available = set(inspect(engine).get_table_names(schema=schema))
    if missing := expected_tables - available:
        raise RuntimeError(f"PostgreSQL schema {schema!r} is missing tables: {sorted(missing)}")
    metadata = MetaData()
    loaded: dict[str, int] = {}
    with engine.begin() as connection:
        for name in LOAD_ORDER:
            table_name = TABLE_NAMES.get(name, name)
            table = Table(table_name, metadata, schema=schema, autoload_with=connection)
            loaded[name] = _upsert(connection, table, frames[name], DATA_CONTRACTS[name]["keys"])
    return loaded


def run_etl(input_dir: Path | str, output_dir: Path | str, load_database: bool = False) -> dict[str, Any]:
    """Run extraction, cleaning, CSV output, and optional PostgreSQL loading."""
    frames = read_csv_datasets(input_dir)
    cleaned, quality = clean_datasets(frames)
    write_processed_datasets(cleaned, output_dir)
    result: dict[str, Any] = {"quality": quality, "database_rows": {}}
    if load_database:
        load_dotenv()
        result["database_rows"] = load_postgres(cleaned, create_postgres_engine())
    report_path = Path(output_dir) / "etl_report.json"
    report_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=Path("data/synthetic"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/processed"))
    parser.add_argument("--load-postgres", action="store_true")
    args = parser.parse_args()
    result = run_etl(args.input_dir, args.output_dir, args.load_postgres)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
