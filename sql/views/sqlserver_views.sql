USE [$(DatabaseName)];
GO

CREATE OR ALTER VIEW supply_chain.vw_product_sales AS
SELECT p.product_id, p.sku, p.product_name, p.category,
    COUNT(DISTINCT s.order_id) AS sales_order_count,
    COALESCE(SUM(s.quantity), 0) AS net_units_sold,
    COALESCE(SUM(s.revenue), 0.00) AS total_sales,
    MAX(s.sale_date) AS last_sale_date
FROM supply_chain.products AS p
LEFT JOIN supply_chain.sales AS s ON s.product_id = p.product_id
GROUP BY p.product_id, p.sku, p.product_name, p.category;
GO

CREATE OR ALTER VIEW supply_chain.vw_inventory_availability AS
WITH ranked_snapshots AS (
    SELECT i.*, ROW_NUMBER() OVER (
        PARTITION BY i.product_id, i.warehouse_id ORDER BY i.snapshot_date DESC
    ) AS snapshot_rank
    FROM supply_chain.inventory_snapshots AS i
), latest AS (
    SELECT * FROM ranked_snapshots WHERE snapshot_rank = 1
), inventory_totals AS (
    SELECT product_id, MAX(snapshot_date) AS latest_snapshot_date,
        SUM(quantity_on_hand) AS quantity_on_hand,
        SUM(quantity_reserved) AS quantity_reserved,
        SUM(quantity_on_hand - quantity_reserved) AS available_quantity,
        SUM(reorder_point) AS reorder_point,
        SUM(CASE
            WHEN reorder_point + safety_stock > quantity_on_hand - quantity_reserved
            THEN reorder_point + safety_stock - (quantity_on_hand - quantity_reserved)
            ELSE 0
        END) AS recommended_reorder_quantity
    FROM latest GROUP BY product_id
)
SELECT p.product_id, p.sku, p.product_name, p.category,
    i.latest_snapshot_date,
    COALESCE(i.quantity_on_hand, 0) AS quantity_on_hand,
    COALESCE(i.quantity_reserved, 0) AS quantity_reserved,
    COALESCE(i.available_quantity, 0) AS available_quantity,
    COALESCE(i.reorder_point, 0) AS reorder_point,
    COALESCE(i.recommended_reorder_quantity, 0) AS recommended_reorder_quantity,
    CASE
        WHEN COALESCE(i.available_quantity, 0) <= 0 THEN 'OUT_OF_STOCK'
        WHEN COALESCE(i.available_quantity, 0) <= COALESCE(i.reorder_point, 0) THEN 'LOW_STOCK'
        ELSE 'IN_STOCK'
    END AS stock_status
FROM supply_chain.products AS p
LEFT JOIN inventory_totals AS i ON i.product_id = p.product_id;
GO

CREATE OR ALTER VIEW supply_chain.vw_monthly_sales AS
SELECT DATEFROMPARTS(YEAR(s.sale_date), MONTH(s.sale_date), 1) AS sales_month,
    COUNT(DISTINCT s.order_id) AS sales_order_count,
    SUM(s.quantity) AS net_units_sold,
    SUM(s.revenue) AS total_sales
FROM supply_chain.sales AS s
GROUP BY DATEFROMPARTS(YEAR(s.sale_date), MONTH(s.sale_date), 1);
GO

CREATE OR ALTER VIEW supply_chain.vw_product_performance AS
SELECT ps.product_id, ps.sku, ps.product_name, ps.category,
    ps.sales_order_count, ps.net_units_sold, ps.total_sales, ps.last_sale_date,
    ia.available_quantity, ia.recommended_reorder_quantity, ia.stock_status,
    DENSE_RANK() OVER (ORDER BY ps.net_units_sold DESC, ps.total_sales DESC) AS sales_rank
FROM supply_chain.vw_product_sales AS ps
LEFT JOIN supply_chain.vw_inventory_availability AS ia ON ia.product_id = ps.product_id;
GO

CREATE OR ALTER VIEW supply_chain.vw_supplier_performance AS
SELECT sp.supplier_id, sp.supplier_name,
    COUNT(sh.shipment_id) AS shipment_count,
    SUM(CASE WHEN sh.status = 'delivered' THEN 1 ELSE 0 END) AS delivered_shipments,
    SUM(CASE WHEN sh.status = 'delayed' THEN 1 ELSE 0 END) AS delayed_shipments,
    CAST(100.0 * SUM(CASE WHEN sh.status = 'delivered' AND sh.arrival_date <= sh.expected_date THEN 1 ELSE 0 END)
        / NULLIF(SUM(CASE WHEN sh.status = 'delivered' THEN 1 ELSE 0 END), 0) AS DECIMAL(6,2)) AS on_time_delivery_rate,
    CAST(AVG(CASE WHEN sh.status = 'delivered' THEN 1.0 * DATEDIFF(DAY, sh.expected_date, sh.arrival_date) END) AS DECIMAL(8,2)) AS average_delivery_variance_days
FROM supply_chain.suppliers AS sp
LEFT JOIN supply_chain.shipments AS sh ON sh.supplier_id = sp.supplier_id
GROUP BY sp.supplier_id, sp.supplier_name;
GO
