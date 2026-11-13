SET search_path TO supply_chain;

-- 1. Executive sales and demand totals. Returns reduce net units and sales.
SELECT
    (SELECT COALESCE(SUM(revenue), 0.00) FROM sales) AS total_sales,
    (SELECT COALESCE(SUM(quantity), 0) FROM sales) AS net_units_sold,
    (SELECT COUNT(DISTINCT order_id) FROM sales) AS sales_order_count,
    (SELECT COALESCE(SUM(quantity), 0) FROM customer_orders WHERE status <> 'cancelled') AS total_ordered_demand;

-- 2. Current stock availability and recommended replenishment.
SELECT *
FROM vw_inventory_availability
ORDER BY
    CASE stock_status WHEN 'OUT_OF_STOCK' THEN 1 WHEN 'LOW_STOCK' THEN 2 ELSE 3 END,
    available_quantity;

-- 3. Top 10 products by net units sold.
SELECT product_id, sku, product_name, category, net_units_sold, total_sales, sales_rank
FROM vw_product_performance
ORDER BY net_units_sold DESC, total_sales DESC
LIMIT 10;

-- 4. Slow-moving products: no sales or the lowest unit movement.
SELECT product_id, sku, product_name, category, net_units_sold, total_sales, last_sale_date, available_quantity
FROM vw_product_performance
ORDER BY net_units_sold ASC, last_sale_date ASC NULLS FIRST
LIMIT 10;

-- 5. Monthly trend.
SELECT * FROM vw_monthly_sales ORDER BY sales_month;

-- 6. Inventory value using the latest stock position.
SELECT
    SUM(ia.quantity_on_hand * p.unit_cost) AS inventory_cost_value,
    SUM(ia.quantity_on_hand * p.unit_price) AS inventory_retail_value
FROM vw_inventory_availability AS ia
JOIN products AS p ON p.product_id = ia.product_id;
