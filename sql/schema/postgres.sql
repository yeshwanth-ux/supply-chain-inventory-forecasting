CREATE SCHEMA IF NOT EXISTS supply_chain;
SET search_path TO supply_chain;

CREATE TABLE IF NOT EXISTS suppliers (
    supplier_id VARCHAR(20) PRIMARY KEY,
    supplier_name VARCHAR(150) NOT NULL,
    country VARCHAR(100) NOT NULL,
    lead_time_days INTEGER NOT NULL CHECK (lead_time_days >= 0),
    reliability_score NUMERIC(5,4) NOT NULL CHECK (reliability_score BETWEEN 0 AND 1)
);

CREATE TABLE IF NOT EXISTS products (
    product_id VARCHAR(20) PRIMARY KEY,
    sku VARCHAR(50) NOT NULL UNIQUE,
    product_name VARCHAR(150) NOT NULL,
    category VARCHAR(100) NOT NULL,
    supplier_id VARCHAR(20) NOT NULL REFERENCES suppliers(supplier_id),
    unit_cost NUMERIC(12,2) NOT NULL CHECK (unit_cost >= 0),
    unit_price NUMERIC(12,2) NOT NULL CHECK (unit_price >= 0)
);

CREATE TABLE IF NOT EXISTS warehouses (
    warehouse_id VARCHAR(20) PRIMARY KEY,
    warehouse_name VARCHAR(150) NOT NULL,
    location VARCHAR(200) NOT NULL
);

CREATE TABLE IF NOT EXISTS inventory_snapshots (
    snapshot_date DATE NOT NULL,
    product_id VARCHAR(20) NOT NULL REFERENCES products(product_id),
    warehouse_id VARCHAR(20) NOT NULL REFERENCES warehouses(warehouse_id),
    quantity_on_hand INTEGER NOT NULL CHECK (quantity_on_hand >= 0),
    quantity_reserved INTEGER NOT NULL DEFAULT 0 CHECK (quantity_reserved >= 0),
    reorder_point INTEGER NOT NULL CHECK (reorder_point >= 0),
    safety_stock INTEGER NOT NULL CHECK (safety_stock >= 0),
    PRIMARY KEY (snapshot_date, product_id, warehouse_id)
);

CREATE TABLE IF NOT EXISTS customer_orders (
    order_id VARCHAR(20) PRIMARY KEY,
    order_date DATE NOT NULL,
    customer_id VARCHAR(20) NOT NULL,
    product_id VARCHAR(20) NOT NULL REFERENCES products(product_id),
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    unit_price NUMERIC(12,2) NOT NULL CHECK (unit_price >= 0),
    status VARCHAR(20) NOT NULL CHECK (status IN ('completed', 'cancelled', 'returned'))
);

CREATE TABLE IF NOT EXISTS sales (
    sale_id VARCHAR(20) PRIMARY KEY,
    order_id VARCHAR(20) NOT NULL REFERENCES customer_orders(order_id),
    sale_date DATE NOT NULL,
    product_id VARCHAR(20) NOT NULL REFERENCES products(product_id),
    quantity INTEGER NOT NULL CHECK (quantity <> 0),
    revenue NUMERIC(14,2) NOT NULL
);

CREATE TABLE IF NOT EXISTS shipments (
    shipment_id VARCHAR(20) PRIMARY KEY,
    supplier_id VARCHAR(20) NOT NULL REFERENCES suppliers(supplier_id),
    product_id VARCHAR(20) NOT NULL REFERENCES products(product_id),
    order_date DATE NOT NULL,
    expected_date DATE NOT NULL,
    arrival_date DATE NULL,
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    status VARCHAR(20) NOT NULL CHECK (status IN ('delivered', 'in_transit', 'delayed')),
    CHECK (expected_date >= order_date)
);

CREATE INDEX IF NOT EXISTS ix_orders_product_date ON customer_orders(product_id, order_date);
CREATE INDEX IF NOT EXISTS ix_sales_product_date ON sales(product_id, sale_date);
CREATE INDEX IF NOT EXISTS ix_shipments_product_expected ON shipments(product_id, expected_date);

INSERT INTO warehouses (warehouse_id, warehouse_name, location) VALUES
    ('WH001', 'East Warehouse', 'New York, NY'),
    ('WH002', 'Central Warehouse', 'Chicago, IL'),
    ('WH003', 'West Warehouse', 'Los Angeles, CA')
ON CONFLICT (warehouse_id) DO NOTHING;
