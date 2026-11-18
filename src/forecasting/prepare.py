"""Prepare complete daily demand history and chronological model datasets."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd

from src.analysis.common import load_clean_datasets
from src.features.feature_engineering import LAG_DAYS, ROLLING_WINDOWS, add_demand_features


def build_daily_demand(frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Aggregate non-cancelled order demand onto a complete product/date grid."""
    all_orders = frames["orders"].copy()
    orders = all_orders.loc[all_orders["status"] != "cancelled"].copy()
    if orders.empty:
        raise ValueError("No non-cancelled orders are available for demand preparation")
    start_date, end_date = all_orders["order_date"].min(), all_orders["order_date"].max()
    product_ids = frames["products"]["product_id"].sort_values().unique()
    dates = pd.date_range(start_date, end_date, freq="D")
    index = pd.MultiIndex.from_product([product_ids, dates], names=["product_id", "date"])
    aggregated = (
        orders.groupby(["product_id", "order_date"], as_index=True)["quantity"]
        .sum()
        .rename_axis(["product_id", "date"])
        .rename("demand")
    )
    daily = aggregated.reindex(index, fill_value=0).reset_index()
    daily["demand"] = pd.to_numeric(daily["demand"], errors="raise").astype("int64")
    if (daily["demand"] < 0).any():
        raise ValueError("Daily demand cannot be negative")
    return daily.merge(
        frames["products"][["product_id", "sku", "product_name", "category"]],
        on="product_id",
        how="left",
        validate="many_to_one",
    )


