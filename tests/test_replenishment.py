"""Tests for inventory optimization and replenishment recommendations."""

import tempfile
import unittest
from pathlib import Path

import pandas as pd

from src.data.generate_synthetic import generate_datasets
from src.inventory.replenishment import (
    calculate_replenishment_recommendations,
    run_replenishment_optimization,
)


class ReplenishmentTests(unittest.TestCase):
    @staticmethod
    def frames() -> dict[str, pd.DataFrame]:
        dates = pd.date_range("2025-03-22", "2025-03-31", freq="D")
        orders = pd.DataFrame(
            {
                "order_id": [f"O{i:02d}" for i in range(10)],
                "order_date": dates,
                "product_id": ["P001"] * 10,
                "quantity": [2, 4] * 5,
                "status": ["completed"] * 10,
            }
        )
        return {
            "products": pd.DataFrame(
                {
                    "product_id": ["P001"],
                    "sku": ["SKU-1"],
                    "product_name": ["Test Product"],
                    "category": ["Test"],
                    "supplier_id": ["S001"],
                    "unit_cost": [10.0],
                }
            ),
            "suppliers": pd.DataFrame(
                {
                    "supplier_id": ["S001"],
                    "supplier_name": ["Test Supplier"],
                    "lead_time_days": [4],
                    "reliability_score": [0.95],
                }
            ),
            "inventory": pd.DataFrame(
                {
                    "snapshot_date": pd.to_datetime(["2025-03-31"]),
                    "product_id": ["P001"],
                    "warehouse_id": ["W001"],
                    "quantity_on_hand": [12],
                    "quantity_reserved": [2],
                }
            ),
            "orders": orders,
            "shipments": pd.DataFrame(
                {
                    "shipment_id": ["SH1", "SH2"],
                    "product_id": ["P001", "P001"],
                    "quantity": [5, 100],
                    "status": ["in_transit", "delivered"],
                    "expected_date": pd.to_datetime(["2025-03-30", "2025-03-25"]),
                    "arrival_date": pd.to_datetime([None, "2025-03-25"]),
                }
            ),
        }

    def test_safety_stock_reorder_point_and_incoming_stock(self) -> None:
        recommendations, summary = calculate_replenishment_recommendations(
            self.frames(), service_level=0.95, demand_window_days=10, review_period_days=7
        )
        row = recommendations.iloc[0]
        self.assertAlmostEqual(row["average_daily_demand"], 3.0)
        self.assertEqual(row["available_stock"], 10)
        self.assertEqual(row["incoming_quantity"], 5)
        self.assertEqual(row["overdue_incoming_quantity"], 5)
        self.assertEqual(row["inventory_position"], 15)
        self.assertEqual(row["safety_stock"], 4)
        self.assertEqual(row["reorder_point"], 16)
        self.assertEqual(row["target_stock"], 37)
        self.assertEqual(row["recommended_reorder_quantity"], 22)
        self.assertEqual(row["replenishment_action"], "ORDER_NOW")
        self.assertEqual(summary["recommended_order_units"], 22)

    def test_incoming_stock_can_prevent_duplicate_order(self) -> None:
        frames = self.frames()
        frames["shipments"].loc[0, "quantity"] = 40
        recommendations, _ = calculate_replenishment_recommendations(
            frames, demand_window_days=10, review_period_days=7
        )
        row = recommendations.iloc[0]
        self.assertEqual(row["recommended_reorder_quantity"], 0)
        self.assertEqual(row["replenishment_action"], "EXPEDITE_INCOMING")

    def test_invalid_parameters_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            calculate_replenishment_recommendations(self.frames(), service_level=1.0)
        with self.assertRaises(ValueError):
            calculate_replenishment_recommendations(self.frames(), demand_window_days=1)

    def test_workflow_writes_recommendations_queue_summary_and_report(self) -> None:
        with tempfile.TemporaryDirectory() as source, tempfile.TemporaryDirectory() as target:
            generate_datasets(source, seed=42)
            root = Path(target)
            summary = run_replenishment_optimization(
                source, root / "optimization", root / "day13.md"
            )
            self.assertEqual(
                {path.name for path in (root / "optimization").iterdir()},
                {
                    "replenishment_recommendations.csv",
                    "replenishment_action_queue.csv",
                    "replenishment_summary.json",
                },
            )
            self.assertTrue((root / "day13.md").is_file())
            self.assertEqual(summary["product_count"], 30)
            self.assertGreater(summary["overdue_review_products"], 0)


if __name__ == "__main__":
    unittest.main()
