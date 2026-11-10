"""Load and validate supply-chain CSV datasets."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable

DATASET_FILES = {name: f"{name}.csv" for name in ("products", "suppliers", "inventory", "orders", "sales", "shipments")}
REQUIRED_COLUMNS = {
    "products": {"product_id", "sku", "product_name", "category", "unit_cost", "unit_price"},
    "suppliers": {"supplier_id", "supplier_name", "country", "lead_time_days", "reliability_score"},
    "inventory": {"snapshot_date", "product_id", "warehouse_id", "quantity_on_hand", "reorder_point"},
    "orders": {"order_id", "order_date", "customer_id", "product_id", "quantity", "unit_price", "status"},
    "sales": {"sale_id", "order_id", "sale_date", "product_id", "quantity", "revenue"},
    "shipments": {"shipment_id", "supplier_id", "product_id", "order_date", "expected_date", "arrival_date", "quantity", "status"},
}


class DatasetValidationError(ValueError):
    """Raised when collected files do not satisfy the data contract."""


def read_csv(path: Path) -> list[dict[str, str]]:
    """Read a UTF-8 CSV file."""
    if not path.is_file():
        raise DatasetValidationError(f"Missing dataset: {path}")
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _values(rows: Iterable[dict[str, str]], field: str) -> set[str]:
    return {row[field] for row in rows}


def load_datasets(data_dir: Path | str) -> dict[str, list[dict[str, str]]]:
    """Load every required dataset from a directory and validate it."""
    root = Path(data_dir)
    datasets = {name: read_csv(root / filename) for name, filename in DATASET_FILES.items()}
    validate_datasets(datasets)
    return datasets


def validate_datasets(datasets: dict[str, list[dict[str, str]]]) -> None:
    """Validate required columns, primary keys, and foreign keys."""
    errors: list[str] = []
    for name, columns in REQUIRED_COLUMNS.items():
        rows = datasets.get(name, [])
        if not rows:
            errors.append(f"{name}: dataset is empty")
        elif missing := columns - set(rows[0]):
            errors.append(f"{name}: missing columns {sorted(missing)}")
    if errors:
        raise DatasetValidationError("; ".join(errors))

    for name, key in {"products": "product_id", "suppliers": "supplier_id", "orders": "order_id", "sales": "sale_id", "shipments": "shipment_id"}.items():
        values = [row[key] for row in datasets[name]]
        if len(values) != len(set(values)):
            errors.append(f"{name}: duplicate {key}")

    products = _values(datasets["products"], "product_id")
    suppliers = _values(datasets["suppliers"], "supplier_id")
    orders = _values(datasets["orders"], "order_id")
    relationships = [
        ("inventory", "product_id", products), ("orders", "product_id", products),
        ("sales", "product_id", products), ("sales", "order_id", orders),
        ("shipments", "product_id", products), ("shipments", "supplier_id", suppliers),
    ]
    for name, field, accepted in relationships:
        if invalid := _values(datasets[name], field) - accepted:
            errors.append(f"{name}: invalid {field} values {sorted(invalid)[:5]}")
    if errors:
        raise DatasetValidationError("; ".join(errors))
