"""Generate deterministic baseline demand forecasts."""

from __future__ import annotations

from collections.abc import Iterable

import numpy as np
import pandas as pd

from src.forecasting.train import validate_daily_history


FORECAST_HORIZONS = (7, 14, 30)
BASELINE_MODELS = ("moving_average", "last_observation")


def _recursive_forecast(values: list[float], horizon_days: int, window_days: int) -> list[float]:
    """Forecast recursively so multi-step predictions never use future actual demand."""
    forecasts: list[float] = []
    working_history = values.copy()
    for _ in range(horizon_days):
        prediction = float(np.mean(working_history[-window_days:]))
        forecasts.append(prediction)
        working_history.append(prediction)
    return forecasts


def forecast_baselines(
    history: pd.DataFrame,
    origin_date: pd.Timestamp | str,
    horizon_days: int,
    moving_average_window: int = 7,
) -> pd.DataFrame:
    """Create moving-average and last-observation forecasts for every product."""
    if horizon_days <= 0 or moving_average_window <= 0:
        raise ValueError("horizon_days and moving_average_window must be positive")
    panel = validate_daily_history(history)
    origin = pd.Timestamp(origin_date)
    if panel["date"].max() != origin:
        raise ValueError("origin_date must equal the final history date")

    records: list[dict[str, object]] = []
    for product_id, group in panel.groupby("product_id", sort=True):
        values = group["demand"].astype(float).tolist()
        if len(values) < moving_average_window:
            raise ValueError(
                f"Product {product_id} has fewer than {moving_average_window} history days"
            )
        model_predictions = {
            "moving_average": _recursive_forecast(
                values, horizon_days, moving_average_window
            ),
            "last_observation": [values[-1]] * horizon_days,
        }
        for model_name, predictions in model_predictions.items():
            for step, prediction in enumerate(predictions, start=1):
                records.append(
                    {
                        "model": model_name,
                        "product_id": product_id,
                        "origin_date": origin,
                        "forecast_date": origin + pd.Timedelta(days=step),
                        "forecast_day": step,
                        "horizon_days": horizon_days,
                        "predicted_demand": max(0.0, prediction),
                    }
                )
    return pd.DataFrame.from_records(records)


def generate_horizon_forecasts(
    history: pd.DataFrame,
    origin_date: pd.Timestamp | str,
    horizons: Iterable[int] = FORECAST_HORIZONS,
    moving_average_window: int = 7,
) -> pd.DataFrame:
    """Generate a comparable long-form forecast table for each requested horizon."""
    requested = tuple(horizons)
    if not requested or any(horizon <= 0 for horizon in requested):
        raise ValueError("At least one positive forecast horizon is required")
    frames = [
        forecast_baselines(history, origin_date, horizon, moving_average_window)
        for horizon in requested
    ]
    return pd.concat(frames, ignore_index=True)
