"""Pandas cleaning rules for supply-chain datasets."""

from __future__ import annotations

from typing import Any

import pandas as pd


class DataCleaningError(ValueError):
    """Raised when input data cannot satisfy the cleaning contract."""


DATA_CONTRACTS: dict[str, dict[str, Any]] = {
    "suppliers": {
        "required": ["supplier_id", "supplier_name", "country", "lead_time_days", "reliability_score"],
        "keys": ["supplier_id"], "ids": ["supplier_id"],
        "integers": ["lead_time_days"], "numbers": ["reliability_score"],
    },
    "products": {
        "required": ["product_id", "sku", "product_name", "category", "supplier_id", "unit_cost", "unit_price"],
        "keys": ["product_id"], "ids": ["product_id", "sku", "supplier_id"],
        "numbers": ["unit_cost", "unit_price"],
    },
    "inventory": {
        "required": ["snapshot_date", "product_id", "warehouse_id", "quantity_on_hand", "reorder_point", "safety_stock"],
        "keys": ["snapshot_date", "product_id", "warehouse_id"], "ids": ["product_id", "warehouse_id"],
        "dates": ["snapshot_date"],
        "integers": ["quantity_on_hand", "quantity_reserved", "reorder_point", "safety_stock"],
        "defaults": {"quantity_reserved": 0},
    },
    "orders": {
        "required": ["order_id", "order_date", "customer_id", "product_id", "quantity", "unit_price", "status"],
        "keys": ["order_id"], "ids": ["order_id", "customer_id", "product_id"],
        "dates": ["order_date"], "integers": ["quantity"], "numbers": ["unit_price"],
        "categories": {"status": {"completed", "cancelled", "returned"}},
    },
    "sales": {
        "required": ["sale_id", "order_id", "sale_date", "product_id", "quantity", "revenue"],
        "keys": ["sale_id"], "ids": ["sale_id", "order_id", "product_id"],
        "dates": ["sale_date"], "integers": ["quantity"], "numbers": ["revenue"],
    },
    "shipments": {
        "required": ["shipment_id", "supplier_id", "product_id", "order_date", "expected_date", "quantity", "status"],
        "keys": ["shipment_id"], "ids": ["shipment_id", "supplier_id", "product_id"],
        "dates": ["order_date", "expected_date", "arrival_date"], "integers": ["quantity"],
        "categories": {"status": {"delivered", "in_transit", "delayed"}},
    },
}


def clean_dataset(name: str, frame: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, int]]:
    """Standardize one dataset and report rows removed during cleaning."""
    if name not in DATA_CONTRACTS:
        raise DataCleaningError(f"Unknown dataset: {name}")
    contract = DATA_CONTRACTS[name]
    cleaned = frame.copy()
    cleaned.columns = cleaned.columns.str.strip().str.lower()
    missing_columns = set(contract["required"]) - set(cleaned.columns)
    if missing_columns:
        raise DataCleaningError(f"{name}: missing columns {sorted(missing_columns)}")

    before = len(cleaned)
    cleaned = cleaned.replace(r"^\s*$", pd.NA, regex=True)
    for column, default in contract.get("defaults", {}).items():
        if column not in cleaned:
            cleaned[column] = default
        else:
            cleaned[column] = cleaned[column].fillna(default)
    for column in contract.get("ids", []):
        cleaned[column] = cleaned[column].astype("string").str.strip().str.upper()
    for column in cleaned.select_dtypes(include=["object", "string"]).columns:
        cleaned[column] = cleaned[column].astype("string").str.strip()
    for column in contract.get("dates", []):
        if column not in cleaned:
            cleaned[column] = pd.NaT
        cleaned[column] = pd.to_datetime(cleaned[column], format="mixed", errors="coerce").dt.normalize()
    for column in contract.get("integers", []):
        cleaned[column] = pd.to_numeric(cleaned[column], errors="coerce").astype("Int64")
    for column in contract.get("numbers", []):
        cleaned[column] = pd.to_numeric(cleaned[column], errors="coerce").astype("Float64")
    for column, allowed in contract.get("categories", {}).items():
        cleaned[column] = cleaned[column].str.lower().str.replace(" ", "_", regex=False)
        cleaned.loc[~cleaned[column].isin(allowed), column] = pd.NA

    if name == "suppliers":
        invalid = (cleaned["lead_time_days"] < 0) | ~cleaned["reliability_score"].between(0, 1)
    elif name == "products":
        invalid = (cleaned["unit_cost"] < 0) | (cleaned["unit_price"] < 0)
    elif name == "inventory":
        invalid = (cleaned[["quantity_on_hand", "quantity_reserved", "reorder_point", "safety_stock"]] < 0).any(axis=1)
    elif name == "orders":
        invalid = (cleaned["quantity"] <= 0) | (cleaned["unit_price"] < 0)
    elif name == "sales":
        invalid = cleaned["quantity"] == 0
    else:
        invalid = (cleaned["quantity"] <= 0) | (cleaned["expected_date"] < cleaned["order_date"])
    cleaned.loc[invalid.fillna(False), contract["required"][0]] = pd.NA

    cleaned = cleaned.dropna(subset=contract["required"])
    missing_removed = before - len(cleaned)
    before_deduplication = len(cleaned)
    cleaned = cleaned.drop_duplicates(subset=contract["keys"], keep="last").reset_index(drop=True)
    return cleaned, {
        "input_rows": before,
        "missing_or_invalid_removed": missing_removed,
        "duplicates_removed": before_deduplication - len(cleaned),
        "output_rows": len(cleaned),
    }


def clean_datasets(frames: dict[str, pd.DataFrame]) -> tuple[dict[str, pd.DataFrame], dict[str, dict[str, int]]]:
    """Clean all datasets and remove records with unresolved relationships."""
    missing = set(DATA_CONTRACTS) - set(frames)
    if missing:
        raise DataCleaningError(f"Missing datasets: {sorted(missing)}")
    cleaned: dict[str, pd.DataFrame] = {}
    report: dict[str, dict[str, int]] = {}
    for name in DATA_CONTRACTS:
        cleaned[name], report[name] = clean_dataset(name, frames[name])

    relations = [
        ("products", "supplier_id", "suppliers", "supplier_id"),
        ("inventory", "product_id", "products", "product_id"),
        ("orders", "product_id", "products", "product_id"),
        ("sales", "order_id", "orders", "order_id"),
        ("sales", "product_id", "products", "product_id"),
        ("shipments", "supplier_id", "suppliers", "supplier_id"),
        ("shipments", "product_id", "products", "product_id"),
    ]
    for child, child_key, parent, parent_key in relations:
        valid = cleaned[child][child_key].isin(cleaned[parent][parent_key])
        removed = int((~valid).sum())
        if removed:
            cleaned[child] = cleaned[child].loc[valid].reset_index(drop=True)
            report[child]["orphan_rows_removed"] = report[child].get("orphan_rows_removed", 0) + removed
            report[child]["output_rows"] = len(cleaned[child])
    return cleaned, report
