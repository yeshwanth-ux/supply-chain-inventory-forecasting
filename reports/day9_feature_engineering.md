# Day 9 Feature Engineering

## Demand definition

Daily demand is the sum of non-cancelled customer-order quantities. Returned orders remain historical demand because customers originally requested those units. Cancelled orders are excluded.

## Prepared data

- History: 2025-01-01 through 2025-12-31 at daily frequency.
- Products: 30.
- Complete product/date rows: 10,950.
- Product/date rows filled with zero demand: 10,096.
- Model-ready rows after the 30-day warm-up: 10,050.

## Chronological split

- Training: 9,150 rows through 2025-12-01.
- Testing: 900 rows from 2025-12-02 through 2025-12-31.
- Holdout length: 30 days for every product.

## Model features

Calendar features include month, day, weekday, quarter, weekend, cyclical time encodings, and one-hot seasonal indicators. Demand features include previous-day demand, 7-day and 30-day lags, and 7-day and 30-day trailing means and standard deviations. Every demand feature uses only earlier dates.

The final training and testing files contain identifiers, a numeric product code, the target demand, and only model features. The source `product_id` and `date` columns remain available for traceability and chronological evaluation.

## Modeling notes

Use the test set only for final chronological evaluation. Fit preprocessing and models on the training set. For multi-step forecasts, generate lag features recursively or from known history rather than using future observed demand.
