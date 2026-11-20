# Day 10 Baseline Forecasting

## Method

The moving-average baseline uses the latest 7 days. Multi-step forecasts are recursive: each predicted day is appended to history before calculating the next day, so holdout actuals never leak into later predictions.

The basic comparison model repeats the last observed demand for every future day. Both models use the same forecast origin and are evaluated against the final 30 days of history.

## Forecast coverage

- Forecast origin: 2025-12-01.
- Products: 30.
- Horizons: 7, 14, 30 days.
- Saved prediction rows: 3,060.

## Lowest MAE by horizon

- 7-day: `last_observation` with MAE 0.671 and WAPE 1.659.
- 14-day: `last_observation` with MAE 0.743 and WAPE 1.560.
- 30-day: `last_observation` with MAE 0.759 and WAPE 1.488.

## Usage

Use these deterministic baselines as the minimum benchmark for later forecasting models. Compare models on the same chronological horizons and prefer lower MAE, RMSE, and WAPE while checking mean error for systematic over- or under-forecasting.
