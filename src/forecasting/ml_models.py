"""Train, tune, evaluate, and save tree-based demand forecasting models."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import ParameterGrid

from src.analysis.common import load_clean_datasets
from src.features.feature_engineering import MODEL_FEATURES
from src.forecasting.prepare import build_daily_demand, split_forecasting_data


RANDOM_STATE = 42
MODEL_CONFIGS: dict[str, dict[str, Any]] = {
    "random_forest": {
        "estimator": RandomForestRegressor,
        "fixed_params": {"random_state": RANDOM_STATE, "n_jobs": -1},
        "parameter_grid": {
            "n_estimators": [80, 160],
            "max_depth": [8, None],
            "min_samples_leaf": [2],
        },
    },
    "gradient_boosting": {
        "estimator": GradientBoostingRegressor,
        "fixed_params": {"random_state": RANDOM_STATE, "loss": "squared_error"},
        "parameter_grid": {
            "n_estimators": [80, 160],
            "learning_rate": [0.03, 0.08],
            "max_depth": [2],
        },
    },
}


def _validate_model_frame(frame: pd.DataFrame, label: str) -> pd.DataFrame:
    required = {"product_id", "date", "demand", *MODEL_FEATURES}
    if missing := required - set(frame.columns):
        raise ValueError(f"{label} data is missing columns: {sorted(missing)}")
    validated = frame.copy()
    validated["date"] = pd.to_datetime(validated["date"], errors="raise")
    if validated[["product_id", "date", "demand", *MODEL_FEATURES]].isna().any().any():
        raise ValueError(f"{label} data contains missing model values")
    if validated.duplicated(["product_id", "date"]).any():
        raise ValueError(f"{label} data contains duplicate product/date rows")
    return validated.sort_values(["date", "product_id"]).reset_index(drop=True)


def split_tuning_data(
    training: pd.DataFrame,
    validation_days: int = 30,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Reserve the latest training dates for chronological parameter tuning."""
    if validation_days <= 0:
        raise ValueError("validation_days must be positive")
    frame = _validate_model_frame(training, "Training")
    dates = frame["date"].drop_duplicates().sort_values()
    if len(dates) <= validation_days:
        raise ValueError("Training history is too short for the requested validation window")
    validation_start = dates.iloc[-validation_days]
    fit = frame.loc[frame["date"] < validation_start].reset_index(drop=True)
    validation = frame.loc[frame["date"] >= validation_start].reset_index(drop=True)
    return fit, validation


def _regression_metrics(actual: pd.Series, predicted: np.ndarray) -> dict[str, float]:
    errors = predicted - actual.to_numpy()
    actual_total = float(actual.abs().sum())
    return {
        "mae": float(mean_absolute_error(actual, predicted)),
        "rmse": float(np.sqrt(mean_squared_error(actual, predicted))),
        "mean_error": float(np.mean(errors)),
        "wape": float(np.sum(np.abs(errors)) / actual_total) if actual_total else np.nan,
        "r2": float(r2_score(actual, predicted)),
    }


def tune_model(
    model_name: str,
    training: pd.DataFrame,
    validation_days: int = 30,
) -> tuple[dict[str, Any], pd.DataFrame]:
    """Tune one model on a date-based validation window using MAE."""
    if model_name not in MODEL_CONFIGS:
        raise ValueError(f"Unsupported model: {model_name}")
    fit, validation = split_tuning_data(training, validation_days)
    config = MODEL_CONFIGS[model_name]
    results: list[dict[str, Any]] = []
    for candidate_number, parameters in enumerate(
        ParameterGrid(config["parameter_grid"]), start=1
    ):
        estimator = config["estimator"](**config["fixed_params"], **parameters)
        estimator.fit(fit.loc[:, MODEL_FEATURES], fit["demand"])
        prediction = np.clip(estimator.predict(validation.loc[:, MODEL_FEATURES]), 0, None)
        results.append(
            {
                "model": model_name,
                "candidate": candidate_number,
                "parameters": json.dumps(parameters, sort_keys=True),
                **_regression_metrics(validation["demand"], prediction),
            }
        )
    tuning = pd.DataFrame(results).sort_values(["mae", "rmse"]).reset_index(drop=True)
    best_parameters = json.loads(tuning.iloc[0]["parameters"])
    return best_parameters, tuning


def train_and_evaluate_models(
    training: pd.DataFrame,
    testing: pd.DataFrame,
    validation_days: int = 30,
) -> tuple[
    dict[str, Any], pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame
]:
    """Tune both models, refit on all training rows, and evaluate the holdout."""
    train = _validate_model_frame(training, "Training")
    test = _validate_model_frame(testing, "Testing")
    if train["date"].max() >= test["date"].min():
        raise ValueError("Training and testing dates must not overlap")

    predictions = test.loc[:, ["product_id", "date", "demand"]].rename(
        columns={"demand": "actual_demand"}
    )
    fitted_models: dict[str, Any] = {}
    tuning_frames: list[pd.DataFrame] = []
    metric_rows: list[dict[str, Any]] = []
    importance_rows: list[dict[str, Any]] = []

    for model_name, config in MODEL_CONFIGS.items():
        best_parameters, tuning = tune_model(model_name, train, validation_days)
        tuning_frames.append(tuning)
        model = config["estimator"](**config["fixed_params"], **best_parameters)
        model.fit(train.loc[:, MODEL_FEATURES], train["demand"])
        predicted = np.clip(model.predict(test.loc[:, MODEL_FEATURES]), 0, None)
        predictions[f"{model_name}_prediction"] = predicted
        metric_rows.append(
            {
                "model": model_name,
                "observations": int(len(test)),
                **_regression_metrics(test["demand"], predicted),
                "best_parameters": json.dumps(best_parameters, sort_keys=True),
            }
        )
        importance_rows.extend(
            {
                "model": model_name,
                "feature": feature,
                "importance": float(importance),
            }
            for feature, importance in zip(MODEL_FEATURES, model.feature_importances_)
        )
        fitted_models[model_name] = model

    metrics = pd.DataFrame(metric_rows).sort_values(["mae", "rmse"]).reset_index(drop=True)
    tuning_results = pd.concat(tuning_frames, ignore_index=True)
    feature_importance = pd.DataFrame(importance_rows).sort_values(
        ["model", "importance"], ascending=[True, False]
    )
    return fitted_models, predictions, metrics, tuning_results, feature_importance


