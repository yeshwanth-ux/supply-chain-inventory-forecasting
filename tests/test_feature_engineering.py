"""Tests for leakage-safe demand feature engineering."""

import unittest

import numpy as np
import pandas as pd

from src.features.feature_engineering import DEMAND_FEATURES, MODEL_FEATURES, add_demand_features


class FeatureEngineeringTests(unittest.TestCase):
    @staticmethod
    def demand_panel(days: int = 45) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "product_id": ["P001"] * days,
                "date": pd.date_range("2025-01-01", periods=days, freq="D"),
                "demand": np.arange(1, days + 1, dtype="int64"),
            }
        )

    def test_lags_and_rolling_averages_use_only_previous_dates(self) -> None:
        featured = add_demand_features(self.demand_panel())
        row = featured.iloc[30]
        self.assertEqual(row["previous_day_demand"], 30)
        self.assertEqual(row["demand_lag_7"], 24)
        self.assertEqual(row["demand_lag_30"], 1)
        self.assertAlmostEqual(row["demand_rolling_mean_7"], np.mean(range(24, 31)))
        self.assertAlmostEqual(row["demand_rolling_mean_30"], np.mean(range(1, 31)))

    def test_future_demand_cannot_change_earlier_features(self) -> None:
        original = self.demand_panel()
        changed = original.copy()
        changed.loc[changed.index >= 35, "demand"] = 9999
        original_features = add_demand_features(original).loc[34, list(DEMAND_FEATURES)]
        changed_features = add_demand_features(changed).loc[34, list(DEMAND_FEATURES)]
        pd.testing.assert_series_equal(original_features, changed_features)

    def test_calendar_and_seasonal_features_are_model_ready(self) -> None:
        panel = pd.DataFrame(
            {
                "product_id": ["P002", "P001", "P002", "P001"],
                "date": pd.to_datetime(["2025-01-15", "2025-04-15", "2025-07-15", "2025-10-15"]),
                "demand": [2, 3, 4, 5],
            }
        )
        featured = add_demand_features(panel)
        seasons = dict(zip(featured["month"], featured["season"]))
        self.assertEqual(seasons, {4: "spring", 10: "autumn", 1: "winter", 7: "summer"})
        self.assertTrue(featured[["season_winter", "season_spring", "season_summer", "season_autumn"]].sum(axis=1).eq(1).all())
        self.assertTrue(featured[["month_sin", "month_cos", "day_of_week_sin", "day_of_week_cos"]].abs().le(1).all().all())
        self.assertTrue(set(MODEL_FEATURES).issubset(featured.columns))

    def test_invalid_inputs_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            add_demand_features(pd.DataFrame({"product_id": ["P001"]}))
        invalid = self.demand_panel(2)
        invalid.loc[1, "demand"] = -1
        with self.assertRaises(ValueError):
            add_demand_features(invalid)


if __name__ == "__main__":
    unittest.main()
