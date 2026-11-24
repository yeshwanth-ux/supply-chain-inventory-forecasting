"""Tests for forecast comparison and best-model selection."""

import tempfile
import unittest
from pathlib import Path

import joblib
import pandas as pd

from src.data.generate_synthetic import generate_datasets
from src.forecasting.evaluate import (
    calculate_model_metrics,
    reshape_model_predictions,
    select_best_model,
)
from src.forecasting.forecast_evaluation import run_forecast_evaluation
from src.forecasting.ml_models import MODEL_CONFIGS


class ForecastEvaluationTests(unittest.TestCase):
    @staticmethod
    def wide_predictions() -> pd.DataFrame:
        return pd.DataFrame(
            {
                "product_id": ["P001", "P001", "P002", "P002"],
                "date": pd.date_range("2025-01-01", periods=4, freq="D"),
                "actual_demand": [2.0, 4.0, 1.0, 3.0],
                "random_forest_prediction": [2.0, 3.0, 2.0, 3.0],
                "gradient_boosting_prediction": [2.0, 4.0, 1.0, 3.0],
            }
        )

    def test_metrics_and_bias_are_calculated_exactly(self) -> None:
        long = reshape_model_predictions(self.wide_predictions())
        metrics = calculate_model_metrics(long).set_index("model")
        self.assertEqual(len(long), 8)
        self.assertEqual(metrics.loc["gradient_boosting", "mae"], 0.0)
        self.assertAlmostEqual(metrics.loc["random_forest", "mae"], 0.5)
        self.assertAlmostEqual(metrics.loc["random_forest", "rmse"], 2 ** -0.5)
        self.assertAlmostEqual(metrics.loc["random_forest", "wape"], 0.2)
        self.assertAlmostEqual(metrics.loc["random_forest", "forecast_bias"], 0.0)

    def test_best_model_uses_mae_then_tie_breakers(self) -> None:
        metrics = calculate_model_metrics(reshape_model_predictions(self.wide_predictions()))
        self.assertEqual(select_best_model(metrics), "gradient_boosting")
        tied = metrics.copy()
        tied.loc[:, ["mae", "rmse", "wape", "forecast_bias"]] = 1.0
        self.assertEqual(select_best_model(tied), "gradient_boosting")

    def test_invalid_prediction_data_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            reshape_model_predictions(self.wide_predictions().drop(columns="actual_demand"))
        invalid = self.wide_predictions()
        invalid.loc[0, "random_forest_prediction"] = None
        with self.assertRaises(ValueError):
            reshape_model_predictions(invalid)

    def test_workflow_saves_selected_model_and_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as source, tempfile.TemporaryDirectory() as target:
            generate_datasets(source, seed=42)
            root = Path(target)
            original_grids = {
                name: config["parameter_grid"] for name, config in MODEL_CONFIGS.items()
            }
            try:
                MODEL_CONFIGS["random_forest"]["parameter_grid"] = {
                    "n_estimators": [10], "max_depth": [4], "min_samples_leaf": [1]
                }
                MODEL_CONFIGS["gradient_boosting"]["parameter_grid"] = {
                    "n_estimators": [10], "learning_rate": [0.05], "max_depth": [2]
                }
                metadata = run_forecast_evaluation(
                    source,
                    root / "evaluation",
                    root / "models" / "best.joblib",
                    root / "day12.md",
                    validation_days=14,
                )
            finally:
                for name, grid in original_grids.items():
                    MODEL_CONFIGS[name]["parameter_grid"] = grid

            self.assertEqual(
                {path.name for path in (root / "evaluation").iterdir()},
                {
                    "actual_vs_predicted.csv",
                    "forecast_model_comparison.csv",
                    "forecast_evaluation_metadata.json",
                },
            )
            bundle = joblib.load(root / "models" / "best.joblib")
            self.assertEqual(bundle["model_name"], metadata["best_model"])
            self.assertIn("estimator", bundle)
            self.assertEqual(bundle["feature_columns"], metadata["feature_columns"])
            self.assertTrue((root / "day12.md").is_file())


if __name__ == "__main__":
    unittest.main()
