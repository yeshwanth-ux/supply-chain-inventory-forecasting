"""Tests for daily demand preparation and chronological splitting."""

import tempfile
import unittest
from pathlib import Path

import pandas as pd

from src.analysis.common import load_clean_datasets
from src.data.generate_synthetic import generate_datasets
from src.forecasting.prepare import build_daily_demand, run_preparation, split_forecasting_data


class ForecastingPreparationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.source = tempfile.TemporaryDirectory()
        generate_datasets(self.source.name, seed=42)
        self.daily = build_daily_demand(load_clean_datasets(self.source.name))

    def tearDown(self) -> None:
        self.source.cleanup()

    def test_daily_panel_is_complete_and_zero_filled(self) -> None:
        counts = self.daily.groupby("product_id")["date"].nunique()
        expected_dates = self.daily["date"].nunique()
        self.assertTrue((counts == expected_dates).all())
        self.assertFalse(self.daily["demand"].isna().any())
        self.assertGreater(int((self.daily["demand"] == 0).sum()), 0)
        self.assertFalse(self.daily.duplicated(["product_id", "date"]).any())

    def test_features_use_prior_demand_and_split_does_not_overlap(self) -> None:
        model, training, testing, metadata = split_forecasting_data(self.daily, test_days=30)
        self.assertLess(training["date"].max(), testing["date"].min())
        self.assertEqual(testing["date"].nunique(), 30)
        self.assertFalse(model.filter(regex=r"(previous_day_demand|demand_(lag|rolling))").isna().any().any())
        row = model.iloc[0]
        previous = self.daily.loc[
            (self.daily["product_id"] == row["product_id"])
            & (self.daily["date"] == row["date"] - pd.Timedelta(days=1)),
            "demand",
        ].iloc[0]
        self.assertEqual(row["previous_day_demand"], previous)
        self.assertEqual(metadata["training_rows"] + metadata["testing_rows"], metadata["model_rows"])

    def test_workflow_writes_all_model_datasets(self) -> None:
        with tempfile.TemporaryDirectory() as output:
            root = Path(output)
            report = root / "day8.md"
            metadata = run_preparation(self.source.name, root / "forecasting", report)
            for filename in (
                "daily_demand.csv",
                "model_data.csv",
                "train.csv",
                "test.csv",
                "final_training_data.csv",
                "final_testing_data.csv",
                "metadata.json",
            ):
                self.assertTrue((root / "forecasting" / filename).is_file())
            self.assertTrue(report.is_file())
            self.assertEqual(metadata["test_days"], 30)

    def test_invalid_split_configuration_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            split_forecasting_data(self.daily, test_days=0)
        with self.assertRaises(ValueError):
            split_forecasting_data(self.daily, test_days=300, minimum_training_days=100)


if __name__ == "__main__":
    unittest.main()
