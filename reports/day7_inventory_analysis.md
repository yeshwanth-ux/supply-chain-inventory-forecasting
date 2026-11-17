# Day 7 Inventory Analysis

## Scope and definitions

The analysis uses the latest warehouse snapshot as of 2025-12-31. Available stock equals on-hand less reserved units.
Turnover is an annualized unit-demand/current on-hand proxy over 362 observed days. Average inventory is unavailable, so this is not the standard cost-of-goods-sold/average-inventory ratio.
Slow-moving means turnover below 1.0 or no net demand in the last 90 days. Excess inventory exceeds both reorder plus safety stock and 180 days of demand cover.

## Inventory position

- On-hand inventory: 13,698 units.
- Reserved inventory: 926 units.
- Available inventory: 12,772 units.
- Low-stock products: 2.
- High or out-of-stock risk products: 2.
- Slow-moving products: 29.
- Excess-inventory products: 25, representing $527,781.92 of estimated excess cost.

## Products requiring review

| Product | Available | Turnover proxy | Days of supply | Low stock | Slow moving | Excess units | Stockout risk |
|---|---:|---:|---:|---|---|---:|---|
| Product 011 (PRD0011) | 83 | 0.74 | 338 | Yes | Yes | 0 | HIGH |
| Product 022 (PRD0022) | 135 | 1.26 | 219 | Yes | No | 0 | HIGH |
| Product 012 (PRD0012) | 199 | 0.25 | 1310 | No | Yes | 0 | MEDIUM |
| Product 019 (PRD0019) | 287 | 0.49 | 666 | No | Yes | 0 | MEDIUM |
| Product 026 (PRD0026) | 302 | 0.72 | 482 | No | Yes | 0 | MEDIUM |
| Product 006 (PRD0006) | 268 | 0.37 | 836 | No | Yes | 7 | LOW |
| Product 008 (PRD0008) | 301 | 0.19 | 1651 | No | Yes | 66 | LOW |
| Product 009 (PRD0009) | 311 | 0.43 | 741 | No | Yes | 68 | LOW |
| Product 004 (PRD0004) | 312 | 0.45 | 758 | No | Yes | 92 | LOW |
| Product 005 (PRD0005) | 324 | 0.34 | 977 | No | Yes | 108 | LOW |
| Product 014 (PRD0014) | 356 | 0.42 | 816 | No | Yes | 157 | LOW |
| Product 013 (PRD0013) | 392 | 0.36 | 916 | No | Yes | 100 | LOW |
| Product 025 (PRD0025) | 398 | 0.28 | 1211 | No | Yes | 169 | LOW |
| Product 003 (PRD0003) | 400 | 0.36 | 905 | No | Yes | 207 | LOW |
| Product 002 (PRD0002) | 445 | 0.31 | 1134 | No | Yes | 217 | LOW |

## Recommended actions

1. Review purchase orders and expedite replenishment for high-risk products.
2. Reduce or defer orders for excess and slow-moving products before adding new stock.
3. Add periodic inventory snapshots so future turnover uses average inventory rather than the current-stock proxy.
