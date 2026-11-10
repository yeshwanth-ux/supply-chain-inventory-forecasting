"""Generate reproducible, relational supply-chain datasets."""

from __future__ import annotations

import argparse
import csv
import random
from datetime import date, timedelta
from pathlib import Path

from src.data.ingestion import DATASET_FILES, load_datasets


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def generate_datasets(output_dir: Path | str, seed: int = 42) -> dict[str, int]:
    """Generate datasets in *output_dir*, validate them, and return row counts."""
    rng, output, start = random.Random(seed), Path(output_dir), date(2025, 1, 1)
    categories = ["Electronics", "Home", "Office", "Industrial", "Personal Care"]
    countries = ["United States", "Canada", "Mexico", "Germany", "India"]
    suppliers = [{"supplier_id": f"SUP{i:03d}", "supplier_name": f"Supplier {i:02d}", "country": countries[(i - 1) % 5], "lead_time_days": rng.randint(4, 21), "reliability_score": f"{rng.uniform(0.82, 0.99):.3f}"} for i in range(1, 9)]

    products = []
    for i in range(1, 31):
        cost = round(rng.uniform(5, 180), 2)
        products.append({"product_id": f"PRD{i:04d}", "sku": f"SKU-{1000 + i}", "product_name": f"Product {i:03d}", "category": categories[(i - 1) % 5], "supplier_id": suppliers[(i - 1) % 8]["supplier_id"], "unit_cost": f"{cost:.2f}", "unit_price": f"{cost * rng.uniform(1.25, 1.8):.2f}"})

    inventory = []
    for product in products:
        for warehouse in ("WH001", "WH002", "WH003"):
            reorder = rng.randint(20, 80)
            inventory.append({"snapshot_date": "2025-12-31", "product_id": product["product_id"], "warehouse_id": warehouse, "quantity_on_hand": rng.randint(0, 300), "quantity_reserved": rng.randint(0, 20), "reorder_point": reorder, "safety_stock": max(10, reorder // 2)})

    orders, sales = [], []
    for i in range(1, 1001):
        product, ordered, quantity = rng.choice(products), start + timedelta(days=rng.randrange(365)), rng.randint(1, 12)
        status, order_id = rng.choice(["completed"] * 8 + ["cancelled", "returned"]), f"ORD{i:06d}"
        orders.append({"order_id": order_id, "order_date": ordered.isoformat(), "customer_id": f"CUS{rng.randint(1, 250):04d}", "product_id": product["product_id"], "quantity": quantity, "unit_price": product["unit_price"], "status": status})
        if status in {"completed", "returned"}:
            sold = -quantity if status == "returned" else quantity
            sales.append({"sale_id": f"SAL{len(sales) + 1:06d}", "order_id": order_id, "sale_date": (ordered + timedelta(days=rng.randint(0, 4))).isoformat(), "product_id": product["product_id"], "quantity": sold, "revenue": f"{sold * float(product['unit_price']):.2f}"})

    shipments = []
    for i in range(1, 181):
        product = rng.choice(products)
        supplier = next(row for row in suppliers if row["supplier_id"] == product["supplier_id"])
        ordered = start + timedelta(days=rng.randrange(340))
        expected = ordered + timedelta(days=int(supplier["lead_time_days"]))
        status = rng.choice(["delivered"] * 8 + ["in_transit", "delayed"])
        arrival = "" if status != "delivered" else (expected + timedelta(days=rng.randint(-2, 5))).isoformat()
        shipments.append({"shipment_id": f"SHP{i:05d}", "supplier_id": supplier["supplier_id"], "product_id": product["product_id"], "order_date": ordered.isoformat(), "expected_date": expected.isoformat(), "arrival_date": arrival, "quantity": rng.randint(50, 500), "status": status})

    datasets = {"products": products, "suppliers": suppliers, "inventory": inventory, "orders": orders, "sales": sales, "shipments": shipments}
    for name, rows in datasets.items():
        _write_csv(output / DATASET_FILES[name], rows)
    load_datasets(output)
    return {name: len(rows) for name, rows in datasets.items()}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("data/synthetic"))
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    counts = generate_datasets(args.output_dir, args.seed)
    print("Generated and validated: " + ", ".join(f"{name}={count}" for name, count in counts.items()))


if __name__ == "__main__":
    main()
