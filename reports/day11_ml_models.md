# Day 11 Machine Learning Models

## Training and tuning

Random Forest and Gradient Boosting regressors use 25 leakage-safe demand, product, calendar, and seasonal features. The final 30 training dates form a chronological validation window for parameter tuning. The selected configurations are refitted on all training rows before holdout evaluation.

## Holdout

- Training: 9,150 rows through 2025-12-01.
- Testing: 900 rows from 2025-12-02 through 2025-12-31.
- Test predictions are one-day-ahead forecasts using lag and rolling features available for each date.

## Performance comparison

| Model | MAE | RMSE | WAPE | R² |
| --- | ---: | ---: | ---: | ---: |
| gradient_boosting | 0.9760 | 2.0899 | 1.9137 | -0.0025 |
| random_forest | 1.0870 | 2.1208 | 2.1313 | -0.0325 |

`gradient_boosting` has the lowest holdout MAE at 0.9760.

## Reproducibility

All models use random state 42. Saved outputs include holdout predictions, every tuning candidate, comparison metrics, feature importances, metadata, and serialized fitted models.
