"""Tests for Random Forest and Gradient Boosting demand models."""

import tempfile
import unittest
from pathlib import Path

import pandas as pd

from src.data.generate_synthetic import generate_datasets
from src.features.feature_engineering import MODEL_FEATURES
from src.forecasting.ml_models import (
    MODEL_CONFIGS,
    run_ml_training,
    split_tuning_data,
    train_and_evaluate_models,
)


class MachineLearningModelTests(unittest.TestCase):
    @staticmethod
    def model_frame(start: str, days: int) -> pd.DataFrame:
        dates = pd.date_range(start, periods=days, freq="D")
        rows = []
        for product_code, product_id in enumerate(("P001", "P002")):
            for day_number, date in enumerate(dates):
                row = {
                    "product_id": product_id,
                    "date": date,
                    "demand": float((day_number + product_code) % 8),
                }
                row.update({feature: float((day_number + index) % 11) for index, feature in enumerate(MODEL_FEATURES)})
                row["product_code"] = float(product_code)
                rows.append(row)
        return pd.DataFrame(rows)

    def test_tuning_split_is_chronological(self) -> None:
        fit, validation = split_tuning_data(self.model_frame("2025-01-01", 60), 14)
        self.assertLess(fit["date"].max(), validation["date"].min())
        self.assertEqual(validation["date"].nunique(), 14)

    def test_both_models_generate_nonnegative_predictions_and_metrics(self) -> None:
        training = self.model_frame("2025-01-01", 60)
        testing = self.model_frame("2025-03-02", 10)
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
            models, predictions, metrics, tuning, importance = train_and_evaluate_models(
                training, testing, validation_days=14
            )
        finally:
            for name, grid in original_grids.items():
                MODEL_CONFIGS[name]["parameter_grid"] = grid
        self.assertEqual(set(models), {"random_forest", "gradient_boosting"})
        self.assertEqual(len(predictions), len(testing))
        self.assertTrue(predictions.filter(like="_prediction").ge(0).all().all())
        self.assertEqual(set(metrics["model"]), set(models))
        self.assertFalse(metrics[["mae", "rmse", "wape", "r2"]].isna().any().any())
        self.assertEqual(len(tuning), 2)
        self.assertEqual(len(importance), 2 * len(MODEL_FEATURES))

    def test_workflow_writes_all_outputs(self) -> None:
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
                metadata = run_ml_training(
                    source,
                    root / "output",
                    root / "models",
                    root / "day11.md",
                    validation_days=14,
                )
            finally:
                for name, grid in original_grids.items():
                    MODEL_CONFIGS[name]["parameter_grid"] = grid
            expected_outputs = {
                "ml_predictions.csv",
                "ml_model_metrics.csv",
                "ml_tuning_results.csv",
                "ml_feature_importance.csv",
                "ml_metadata.json",
            }
            self.assertEqual({path.name for path in (root / "output").iterdir()}, expected_outputs)
            self.assertEqual(
                {path.name for path in (root / "models").iterdir()},
                {"random_forest.joblib", "gradient_boosting.joblib"},
            )
            self.assertTrue((root / "day11.md").is_file())
            self.assertIn(metadata["best_model"], {"random_forest", "gradient_boosting"})

    def test_invalid_training_data_is_rejected(self) -> None:
        invalid = self.model_frame("2025-01-01", 40).drop(columns=[MODEL_FEATURES[-1]])
        with self.assertRaises(ValueError):
            split_tuning_data(invalid, 10)
        with self.assertRaises(ValueError):
            split_tuning_data(self.model_frame("2025-01-01", 10), 10)


if __name__ == "__main__":
    unittest.main()
