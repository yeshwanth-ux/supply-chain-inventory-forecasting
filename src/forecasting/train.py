"""Validate daily demand history and create chronological forecast origins."""

from __future__ import annotations

import pandas as pd


def validate_daily_history(daily: pd.DataFrame) -> pd.DataFrame:
    """Return a sorted, validated product-level daily demand panel."""
    required = {"product_id", "date", "demand"}
    if missing := required - set(daily.columns):
        raise ValueError(f"Daily demand is missing columns: {sorted(missing)}")
    history = daily.copy()
    history["date"] = pd.to_datetime(history["date"], errors="raise")
    history["demand"] = pd.to_numeric(history["demand"], errors="raise")
    if history[list(required)].isna().any().any():
        raise ValueError("Daily demand cannot contain missing product, date, or demand values")
    if (history["demand"] < 0).any():
        raise ValueError("Daily demand cannot be negative")
    if history.duplicated(["product_id", "date"]).any():
        raise ValueError("Daily demand contains duplicate product/date rows")
    history = history.sort_values(["product_id", "date"]).reset_index(drop=True)
    date_steps = history.groupby("product_id")["date"].diff().dropna()
    if not date_steps.eq(pd.Timedelta(days=1)).all():
        raise ValueError("Every product must have complete consecutive daily history")
    date_ranges = history.groupby("product_id")["date"].agg(["min", "max", "count"])
    if len(date_ranges[["min", "max", "count"]].drop_duplicates()) != 1:
        raise ValueError("Every product must share the same daily history range")
    return history


def chronological_holdout(
    daily: pd.DataFrame,
    horizon_days: int = 30,
    minimum_history_days: int = 30,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.Timestamp]:
    """Split a complete panel at one shared origin for honest backtesting."""
    if horizon_days <= 0 or minimum_history_days <= 0:
        raise ValueError("horizon_days and minimum_history_days must be positive")
    history = validate_daily_history(daily)
    dates = history["date"].drop_duplicates().sort_values()
    if len(dates) < horizon_days + minimum_history_days:
        raise ValueError(
            f"Need at least {horizon_days + minimum_history_days} dates; found {len(dates)}"
        )
    test_start = dates.iloc[-horizon_days]
    train = history.loc[history["date"] < test_start].reset_index(drop=True)
    actuals = history.loc[history["date"] >= test_start].reset_index(drop=True)
    origin = test_start - pd.Timedelta(days=1)
    return train, actuals, origin