def split_forecasting_data(
    daily_demand: pd.DataFrame,
    test_days: int = 30,
    minimum_training_days: int = 90,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    """Add past-only features and split every product at one date cutoff."""
    if test_days <= 0 or minimum_training_days <= 0:
        raise ValueError("test_days and minimum_training_days must be positive")
    unique_dates = daily_demand["date"].sort_values().unique()
    if len(unique_dates) < test_days + minimum_training_days:
        raise ValueError(
            f"Need at least {test_days + minimum_training_days} daily observations; found {len(unique_dates)}"
        )
    featured = add_demand_features(daily_demand)
    required_features = [
        *(f"demand_lag_{lag}" for lag in LAG_DAYS),
        *(f"demand_rolling_mean_{window}" for window in ROLLING_WINDOWS),
        *(f"demand_rolling_std_{window}" for window in ROLLING_WINDOWS),
    ]
    model_data = featured.dropna(subset=required_features).reset_index(drop=True)
    test_start = pd.Timestamp(unique_dates[-test_days])
    training = model_data.loc[model_data["date"] < test_start].reset_index(drop=True)
    testing = model_data.loc[model_data["date"] >= test_start].reset_index(drop=True)
    if training.empty or testing.empty:
        raise ValueError("Chronological split produced an empty training or testing dataset")
    if training["date"].max() >= testing["date"].min():
        raise AssertionError("Training and testing dates overlap")
    expected_products = set(daily_demand["product_id"])
    if set(training["product_id"]) != expected_products or set(testing["product_id"]) != expected_products:
        raise ValueError("Every product must appear in both training and testing datasets")

    metadata = {
        "frequency": "daily",
        "demand_definition": "non-cancelled customer order quantity",
        "history_start": daily_demand["date"].min().strftime("%Y-%m-%d"),
        "history_end": daily_demand["date"].max().strftime("%Y-%m-%d"),
        "product_count": int(daily_demand["product_id"].nunique()),
        "history_rows": int(len(daily_demand)),
        "zero_demand_rows": int((daily_demand["demand"] == 0).sum()),
        "model_rows": int(len(model_data)),
        "training_rows": int(len(training)),
        "testing_rows": int(len(testing)),
        "training_end": training["date"].max().strftime("%Y-%m-%d"),
        "testing_start": testing["date"].min().strftime("%Y-%m-%d"),
        "testing_end": testing["date"].max().strftime("%Y-%m-%d"),
        "test_days": test_days,
        "minimum_training_days": minimum_training_days,
        "maximum_lag_days": max(LAG_DAYS),
    }
    return model_data, training, testing, metadata


def write_forecasting_outputs(
    daily: pd.DataFrame,
    model_data: pd.DataFrame,
    training: pd.DataFrame,
    testing: pd.DataFrame,
    metadata: dict[str, Any],
    output_dir: Path | str,
    report_path: Path | str,
) -> None:
    """Write reproducible CSV datasets, metadata, and a Markdown report."""
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    daily.to_csv(output / "daily_demand.csv", index=False, date_format="%Y-%m-%d")
    model_data.to_csv(output / "model_data.csv", index=False, date_format="%Y-%m-%d")
    training.to_csv(output / "train.csv", index=False, date_format="%Y-%m-%d")
    testing.to_csv(output / "test.csv", index=False, date_format="%Y-%m-%d")
    (output / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    report = Path(report_path)
    report.parent.mkdir(parents=True, exist_ok=True)
    missing_dates_filled = metadata["zero_demand_rows"]
    lines = [
        "# Day 8 Demand Forecasting Preparation",
        "",
        "## Demand definition",
        "",
        "Daily demand is the sum of non-cancelled customer-order quantities. Returned orders remain historical demand because customers originally requested those units. Cancelled orders are excluded.",
        "",
        "## Prepared data",
        "",
        f"- History: {metadata['history_start']} through {metadata['history_end']} at daily frequency.",
        f"- Products: {metadata['product_count']}.",
        f"- Complete product/date rows: {metadata['history_rows']:,}.",
        f"- Product/date rows filled with zero demand: {missing_dates_filled:,}.",
        f"- Model-ready rows after the {metadata['maximum_lag_days']}-day warm-up: {metadata['model_rows']:,}.",
        "",
        "## Chronological split",
        "",
        f"- Training: {metadata['training_rows']:,} rows through {metadata['training_end']}.",
        f"- Testing: {metadata['testing_rows']:,} rows from {metadata['testing_start']} through {metadata['testing_end']}.",
        f"- Holdout length: {metadata['test_days']} days for every product.",
        "",
        "## Model features",
        "",
        "Calendar features include weekday, month, quarter, day of year, and weekend status. Demand features include 1, 7, 14, and 28-day lags plus 7 and 28-day trailing means and standard deviations. Every demand feature uses only earlier dates.",
        "",
        "## Modeling notes",
        "",
        "Use the test set only for final chronological evaluation. Fit preprocessing and models on the training set. For multi-step forecasts, generate lag features recursively or from known history rather than using future observed demand.",
        "",
    ]
    report.write_text("\n".join(lines), encoding="utf-8")


def run_preparation(
    data_dir: Path | str,
    output_dir: Path | str,
    report_path: Path | str,
    test_days: int = 30,
    minimum_training_days: int = 90,
) -> dict[str, Any]:
    """Run the complete demand preparation workflow."""
    frames = load_clean_datasets(data_dir)
    daily = build_daily_demand(frames)
    model_data, training, testing, metadata = split_forecasting_data(
        daily, test_days, minimum_training_days
    )
    write_forecasting_outputs(
        daily, model_data, training, testing, metadata, output_dir, report_path
    )
    return metadata


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path("data/synthetic"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/processed/forecasting"))
    parser.add_argument("--report", type=Path, default=Path("reports/day8_forecasting_preparation.md"))
    parser.add_argument("--test-days", type=int, default=30)
    parser.add_argument("--minimum-training-days", type=int, default=90)
    args = parser.parse_args()
    print(json.dumps(run_preparation(
        args.data_dir,
        args.output_dir,
        args.report,
        args.test_days,
        args.minimum_training_days,
    ), indent=2))


if __name__ == "__main__":
    main()
