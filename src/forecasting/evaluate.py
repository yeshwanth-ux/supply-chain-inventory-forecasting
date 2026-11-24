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


def reshape_model_predictions(predictions: pd.DataFrame) -> pd.DataFrame:
    """Convert wide ML predictions into one comparable row per model and observation."""
    required = {"product_id", "date", "actual_demand"}
    if missing := required - set(predictions.columns):
        raise ValueError(f"Model predictions are missing columns: {sorted(missing)}")
    prediction_columns = sorted(
        column for column in predictions.columns if column.endswith("_prediction")
    )
    if not prediction_columns:
        raise ValueError("Model predictions do not contain any *_prediction columns")
    frame = predictions.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="raise")
    if frame[[*required, *prediction_columns]].isna().any().any():
        raise ValueError("Model predictions contain missing values")
    if frame.duplicated(["product_id", "date"]).any():
        raise ValueError("Model predictions contain duplicate product/date rows")
    long = frame.melt(
        id_vars=["product_id", "date", "actual_demand"],
        value_vars=prediction_columns,
        var_name="model",
        value_name="predicted_demand",
    )
    long["model"] = long["model"].str.removesuffix("_prediction")
    long["error"] = long["predicted_demand"] - long["actual_demand"]
    long["absolute_error"] = long["error"].abs()
    long["squared_error"] = np.square(long["error"])
    return long.sort_values(["date", "product_id", "model"]).reset_index(drop=True)


def calculate_model_metrics(predictions: pd.DataFrame) -> pd.DataFrame:
    """Calculate MAE, RMSE, WAPE, and signed forecast bias for each model."""
    required = {"model", "actual_demand", "predicted_demand"}
    if missing := required - set(predictions.columns):
        raise ValueError(f"Comparable predictions are missing columns: {sorted(missing)}")
    if predictions[list(required)].isna().any().any():
        raise ValueError("Comparable predictions contain missing values")
    rows: list[dict[str, float | int | str]] = []
    for model, group in predictions.groupby("model", sort=True):
        errors = group["predicted_demand"] - group["actual_demand"]
        actual_total = float(group["actual_demand"].abs().sum())
        rows.append(
            {
                "model": model,
                "observations": int(len(group)),
                "mae": float(errors.abs().mean()),
                "rmse": float(np.sqrt(np.mean(np.square(errors)))),
                "wape": float(errors.abs().sum() / actual_total)
                if actual_total
                else np.nan,
                "forecast_bias": float(errors.mean()),
                "forecast_bias_percent": float(errors.sum() / actual_total)
                if actual_total
                else np.nan,
            }
        )
    return pd.DataFrame(rows).sort_values(
        ["mae", "rmse", "wape", "forecast_bias"],
        key=lambda values: values.abs() if values.name == "forecast_bias" else values,
    ).reset_index(drop=True)


def select_best_model(metrics: pd.DataFrame) -> str:
    """Select the model with the lowest MAE, then RMSE, WAPE, and absolute bias."""
    required = {"model", "mae", "rmse", "wape", "forecast_bias"}
    if missing := required - set(metrics.columns):
        raise ValueError(f"Model metrics are missing columns: {sorted(missing)}")
    if metrics.empty or metrics[list(required)].isna().any().any():
        raise ValueError("Model metrics must be complete and non-empty")
    ranked = metrics.assign(absolute_bias=metrics["forecast_bias"].abs()).sort_values(
        ["mae", "rmse", "wape", "absolute_bias", "model"]
    )
    return str(ranked.iloc[0]["model"])
