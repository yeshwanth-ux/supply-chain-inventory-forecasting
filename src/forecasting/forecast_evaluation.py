"""Evaluate trained forecasting models and save the selected production model."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import joblib
import pandas as pd

from src.analysis.common import load_clean_datasets
from src.features.feature_engineering import MODEL_FEATURES
from src.forecasting.evaluate import (
    calculate_model_metrics,
    reshape_model_predictions,
    select_best_model,
)
from src.forecasting.ml_models import RANDOM_STATE, train_and_evaluate_models
from src.forecasting.prepare import build_daily_demand, split_forecasting_data


def save_best_model_bundle(
    model: Any,
    model_name: str,
    metrics: pd.DataFrame,
    destination: Path | str,
    metadata: dict[str, Any],
) -> None:
    """Serialize the selected estimator with its feature and evaluation contract."""
    selected_metrics = metrics.loc[metrics["model"] == model_name].iloc[0].to_dict()
    bundle = {
        "model_name": model_name,
        "estimator": model,
        "feature_columns": list(MODEL_FEATURES),
        "target_column": "demand",
        "prediction_floor": 0.0,
        "evaluation_metrics": selected_metrics,
        "metadata": metadata,
    }
    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(bundle, path)


def write_evaluation_outputs(
    comparison: pd.DataFrame,
    metrics: pd.DataFrame,
    output_dir: Path | str,
    report_path: Path | str,
    metadata: dict[str, Any],
) -> None:
    """Write evaluation tables, selection metadata, and a Markdown report."""
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    comparison.to_csv(
        output / "actual_vs_predicted.csv", index=False, date_format="%Y-%m-%d"
    )
    metrics.to_csv(output / "forecast_model_comparison.csv", index=False)
    (output / "forecast_evaluation_metadata.json").write_text(
        json.dumps(metadata, indent=2), encoding="utf-8"
    )

    winner = metrics.loc[metrics["model"] == metadata["best_model"]].iloc[0]
    lines = [
        "# Day 12 Forecast Evaluation",
        "",
        "## Evaluation method",
        "",
        f"Random Forest and Gradient Boosting are compared on the same {metadata['testing_rows']:,} product-date observations from {metadata['testing_start']} through {metadata['testing_end']}. Lower MAE, RMSE, and WAPE indicate better accuracy. Forecast bias is predicted demand minus actual demand, so positive values indicate over-forecasting and negative values indicate under-forecasting.",
        "",
        "## Model comparison",
        "",
        "| Model | MAE | RMSE | WAPE | Bias | Bias % |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in metrics.itertuples(index=False):
        lines.append(
            f"| {row.model} | {row.mae:.4f} | {row.rmse:.4f} | {row.wape:.4f} | {row.forecast_bias:.4f} | {row.forecast_bias_percent:.2%} |"
        )
    lines.extend(
        [
            "",
            "## Selected model",
            "",
            f"`{metadata['best_model']}` is selected because it has the lowest MAE ({winner['mae']:.4f}). Its RMSE is {winner['rmse']:.4f}, WAPE is {winner['wape']:.4f}, and average forecast bias is {winner['forecast_bias']:.4f} units.",
            "",
            f"The selected estimator is saved as `{metadata['model_file']}` with its ordered feature list, target definition, prediction floor, evaluation metrics, and training metadata. Future prediction code must supply all {len(MODEL_FEATURES)} features in the saved order.",
            "",
        ]
    )
    report = Path(report_path)
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text("\n".join(lines), encoding="utf-8")


def run_forecast_evaluation(
    data_dir: Path | str,
    output_dir: Path | str,
    model_path: Path | str,
    report_path: Path | str,
    test_days: int = 30,
    validation_days: int = 30,
) -> dict[str, Any]:
    """Retrain, evaluate, select, and save the best forecasting model."""
    daily = build_daily_demand(load_clean_datasets(data_dir))
    _, training, testing, _ = split_forecasting_data(daily, test_days=test_days)
    models, wide_predictions, _, _, _ = train_and_evaluate_models(
        training, testing, validation_days
    )
    comparison = reshape_model_predictions(wide_predictions)
    metrics = calculate_model_metrics(comparison)
    best_model = select_best_model(metrics)
    destination = Path(model_path)
    metadata = {
        "random_state": RANDOM_STATE,
        "best_model": best_model,
        "selection_metric": "mae",
        "training_rows": int(len(training)),
        "testing_rows": int(len(testing)),
        "training_end": training["date"].max().strftime("%Y-%m-%d"),
        "testing_start": testing["date"].min().strftime("%Y-%m-%d"),
        "testing_end": testing["date"].max().strftime("%Y-%m-%d"),
        "validation_days": validation_days,
        "feature_columns": list(MODEL_FEATURES),
        "model_file": destination.as_posix(),
    }
    save_best_model_bundle(
        models[best_model], best_model, metrics, destination, metadata
    )
    write_evaluation_outputs(comparison, metrics, output_dir, report_path, metadata)
    return metadata


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path("data/synthetic"))
    parser.add_argument(
        "--output-dir", type=Path, default=Path("data/processed/forecasting/evaluation")
    )
    parser.add_argument(
        "--model-path", type=Path, default=Path("models/day12/best_forecasting_model.joblib")
    )
    parser.add_argument("--report", type=Path, default=Path("reports/day12_forecast_evaluation.md"))
    parser.add_argument("--test-days", type=int, default=30)
    parser.add_argument("--validation-days", type=int, default=30)
    args = parser.parse_args()
    print(
        json.dumps(
            run_forecast_evaluation(
                args.data_dir,
                args.output_dir,
                args.model_path,
                args.report,
                args.test_days,
                args.validation_days,
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
