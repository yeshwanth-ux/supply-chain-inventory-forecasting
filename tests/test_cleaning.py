"""Tests for Pandas data cleaning behavior."""

import unittest

import pandas as pd

from src.data.cleaning import clean_dataset


class CleaningTests(unittest.TestCase):
    def test_orders_are_standardized_and_deduplicated(self) -> None:
        frame = pd.DataFrame([
            {"order_id": " ord001 ", "order_date": "2025/01/02", "customer_id": "cus1", "product_id": "prd1", "quantity": "2", "unit_price": "10.50", "status": "Completed"},
            {"order_id": "ORD001", "order_date": "2025-01-03", "customer_id": "CUS1", "product_id": "PRD1", "quantity": "3", "unit_price": "10.50", "status": "completed"},
            {"order_id": "", "order_date": "bad-date", "customer_id": "CUS2", "product_id": "PRD1", "quantity": "x", "unit_price": "10", "status": "unknown"},
        ])
        cleaned, report = clean_dataset("orders", frame)
        self.assertEqual(len(cleaned), 1)
        self.assertEqual(cleaned.loc[0, "order_id"], "ORD001")
        self.assertEqual(cleaned.loc[0, "quantity"], 3)
        self.assertEqual(report["duplicates_removed"], 1)
        self.assertEqual(report["missing_or_invalid_removed"], 1)

    def test_inventory_fills_optional_reserved_quantity(self) -> None:
        frame = pd.DataFrame([{
            "snapshot_date": "2025-12-31", "product_id": "prd1", "warehouse_id": "wh001",
            "quantity_on_hand": "10", "reorder_point": "5", "safety_stock": "2",
        }])
        cleaned, _ = clean_dataset("inventory", frame)
        self.assertEqual(cleaned.loc[0, "product_id"], "PRD1")
        self.assertEqual(cleaned.loc[0, "quantity_reserved"], 0)


if __name__ == "__main__":
    unittest.main()
