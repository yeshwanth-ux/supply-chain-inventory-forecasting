# Day 14 Supplier and Order Analysis

## Scope

The analysis covers 180 inbound shipment lines through 2025-12-31. Each shipment line represents an inbound purchase-order line because the available dataset does not include a separate purchase-order header identifier.

A shipment is delayed when it arrived after its expected date, remains open after its expected date, or carries a delayed status. Supplier reliability uses four transparent checks: on-time delivery below target, configured reliability below target, actual lead time more than 25% above configured lead time, and open overdue shipments. Unreliable means at least two checks or an on-time rate below 80%; review means one check.

## Overall performance

- Suppliers: 8.
- Delivered shipments: 147.
- Identified delayed shipments: 130, including 33 open overdue shipments.
- Overall on-time delivery rate: 34.0%.
- Average actual lead time: 15.54 days.
- Unreliable suppliers: 8; suppliers requiring review: 0.

## Suppliers requiring action

| Status | Supplier | Shipments | On-time rate | Avg actual lead time | Open overdue | Risk flags |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| UNRELIABLE | Supplier 04 (SUP004) | 27 | 19.0% | 14.48 | 6 | 3 |
| UNRELIABLE | Supplier 01 (SUP001) | 17 | 28.6% | 9.64 | 3 | 3 |
| UNRELIABLE | Supplier 02 (SUP002) | 20 | 37.5% | 15.75 | 4 | 3 |
| UNRELIABLE | Supplier 03 (SUP003) | 32 | 38.5% | 11.31 | 6 | 3 |
| UNRELIABLE | Supplier 08 (SUP008) | 19 | 61.5% | 14.23 | 6 | 3 |
| UNRELIABLE | Supplier 06 (SUP006) | 16 | 15.4% | 21.23 | 3 | 2 |
| UNRELIABLE | Supplier 05 (SUP005) | 31 | 26.9% | 21.04 | 5 | 2 |
| UNRELIABLE | Supplier 07 (SUP007) | 18 | 50.0% | 16.17 | 0 | 1 |

## Recommended actions

1. Escalate open overdue shipments and confirm revised arrival dates.
2. Review unreliable suppliers before assigning new purchase orders.
3. Compare actual lead times with configured lead times during supplier reviews.
4. Recalculate performance after shipment status or arrival-date updates.
