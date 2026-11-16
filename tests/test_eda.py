"""Tests for exploratory analysis calculations."""

import tempfile
import unittest
from pathlib import Path

from src.analysis.eda import calculate_insights, prepare_analysis, run_eda
from src.data.generate_synthetic import generate_datasets


class ExploratoryAnalysisTests(unittest.TestCase):
    def setUp(self) -> None:
        self.source = tempfile.TemporaryDirectory()
        generate_datasets(self.source.name, seed=42)

    def tearDown(self) -> None:
        self.source.cleanup()

    def test_analysis_excludes_partial_final_month_from_seasonality(self) -> None:
        analysis = prepare_analysis(self.source.name)
        final_month = analysis["monthly"].iloc[-1]
        self.assertFalse(bool(final_month["is_complete_month"]))
        self.assertEqual(
            analysis["seasonality"]["years_observed"].sum(),
            analysis["monthly"]["is_complete_month"].sum(),
        )

    def test_headline_metrics_are_reconciled(self) -> None:
        analysis = prepare_analysis(self.source.name)
        insights = calculate_insights(analysis)
        self.assertAlmostEqual(insights["total_sales"], analysis["sales"]["revenue"].sum(), places=2)
        self.assertEqual(insights["net_units_sold"], analysis["sales"]["quantity"].sum())
        self.assertEqual(
            insights["complete_months_observed"],
            int(analysis["monthly"]["is_complete_month"].sum()),
        )

    def test_workflow_writes_report_tables_and_figures(self) -> None:
        with tempfile.TemporaryDirectory() as output:
            root = Path(output)
            run_eda(self.source.name, root / "figures", root / "day6_eda.md")
            self.assertTrue((root / "day6_eda.md").is_file())
            self.assertEqual(len(list((root / "figures").glob("*.png"))), 4)
            self.assertTrue((root / "eda_tables" / "product_performance.csv").is_file())


if __name__ == "__main__":
    unittest.main()
