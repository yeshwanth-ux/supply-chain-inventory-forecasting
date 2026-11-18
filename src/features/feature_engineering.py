"""Build leakage-safe features for demand forecasting."""

from __future__ import annotations

import pandas as pd


LAG_DAYS = (1, 7, 14, 28)
ROLLING_WINDOWS = (7, 28)


def add_demand_features(demand: pd.DataFrame) -> pd.DataFrame:
    """Add calendar, lag, and trailing features to a daily product panel."""
    required = {"product_id", "date", "demand"}
    if missing := required - set(demand.columns):
        raise ValueError(f"Demand data is missing columns: {sorted(missing)}")
    featured = demand.sort_values(["product_id", "date"]).copy()
    if featured.duplicated(["product_id", "date"]).any():
        raise ValueError("Demand data contains duplicate product/date rows")

    featured["day_of_week"] = featured["date"].dt.dayofweek
    featured["day_of_month"] = featured["date"].dt.day
    featured["week_of_year"] = featured["date"].dt.isocalendar().week.astype("int64")
    featured["month"] = featured["date"].dt.month
    featured["quarter"] = featured["date"].dt.quarter
    featured["day_of_year"] = featured["date"].dt.dayofyear
    featured["is_weekend"] = featured["day_of_week"].isin([5, 6]).astype("int8")

    grouped = featured.groupby("product_id", sort=False)["demand"]
    for lag in LAG_DAYS:
        featured[f"demand_lag_{lag}"] = grouped.shift(lag)
    for window in ROLLING_WINDOWS:
        featured[f"demand_rolling_mean_{window}"] = grouped.transform(
            lambda values: values.shift(1).rolling(window=window, min_periods=window).mean()
        )
        featured[f"demand_rolling_std_{window}"] = grouped.transform(
            lambda values: values.shift(1).rolling(window=window, min_periods=window).std(ddof=0)
        )
    return featured
