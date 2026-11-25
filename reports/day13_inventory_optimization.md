# Day 13 Inventory Optimization

## Method

Recommendations use the latest inventory snapshot as of 2025-12-31, a 90-day zero-filled daily demand history, supplier lead times, and a 95% target service level.

Safety stock equals the service factor multiplied by daily demand deviation and the square root of lead time. Reorder point equals expected lead-time demand plus safety stock. Inventory position equals available stock plus undelivered incoming shipments. When inventory position is at or below the reorder point, the recommendation orders up to lead-time demand plus the review period and safety stock.

## Replenishment summary

- Products evaluated: 30.
- Order-now products: 0.
- Products with incoming stock to expedite: 0.
- Products with overdue incoming stock to review: 20.
- Recommended order quantity: 0 units.
- Recommended order value: $0.00.
- Open incoming quantity: 9,688 units, including 9,688 overdue units.

## Automated action queue

| Priority | Product | Available | Incoming | Safety stock | Reorder point | Inventory position | Recommended order | Action |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| MEDIUM | Product 001 (PRD0001) | 551 | 258 | 11 | 16 | 809 | 0 | REVIEW_OVERDUE_INCOMING |
| MEDIUM | Product 002 (PRD0002) | 445 | 1,565 | 15 | 25 | 2,010 | 0 | REVIEW_OVERDUE_INCOMING |
| MEDIUM | Product 003 (PRD0003) | 400 | 285 | 11 | 16 | 685 | 0 | REVIEW_OVERDUE_INCOMING |
| MEDIUM | Product 004 (PRD0004) | 312 | 269 | 11 | 18 | 581 | 0 | REVIEW_OVERDUE_INCOMING |
| MEDIUM | Product 005 (PRD0005) | 324 | 790 | 13 | 20 | 1,114 | 0 | REVIEW_OVERDUE_INCOMING |
| MEDIUM | Product 008 (PRD0008) | 301 | 347 | 11 | 17 | 648 | 0 | REVIEW_OVERDUE_INCOMING |
| MEDIUM | Product 009 (PRD0009) | 311 | 107 | 7 | 10 | 418 | 0 | REVIEW_OVERDUE_INCOMING |
| MEDIUM | Product 011 (PRD0011) | 83 | 465 | 5 | 7 | 548 | 0 | REVIEW_OVERDUE_INCOMING |
| MEDIUM | Product 012 (PRD0012) | 199 | 1,338 | 9 | 12 | 1,537 | 0 | REVIEW_OVERDUE_INCOMING |
| MEDIUM | Product 013 (PRD0013) | 392 | 107 | 22 | 41 | 499 | 0 | REVIEW_OVERDUE_INCOMING |
| MEDIUM | Product 016 (PRD0016) | 454 | 470 | 13 | 21 | 924 | 0 | REVIEW_OVERDUE_INCOMING |
| MEDIUM | Product 019 (PRD0019) | 287 | 730 | 11 | 16 | 1,017 | 0 | REVIEW_OVERDUE_INCOMING |
| MEDIUM | Product 020 (PRD0020) | 619 | 270 | 11 | 17 | 889 | 0 | REVIEW_OVERDUE_INCOMING |
| MEDIUM | Product 021 (PRD0021) | 501 | 345 | 13 | 22 | 846 | 0 | REVIEW_OVERDUE_INCOMING |
| MEDIUM | Product 022 (PRD0022) | 135 | 617 | 19 | 36 | 752 | 0 | REVIEW_OVERDUE_INCOMING |
| MEDIUM | Product 024 (PRD0024) | 473 | 706 | 12 | 18 | 1,179 | 0 | REVIEW_OVERDUE_INCOMING |
| MEDIUM | Product 027 (PRD0027) | 570 | 414 | 15 | 24 | 984 | 0 | REVIEW_OVERDUE_INCOMING |
| MEDIUM | Product 028 (PRD0028) | 505 | 80 | 19 | 32 | 585 | 0 | REVIEW_OVERDUE_INCOMING |
| MEDIUM | Product 029 (PRD0029) | 522 | 54 | 17 | 29 | 576 | 0 | REVIEW_OVERDUE_INCOMING |
| MEDIUM | Product 030 (PRD0030) | 505 | 471 | 16 | 25 | 976 | 0 | REVIEW_OVERDUE_INCOMING |

## Operational notes

Review overdue inbound shipments before placing replacement orders. Recalculate after material demand, lead-time, reservation, or shipment-status changes. Synthetic development data should not be used for live purchasing decisions.