def write_model_outputs(
    models: dict[str, Any],
    predictions: pd.DataFrame,
    metrics: pd.DataFrame,
    tuning_results: pd.DataFrame,
    feature_importance: pd.DataFrame,
    output_dir: Path | str,
    model_dir: Path | str,
    report_path: Path | str,
    metadata: dict[str, Any],
) -> None:
    """Save models, predictions, tuning results, metrics, metadata, and report."""
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    predictions.to_csv(output / "ml_predictions.csv", index=False, date_format="%Y-%m-%d")
    metrics.to_csv(output / "ml_model_metrics.csv", index=False)
    tuning_results.to_csv(output / "ml_tuning_results.csv", index=False)
    feature_importance.to_csv(output / "ml_feature_importance.csv", index=False)
    (output / "ml_metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    saved_models = Path(model_dir)
    saved_models.mkdir(parents=True, exist_ok=True)
    for model_name, model in models.items():
        joblib.dump(model, saved_models / f"{model_name}.joblib")

    winner = metrics.iloc[0]
    lines = [
        "# Day 11 Machine Learning Models",
        "",
        "## Training and tuning",
        "",
        f"Random Forest and Gradient Boosting regressors use {len(MODEL_FEATURES)} leakage-safe demand, product, calendar, and seasonal features. The final {metadata['validation_days']} training dates form a chronological validation window for parameter tuning. The selected configurations are refitted on all training rows before holdout evaluation.",
        "",
        "## Holdout",
        "",
        f"- Training: {metadata['training_rows']:,} rows through {metadata['training_end']}.",
        f"- Testing: {metadata['testing_rows']:,} rows from {metadata['testing_start']} through {metadata['testing_end']}.",
        "- Test predictions are one-day-ahead forecasts using lag and rolling features available for each date.",
        "",
        "## Performance comparison",
        "",
        "| Model | MAE | RMSE | WAPE | R² |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for row in metrics.itertuples(index=False):
        lines.append(
            f"| {row.model} | {row.mae:.4f} | {row.rmse:.4f} | {row.wape:.4f} | {row.r2:.4f} |"
        )
    lines.extend(
        [
            "",
            f"`{winner['model']}` has the lowest holdout MAE at {winner['mae']:.4f}.",
            "",
            "## Reproducibility",
            "",
            f"All models use random state {RANDOM_STATE}. Saved outputs include holdout predictions, every tuning candidate, comparison metrics, feature importances, metadata, and serialized fitted models.",
            "",
        ]
    )
    report = Path(report_path)
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text("\n".join(lines), encoding="utf-8")


def run_ml_training(
    data_dir: Path | str,
    output_dir: Path | str,
    model_dir: Path | str,
    report_path: Path | str,
    test_days: int = 30,
    validation_days: int = 30,
) -> dict[str, Any]:
    """Run the complete tree-based demand-model workflow."""
    daily = build_daily_demand(load_clean_datasets(data_dir))
    _, training, testing, _ = split_forecasting_data(daily, test_days=test_days)
    models, predictions, metrics, tuning, importance = train_and_evaluate_models(
        training, testing, validation_days
    )
    metadata = {
        "random_state": RANDOM_STATE,
        "features": list(MODEL_FEATURES),
        "feature_count": len(MODEL_FEATURES),
        "training_rows": int(len(training)),
        "testing_rows": int(len(testing)),
        "training_end": training["date"].max().strftime("%Y-%m-%d"),
        "testing_start": testing["date"].min().strftime("%Y-%m-%d"),
        "testing_end": testing["date"].max().strftime("%Y-%m-%d"),
        "validation_days": validation_days,
        "best_model": str(metrics.iloc[0]["model"]),
        "best_parameters": {
            row.model: json.loads(row.best_parameters)
            for row in metrics.itertuples(index=False)
        },
    }
    write_model_outputs(
        models,
        predictions,
        metrics,
        tuning,
        importance,
        output_dir,
        model_dir,
        report_path,
        metadata,
    )
    return metadata


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path("data/synthetic"))
    parser.add_argument(
        "--output-dir", type=Path, default=Path("data/processed/forecasting/ml")
    )
    parser.add_argument("--model-dir", type=Path, default=Path("models/day11"))
    parser.add_argument("--report", type=Path, default=Path("reports/day11_ml_models.md"))
    parser.add_argument("--test-days", type=int, default=30)
    parser.add_argument("--validation-days", type=int, default=30)
    args = parser.parse_args()
    print(
        json.dumps(
            run_ml_training(
                args.data_dir,
                args.output_dir,
                args.model_dir,
                args.report,
                args.test_days,
                args.validation_days,
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
