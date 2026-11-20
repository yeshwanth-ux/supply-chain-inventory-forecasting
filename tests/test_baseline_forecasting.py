"""Tests for deterministic baseline demand forecasts."""

import tempfile
import unittest
from pathlib import Path

import pandas as pd

from src.data.generate_synthetic import generate_datasets
from src.forecasting.baseline import run_baseline_forecasting
from src.forecasting.evaluate import attach_actuals, calculate_metrics
from src.forecasting.predict import forecast_baselines, generate_horizon_forecasts
from src.forecasting.train import chronological_holdout


class BaselineForecastingTests(unittest.TestCase):
    @staticmethod
    def panel(days: int = 70) -> pd.DataFrame:
        dates = pd.date_range("2025-01-01", periods=days, freq="D")
        return pd.concat(
            [
                pd.DataFrame({"product_id": product, "date": dates, "demand": demand})
                for product, demand in (("P001", range(1, days + 1)), ("P002", [5] * days))
            ],
            ignore_index=True,
        )

    def test_recursive_moving_average_does_not_use_holdout_actuals(self) -> None:
        train, actuals, origin = chronological_holdout(self.panel(), horizon_days=7)
        predictions = forecast_baselines(train, origin, horizon_days=7, moving_average_window=7)
        moving = predictions.loc[
            (predictions["product_id"] == "P001")
            & (predictions["model"] == "moving_average")
        ].sort_values("forecast_day")
        expected_first = train.loc[train["product_id"] == "P001", "demand"].tail(7).mean()
        self.assertAlmostEqual(moving.iloc[0]["predicted_demand"], expected_first)
        self.assertNotEqual(moving.iloc[1]["predicted_demand"], actuals.iloc[0]["demand"])
        changed_actuals = actuals.copy()
        changed_actuals["demand"] = 9999
        repeated = forecast_baselines(train, origin, horizon_days=7, moving_average_window=7)
        pd.testing.assert_frame_equal(predictions, repeated)

    def test_all_models_and_horizons_are_generated(self) -> None:
        train, _, origin = chronological_holdout(self.panel(), horizon_days=30)
        predictions = generate_horizon_forecasts(train, origin)
        self.assertEqual(set(predictions["horizon_days"]), {7, 14, 30})
        self.assertEqual(set(predictions["model"]), {"moving_average", "last_observation"})
        self.assertEqual(len(predictions), 2 * 2 * (7 + 14 + 30))
        self.assertTrue((predictions["predicted_demand"] >= 0).all())

    def test_evaluation_metrics_are_calculated(self) -> None:
        train, actuals, origin = chronological_holdout(self.panel(), horizon_days=30)
        evaluated = attach_actuals(generate_horizon_forecasts(train, origin), actuals)
        metrics = calculate_metrics(evaluated)
        self.assertEqual(len(metrics), 6)
        self.assertFalse(metrics[["mae", "rmse", "mean_error", "wape"]].isna().any().any())
        self.assertTrue((metrics[["mae", "rmse", "wape"]] >= 0).all().all())

    def test_workflow_writes_predictions_metrics_metadata_and_report(self) -> None:
        with tempfile.TemporaryDirectory() as source, tempfile.TemporaryDirectory() as target:
            generate_datasets(source, seed=42)
            root = Path(target)
            metadata = run_baseline_forecasting(source, root / "baseline", root / "day10.md")
            expected = {
                "baseline_predictions.csv",
                "baseline_forecast_7_day.csv",
                "baseline_forecast_14_day.csv",
                "baseline_forecast_30_day.csv",
                "baseline_metrics.csv",
                "baseline_metadata.json",
            }
            self.assertEqual({path.name for path in (root / "baseline").iterdir()}, expected)
            self.assertTrue((root / "day10.md").is_file())
            self.assertEqual(metadata["prediction_rows"], 3060)

    def test_invalid_or_incomplete_history_is_rejected(self) -> None:
        incomplete = self.panel().drop(index=5)
        with self.assertRaises(ValueError):
            chronological_holdout(incomplete, horizon_days=7)
        with self.assertRaises(ValueError):
            forecast_baselines(self.panel(), "2025-02-09", horizon_days=0)


if __name__ == "__main__":
    unittest.main()
