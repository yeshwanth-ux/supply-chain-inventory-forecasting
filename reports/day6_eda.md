# Day 6 Exploratory Data Analysis

## Scope

The analysis uses synthetic sales and inventory data. Returns reduce units and sales. The final partial month is excluded from peak, low, and seasonal comparisons.

## Business insights

- Net sales total $661,174.71 across 4,546 net units.
- 2025-08 has the highest complete-month demand at 460 units. 2025-09 has the lowest at 301 units.
- Complete-month demand varies by 10.3% relative to its mean. Only 12 complete months are available, so the data does not establish a recurring seasonal pattern.
- Product 026 (PRD0026) leads demand with 227 net units. The top five products contribute 23.7% of net units.
- 2 products are below their combined reorder points and 0 are out of stock.

## Top products

| Product | Net units | Net sales |
|---|---:|---:|
| Product 026 (PRD0026) | 227 | $49,320.29 |
| Product 007 (PRD0007) | 226 | $25,149.28 |
| Product 022 (PRD0022) | 223 | $55,143.44 |
| Product 016 (PRD0016) | 211 | $46,415.78 |
| Product 027 (PRD0027) | 191 | $35,025.58 |

## Stock attention

| Product | Available units | Reorder point | Status |
|---|---:|---:|---|
| Product 011 (PRD0011) | 83 | 166 | LOW_STOCK |
| Product 022 (PRD0022) | 135 | 140 | LOW_STOCK |

## Interpretation

Prioritize replenishment for Product 022 (PRD0022), which combines top-five demand with low stock. Add at least two full years of observed demand before treating month-of-year differences as seasonality.
