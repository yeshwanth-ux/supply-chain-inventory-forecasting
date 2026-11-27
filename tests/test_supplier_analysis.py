"""Tests for supplier delivery and inbound order analysis."""

import tempfile
import unittest
from pathlib import Path

import pandas as pd

from src.analysis.supplier_analysis import (
    calculate_supplier_performance,
    run_supplier_analysis,
)
from src.data.generate_synthetic import generate_datasets


class SupplierAnalysisTests(unittest.TestCase):
    @staticmethod
    def frames() -> dict[str, pd.DataFrame]:
        return {
            "suppliers": pd.DataFrame(
                {
                    "supplier_id": ["S001", "S002"],
                    "supplier_name": ["Supplier One", "Supplier Two"],
                    "country": ["US", "CA"],
                    "lead_time_days": [5, 5],
                    "reliability_score": [0.95, 0.85],
                }
            ),
            "inventory": pd.DataFrame(
                {"snapshot_date": pd.to_datetime(["2025-01-31"])}
            ),
            "shipments": pd.DataFrame(
                {
                    "shipment_id": ["SH1", "SH2", "SH3", "SH4"],
                    "supplier_id": ["S001", "S001", "S002", "S002"],
                    "product_id": ["P1", "P1", "P2", "P2"],
                    "order_date": pd.to_datetime(
                        ["2025-01-01", "2025-01-02", "2025-01-01", "2025-01-10"]
                    ),
                    "expected_date": pd.to_datetime(
                        ["2025-01-06", "2025-01-07", "2025-01-06", "2025-01-15"]
                    ),
                    "arrival_date": pd.to_datetime(
                        ["2025-01-06", "2025-01-09", None, None]
                    ),
                    "quantity": [10, 20, 30, 40],
                    "status": ["delivered", "delivered", "delayed", "in_transit"],
                }
            ),
        }

    def test_delivery_lead_time_delay_and_status_metrics(self) -> None:
        performance, delayed, status, summary = calculate_supplier_performance(
            self.frames(), on_time_target=0.90, reliability_threshold=0.90
        )
        first = performance.set_index("supplier_id").loc["S001"]
        second = performance.set_index("supplier_id").loc["S002"]
        self.assertEqual(first["delivered_shipments"], 2)
        self.assertAlmostEqual(first["on_time_delivery_rate"], 0.5)
        self.assertAlmostEqual(first["average_actual_lead_time_days"], 6.0)
        self.assertEqual(second["open_overdue_shipments"], 2)
        self.assertEqual(str(second["supplier_status"]), "UNRELIABLE")
        self.assertEqual(set(delayed["shipment_id"]), {"SH2", "SH3", "SH4"})
        self.assertEqual(status["purchase_order_lines"].sum(), 4)
        self.assertEqual(summary["identified_delayed_shipments"], 3)

    def test_invalid_thresholds_and_empty_shipments_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            calculate_supplier_performance(self.frames(), on_time_target=0)
        frames = self.frames()
        frames["shipments"] = frames["shipments"].iloc[0:0]
        with self.assertRaises(ValueError):
            calculate_supplier_performance(frames)

    def test_workflow_writes_all_analysis_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as source, tempfile.TemporaryDirectory() as target:
            generate_datasets(source, seed=42)
            root = Path(target)
            summary = run_supplier_analysis(
                source, root / "supplier_analysis", root / "day14.md"
            )
            self.assertEqual(
                {path.name for path in (root / "supplier_analysis").iterdir()},
                {
                    "supplier_performance.csv",
                    "delayed_shipments.csv",
                    "purchase_order_status.csv",
                    "supplier_analysis_summary.json",
                },
            )
            self.assertTrue((root / "day14.md").is_file())
            self.assertEqual(summary["supplier_count"], 8)


if __name__ == "__main__":
    unittest.main()
