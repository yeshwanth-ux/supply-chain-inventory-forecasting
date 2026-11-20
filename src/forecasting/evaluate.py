"""Evaluate baseline demand forecasts."""

from __future__ import annotations

import numpy as np
import pandas as pd


def attach_actuals(predictions: pd.DataFrame, actuals: pd.DataFrame) -> pd.DataFrame:
    """Join product/date forecasts to observed demand with strict coverage checks."""
    required_predictions = {"model", "product_id", "forecast_date", "predicted_demand"}
    if missing := required_predictions - set(predictions.columns):
        raise ValueError(f"Predictions are missing columns: {sorted(missing)}")
    required_actuals = {"product_id", "date", "demand"}
    if missing := required_actuals - set(actuals.columns):
        raise ValueError(f"Actuals are missing columns: {sorted(missing)}")
    observed = actuals.loc[:, ["product_id", "date", "demand"]].copy()
    observed["date"] = pd.to_datetime(observed["date"], errors="raise")
    if observed.duplicated(["product_id", "date"]).any():
        raise ValueError("Actuals contain duplicate product/date rows")
    evaluated = predictions.merge(
        observed,
        left_on=["product_id", "forecast_date"],
        right_on=["product_id", "date"],
        how="left",
        validate="many_to_one",
    ).drop(columns="date")
    if evaluated["demand"].isna().any():
        raise ValueError("Actual demand is unavailable for one or more forecast rows")
    return evaluated.rename(columns={"demand": "actual_demand"})


def calculate_metrics(evaluated: pd.DataFrame) -> pd.DataFrame:
    """Calculate MAE, RMSE, bias, and WAPE by model and forecast horizon."""
    required = {"model", "horizon_days", "predicted_demand", "actual_demand"}
    if missing := required - set(evaluated.columns):
        raise ValueError(f"Evaluated predictions are missing columns: {sorted(missing)}")
    rows: list[dict[str, float | int | str]] = []
    for (model, horizon), group in evaluated.groupby(["model", "horizon_days"], sort=True):
        errors = group["predicted_demand"] - group["actual_demand"]
        absolute_actual = group["actual_demand"].abs().sum()
        rows.append(
            {
                "model": model,
                "horizon_days": int(horizon),
                "observations": int(len(group)),
                "mae": float(errors.abs().mean()),
                "rmse": float(np.sqrt(np.mean(np.square(errors)))),
                "mean_error": float(errors.mean()),
                "wape": float(errors.abs().sum() / absolute_actual)
                if absolute_actual
                else np.nan,
            }
        )
    return pd.DataFrame(rows)
