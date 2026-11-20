"""Run and evaluate moving-average and naive baseline demand forecasts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd

from src.analysis.common import load_clean_datasets
from src.forecasting.evaluate import attach_actuals, calculate_metrics
from src.forecasting.predict import FORECAST_HORIZONS, generate_horizon_forecasts
from src.forecasting.prepare import build_daily_demand
from src.forecasting.train import chronological_holdout


def write_baseline_outputs(
    predictions: pd.DataFrame,
    metrics: pd.DataFrame,
    output_dir: Path | str,
    report_path: Path | str,
    metadata: dict[str, Any],
) -> None:
    """Write comparison predictions, horizon files, metrics, metadata, and report."""
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    predictions.to_csv(output / "baseline_predictions.csv", index=False, date_format="%Y-%m-%d")
    for horizon in FORECAST_HORIZONS:
        predictions.loc[predictions["horizon_days"] == horizon].to_csv(
            output / f"baseline_forecast_{horizon}_day.csv",
            index=False,
            date_format="%Y-%m-%d",
        )
    metrics.to_csv(output / "baseline_metrics.csv", index=False)
    (output / "baseline_metadata.json").write_text(
        json.dumps(metadata, indent=2), encoding="utf-8"
    )

    best = metrics.sort_values(["horizon_days", "mae"]).groupby("horizon_days").first()
    lines = [
        "# Day 10 Baseline Forecasting",
        "",
        "## Method",
        "",
        f"The moving-average baseline uses the latest {metadata['moving_average_window']} days. Multi-step forecasts are recursive: each predicted day is appended to history before calculating the next day, so holdout actuals never leak into later predictions.",
        "",
        "The basic comparison model repeats the last observed demand for every future day. Both models use the same forecast origin and are evaluated against the final 30 days of history.",
        "",
        "## Forecast coverage",
        "",
        f"- Forecast origin: {metadata['forecast_origin']}.",
        f"- Products: {metadata['product_count']}.",
        f"- Horizons: {', '.join(str(value) for value in metadata['forecast_horizons'])} days.",
        f"- Saved prediction rows: {metadata['prediction_rows']:,}.",
        "",
        "## Lowest MAE by horizon",
        "",
    ]
    for horizon, row in best.iterrows():
        lines.append(
            f"- {horizon}-day: `{row['model']}` with MAE {row['mae']:.3f} and WAPE {row['wape']:.3f}."
        )
    lines.extend(
        [
            "",
            "## Usage",
            "",
            "Use these deterministic baselines as the minimum benchmark for later forecasting models. Compare models on the same chronological horizons and prefer lower MAE, RMSE, and WAPE while checking mean error for systematic over- or under-forecasting.",
            "",
        ]
    )
    report = Path(report_path)
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text("\n".join(lines), encoding="utf-8")


def run_baseline_forecasting(
    data_dir: Path | str,
    output_dir: Path | str,
    report_path: Path | str,
    moving_average_window: int = 7,
) -> dict[str, Any]:
    """Prepare history, backtest baselines, and save all comparison outputs."""
    if moving_average_window <= 0:
        raise ValueError("moving_average_window must be positive")
    daily = build_daily_demand(load_clean_datasets(data_dir))
    training, actuals, origin = chronological_holdout(
        daily,
        horizon_days=max(FORECAST_HORIZONS),
        minimum_history_days=moving_average_window,
    )
    predictions = generate_horizon_forecasts(
        training,
        origin,
        horizons=FORECAST_HORIZONS,
        moving_average_window=moving_average_window,
    )
    evaluated = attach_actuals(predictions, actuals)
    metrics = calculate_metrics(evaluated)
    metadata = {
        "forecast_origin": origin.strftime("%Y-%m-%d"),
        "actuals_start": actuals["date"].min().strftime("%Y-%m-%d"),
        "actuals_end": actuals["date"].max().strftime("%Y-%m-%d"),
        "product_count": int(training["product_id"].nunique()),
        "moving_average_window": moving_average_window,
        "forecast_horizons": list(FORECAST_HORIZONS),
        "models": sorted(evaluated["model"].unique().tolist()),
        "prediction_rows": int(len(evaluated)),
    }
    write_baseline_outputs(evaluated, metrics, output_dir, report_path, metadata)
    return metadata


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path("data/synthetic"))
    parser.add_argument(
        "--output-dir", type=Path, default=Path("data/processed/forecasting/baseline")
    )
    parser.add_argument("--report", type=Path, default=Path("reports/day10_baseline_forecasting.md"))
    parser.add_argument("--moving-average-window", type=int, default=7)
    args = parser.parse_args()
    print(
        json.dumps(
            run_baseline_forecasting(
                args.data_dir,
                args.output_dir,
                args.report,
                args.moving_average_window,
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
