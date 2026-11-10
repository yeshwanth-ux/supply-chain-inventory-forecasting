# Day 2 Data Dictionary

Dates use ISO `YYYY-MM-DD`, identifiers are strings, quantities are integers, and money has two decimal places.

| Dataset | Grain | Primary key | Main relationships |
|---|---|---|---|
| products.csv | One product | product_id | supplier_id → suppliers |
| suppliers.csv | One supplier | supplier_id | — |
| inventory.csv | Product/warehouse snapshot | snapshot_date + product_id + warehouse_id | product_id → products |
| orders.csv | One order line | order_id | product_id → products |
| sales.csv | One posted sale/return | sale_id | order_id → orders; product_id → products |
| shipments.csv | One inbound shipment | shipment_id | supplier_id → suppliers; product_id → products |

Returns have negative quantity and revenue. Open shipments have an empty `arrival_date`. This synthetic data is for development and analysis, not operational decisions.
