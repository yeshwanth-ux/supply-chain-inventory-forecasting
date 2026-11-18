# Day 8 Demand Forecasting Preparation

## Demand definition

Daily demand is the sum of non-cancelled customer-order quantities. Returned orders remain historical demand because customers originally requested those units. Cancelled orders are excluded.

## Prepared data

- History: 2025-01-01 through 2025-12-31 at daily frequency.
- Products: 30.
- Complete product/date rows: 10,950.
- Product/date rows filled with zero demand: 10,096.
- Model-ready rows after the 28-day warm-up: 10,110.

## Chronological split

- Training: 9,210 rows through 2025-12-01.
- Testing: 900 rows from 2025-12-02 through 2025-12-31.
- Holdout length: 30 days for every product.

## Model features

Calendar features include weekday, month, quarter, day of year, and weekend status. Demand features include 1, 7, 14, and 28-day lags plus 7 and 28-day trailing means and standard deviations. Every demand feature uses only earlier dates.

## Modeling notes

Use the test set only for final chronological evaluation. Fit preprocessing and models on the training set. For multi-step forecasts, generate lag features recursively or from known history rather than using future observed demand.
