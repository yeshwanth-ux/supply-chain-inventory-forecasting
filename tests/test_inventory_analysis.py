"""Tests for product-level inventory analysis."""

import tempfile
import unittest
from pathlib import Path

from src.analysis.common import load_clean_datasets
from src.data.generate_synthetic import generate_datasets
from src.inventory.analysis import calculate_inventory_metrics, run_inventory_analysis


class InventoryAnalysisTests(unittest.TestCase):
    def setUp(self) -> None:
        self.source = tempfile.TemporaryDirectory()
        generate_datasets(self.source.name, seed=42)

    def tearDown(self) -> None:
        self.source.cleanup()

    def test_stock_and_risk_calculations_reconcile(self) -> None:
        analysis, summary = calculate_inventory_metrics(load_clean_datasets(self.source.name))
        self.assertTrue((analysis["available_stock"] == analysis["quantity_on_hand"] - analysis["quantity_reserved"]).all())
        self.assertTrue((analysis["low_stock"] == (analysis["available_stock"] <= analysis["reorder_point"])).all())
        self.assertEqual(summary["total_available"], int(analysis["available_stock"].sum()))
        self.assertTrue(
            analysis.loc[analysis["low_stock"], "stockout_risk"].astype("string").isin(["HIGH", "OUT_OF_STOCK"]).all()
        )

    def test_invalid_thresholds_are_rejected(self) -> None:
        frames = load_clean_datasets(self.source.name)
        with self.assertRaises(ValueError):
            calculate_inventory_metrics(frames, trailing_days=0)
        with self.assertRaises(ValueError):
            calculate_inventory_metrics(frames, excess_cover_days=-1)

    def test_workflow_writes_report_and_detail_table(self) -> None:
        with tempfile.TemporaryDirectory() as output:
            report = Path(output) / "day7_inventory_analysis.md"
            summary = run_inventory_analysis(self.source.name, report)
            self.assertTrue(report.is_file())
            self.assertTrue((Path(output) / "inventory_tables" / "inventory_analysis.csv").is_file())
            self.assertGreater(summary["total_available"], 0)


if __name__ == "__main__":
    unittest.main()
