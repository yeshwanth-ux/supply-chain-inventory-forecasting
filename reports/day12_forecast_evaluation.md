# Day 12 Forecast Evaluation

## Evaluation method

Random Forest and Gradient Boosting are compared on the same 900 product-date observations from 2025-12-02 through 2025-12-31. Lower MAE, RMSE, and WAPE indicate better accuracy. Forecast bias is predicted demand minus actual demand, so positive values indicate over-forecasting and negative values indicate under-forecasting.

## Model comparison

| Model | MAE | RMSE | WAPE | Bias | Bias % |
| --- | ---: | ---: | ---: | ---: | ---: |
| gradient_boosting | 0.9760 | 2.0899 | 1.9137 | 0.0401 | 7.86% |
| random_forest | 1.0870 | 2.1208 | 2.1313 | 0.1714 | 33.60% |

## Selected model

`gradient_boosting` is selected because it has the lowest MAE (0.9760). Its RMSE is 2.0899, WAPE is 1.9137, and average forecast bias is 0.0401 units.

The selected estimator is saved as `models/day12/best_forecasting_model.joblib` with its ordered feature list, target definition, prediction floor, evaluation metrics, and training metadata. Future prediction code must supply all 25 features in the saved order.
