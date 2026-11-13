SET search_path TO supply_chain;

CREATE OR REPLACE VIEW vw_product_sales AS
SELECT
    p.product_id,
    p.sku,
    p.product_name,
    p.category,
    COUNT(DISTINCT s.order_id) AS sales_order_count,
    COALESCE(SUM(s.quantity), 0) AS net_units_sold,
    COALESCE(SUM(s.revenue), 0.00) AS total_sales,
    MAX(s.sale_date) AS last_sale_date
FROM products AS p
LEFT JOIN sales AS s ON s.product_id = p.product_id
GROUP BY p.product_id, p.sku, p.product_name, p.category;

CREATE OR REPLACE VIEW vw_inventory_availability AS
WITH ranked_snapshots AS (
    SELECT
        i.*,
        ROW_NUMBER() OVER (
            PARTITION BY i.product_id, i.warehouse_id
            ORDER BY i.snapshot_date DESC
        ) AS snapshot_rank
    FROM inventory_snapshots AS i
), latest AS (
    SELECT * FROM ranked_snapshots WHERE snapshot_rank = 1
)
SELECT
    p.product_id,
    p.sku,
    p.product_name,
    p.category,
    MAX(l.snapshot_date) AS latest_snapshot_date,
    COALESCE(SUM(l.quantity_on_hand), 0) AS quantity_on_hand,
    COALESCE(SUM(l.quantity_reserved), 0) AS quantity_reserved,
    COALESCE(SUM(l.quantity_on_hand - l.quantity_reserved), 0) AS available_quantity,
    COALESCE(SUM(l.reorder_point), 0) AS reorder_point,
    COALESCE(SUM(GREATEST(l.reorder_point + l.safety_stock - (l.quantity_on_hand - l.quantity_reserved), 0)), 0) AS recommended_reorder_quantity,
    CASE
        WHEN COALESCE(SUM(l.quantity_on_hand - l.quantity_reserved), 0) <= 0 THEN 'OUT_OF_STOCK'
        WHEN COALESCE(SUM(l.quantity_on_hand - l.quantity_reserved), 0) <= COALESCE(SUM(l.reorder_point), 0) THEN 'LOW_STOCK'
        ELSE 'IN_STOCK'
    END AS stock_status
FROM products AS p
LEFT JOIN latest AS l ON l.product_id = p.product_id
GROUP BY p.product_id, p.sku, p.product_name, p.category;

CREATE OR REPLACE VIEW vw_monthly_sales AS
SELECT
    DATE_TRUNC('month', s.sale_date)::date AS sales_month,
    COUNT(DISTINCT s.order_id) AS sales_order_count,
    SUM(s.quantity) AS net_units_sold,
    SUM(s.revenue) AS total_sales
FROM sales AS s
GROUP BY DATE_TRUNC('month', s.sale_date)::date;

CREATE OR REPLACE VIEW vw_product_performance AS
SELECT
    ps.product_id,
    ps.sku,
    ps.product_name,
    ps.category,
    ps.sales_order_count,
    ps.net_units_sold,
    ps.total_sales,
    ps.last_sale_date,
    ia.available_quantity,
    ia.recommended_reorder_quantity,
    ia.stock_status,
    DENSE_RANK() OVER (ORDER BY ps.net_units_sold DESC, ps.total_sales DESC) AS sales_rank
FROM vw_product_sales AS ps
LEFT JOIN vw_inventory_availability AS ia ON ia.product_id = ps.product_id;

CREATE OR REPLACE VIEW vw_supplier_performance AS
SELECT
    sp.supplier_id,
    sp.supplier_name,
    COUNT(sh.shipment_id) AS shipment_count,
    COUNT(sh.shipment_id) FILTER (WHERE sh.status = 'delivered') AS delivered_shipments,
    COUNT(sh.shipment_id) FILTER (WHERE sh.status = 'delayed') AS delayed_shipments,
    ROUND(
        100.0 * COUNT(sh.shipment_id) FILTER (
            WHERE sh.status = 'delivered' AND sh.arrival_date <= sh.expected_date
        ) / NULLIF(COUNT(sh.shipment_id) FILTER (WHERE sh.status = 'delivered'), 0),
        2
    ) AS on_time_delivery_rate,
    ROUND(AVG(sh.arrival_date - sh.expected_date) FILTER (WHERE sh.status = 'delivered'), 2) AS average_delivery_variance_days
FROM suppliers AS sp
LEFT JOIN shipments AS sh ON sh.supplier_id = sp.supplier_id
GROUP BY sp.supplier_id, sp.supplier_name;
