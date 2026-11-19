"""Build leakage-safe features for demand forecasting."""

from __future__ import annotations

import numpy as np
import pandas as pd


LAG_DAYS = (1, 7, 30)
ROLLING_WINDOWS = (7, 30)
SEASON_BY_MONTH = {
    1: "winter",
    2: "winter",
    3: "spring",
    4: "spring",
    5: "spring",
    6: "summer",
    7: "summer",
    8: "summer",
    9: "autumn",
    10: "autumn",
    11: "autumn",
    12: "winter",
}

CALENDAR_FEATURES = (
    "day_of_week",
    "day_of_month",
    "week_of_year",
    "month",
    "quarter",
    "day_of_year",
    "is_weekend",
    "month_sin",
    "month_cos",
    "day_of_week_sin",
    "day_of_week_cos",
    "day_of_year_sin",
    "day_of_year_cos",
    "season_winter",
    "season_spring",
    "season_summer",
    "season_autumn",
)
DEMAND_FEATURES = (
    "previous_day_demand",
    "demand_lag_7",
    "demand_lag_30",
    "demand_rolling_mean_7",
    "demand_rolling_std_7",
    "demand_rolling_mean_30",
    "demand_rolling_std_30",
)
MODEL_FEATURES = ("product_code", *CALENDAR_FEATURES, *DEMAND_FEATURES)


def add_demand_features(demand: pd.DataFrame) -> pd.DataFrame:
    """Add calendar, lag, and trailing features to a daily product panel."""
    required = {"product_id", "date", "demand"}
    if missing := required - set(demand.columns):
        raise ValueError(f"Demand data is missing columns: {sorted(missing)}")
    featured = demand.copy()
    featured["date"] = pd.to_datetime(featured["date"], errors="raise")
    featured["demand"] = pd.to_numeric(featured["demand"], errors="raise")
    if featured[["product_id", "date", "demand"]].isna().any().any():
        raise ValueError("Demand feature inputs cannot contain missing values")
    if (featured["demand"] < 0).any():
        raise ValueError("Demand cannot be negative")
    featured = featured.sort_values(["product_id", "date"]).reset_index(drop=True)
    if featured.duplicated(["product_id", "date"]).any():
        raise ValueError("Demand data contains duplicate product/date rows")

    featured["day_of_week"] = featured["date"].dt.dayofweek
    featured["day_of_month"] = featured["date"].dt.day
    featured["week_of_year"] = featured["date"].dt.isocalendar().week.astype("int64")
    featured["month"] = featured["date"].dt.month
    featured["quarter"] = featured["date"].dt.quarter
    featured["day_of_year"] = featured["date"].dt.dayofyear
    featured["is_weekend"] = featured["day_of_week"].isin([5, 6]).astype("int8")
    featured["season"] = featured["month"].map(SEASON_BY_MONTH)

    featured["month_sin"] = np.sin(2 * np.pi * (featured["month"] - 1) / 12)
    featured["month_cos"] = np.cos(2 * np.pi * (featured["month"] - 1) / 12)
    featured["day_of_week_sin"] = np.sin(2 * np.pi * featured["day_of_week"] / 7)
    featured["day_of_week_cos"] = np.cos(2 * np.pi * featured["day_of_week"] / 7)
    featured["day_of_year_sin"] = np.sin(2 * np.pi * (featured["day_of_year"] - 1) / 365.25)
    featured["day_of_year_cos"] = np.cos(2 * np.pi * (featured["day_of_year"] - 1) / 365.25)
    for season in ("winter", "spring", "summer", "autumn"):
        featured[f"season_{season}"] = (featured["season"] == season).astype("int8")

    product_codes = {
        product_id: code
        for code, product_id in enumerate(sorted(featured["product_id"].unique()))
    }
    featured["product_code"] = featured["product_id"].map(product_codes).astype("int64")

    grouped = featured.groupby("product_id", sort=False)["demand"]
    for lag in LAG_DAYS:
        name = "previous_day_demand" if lag == 1 else f"demand_lag_{lag}"
        featured[name] = grouped.shift(lag)
    for window in ROLLING_WINDOWS:
        featured[f"demand_rolling_mean_{window}"] = grouped.transform(
            lambda values: values.shift(1).rolling(window=window, min_periods=window).mean()
        )
        featured[f"demand_rolling_std_{window}"] = grouped.transform(
            lambda values: values.shift(1).rolling(window=window, min_periods=window).std(ddof=0)
        )
    return featured
