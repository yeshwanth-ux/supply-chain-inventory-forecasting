IF DB_ID(N'$(DatabaseName)') IS NULL
BEGIN
    EXEC(N'CREATE DATABASE [' + N'$(DatabaseName)' + N']');
END;
GO
USE [$(DatabaseName)];
GO
IF SCHEMA_ID(N'supply_chain') IS NULL EXEC(N'CREATE SCHEMA supply_chain');
GO

IF OBJECT_ID(N'supply_chain.suppliers', N'U') IS NULL CREATE TABLE supply_chain.suppliers (
    supplier_id VARCHAR(20) PRIMARY KEY, supplier_name VARCHAR(150) NOT NULL,
    country VARCHAR(100) NOT NULL, lead_time_days INT NOT NULL CHECK (lead_time_days >= 0),
    reliability_score DECIMAL(5,4) NOT NULL CHECK (reliability_score BETWEEN 0 AND 1)
);
IF OBJECT_ID(N'supply_chain.products', N'U') IS NULL CREATE TABLE supply_chain.products (
    product_id VARCHAR(20) PRIMARY KEY, sku VARCHAR(50) NOT NULL UNIQUE,
    product_name VARCHAR(150) NOT NULL, category VARCHAR(100) NOT NULL,
    supplier_id VARCHAR(20) NOT NULL REFERENCES supply_chain.suppliers(supplier_id),
    unit_cost DECIMAL(12,2) NOT NULL CHECK (unit_cost >= 0), unit_price DECIMAL(12,2) NOT NULL CHECK (unit_price >= 0)
);
IF OBJECT_ID(N'supply_chain.warehouses', N'U') IS NULL CREATE TABLE supply_chain.warehouses (
    warehouse_id VARCHAR(20) PRIMARY KEY, warehouse_name VARCHAR(150) NOT NULL, location VARCHAR(200) NOT NULL
);
IF OBJECT_ID(N'supply_chain.inventory_snapshots', N'U') IS NULL CREATE TABLE supply_chain.inventory_snapshots (
    snapshot_date DATE NOT NULL, product_id VARCHAR(20) NOT NULL REFERENCES supply_chain.products(product_id),
    warehouse_id VARCHAR(20) NOT NULL REFERENCES supply_chain.warehouses(warehouse_id),
    quantity_on_hand INT NOT NULL CHECK (quantity_on_hand >= 0), quantity_reserved INT NOT NULL DEFAULT 0 CHECK (quantity_reserved >= 0),
    reorder_point INT NOT NULL CHECK (reorder_point >= 0), safety_stock INT NOT NULL CHECK (safety_stock >= 0),
    CONSTRAINT pk_inventory_snapshots PRIMARY KEY (snapshot_date, product_id, warehouse_id)
);
IF OBJECT_ID(N'supply_chain.customer_orders', N'U') IS NULL CREATE TABLE supply_chain.customer_orders (
    order_id VARCHAR(20) PRIMARY KEY, order_date DATE NOT NULL, customer_id VARCHAR(20) NOT NULL,
    product_id VARCHAR(20) NOT NULL REFERENCES supply_chain.products(product_id), quantity INT NOT NULL CHECK (quantity > 0),
    unit_price DECIMAL(12,2) NOT NULL CHECK (unit_price >= 0), status VARCHAR(20) NOT NULL CHECK (status IN ('completed','cancelled','returned'))
);
IF OBJECT_ID(N'supply_chain.sales', N'U') IS NULL CREATE TABLE supply_chain.sales (
    sale_id VARCHAR(20) PRIMARY KEY, order_id VARCHAR(20) NOT NULL REFERENCES supply_chain.customer_orders(order_id),
    sale_date DATE NOT NULL, product_id VARCHAR(20) NOT NULL REFERENCES supply_chain.products(product_id),
    quantity INT NOT NULL CHECK (quantity <> 0), revenue DECIMAL(14,2) NOT NULL
);
IF OBJECT_ID(N'supply_chain.shipments', N'U') IS NULL CREATE TABLE supply_chain.shipments (
    shipment_id VARCHAR(20) PRIMARY KEY, supplier_id VARCHAR(20) NOT NULL REFERENCES supply_chain.suppliers(supplier_id),
    product_id VARCHAR(20) NOT NULL REFERENCES supply_chain.products(product_id), order_date DATE NOT NULL,
    expected_date DATE NOT NULL, arrival_date DATE NULL, quantity INT NOT NULL CHECK (quantity > 0),
    status VARCHAR(20) NOT NULL CHECK (status IN ('delivered','in_transit','delayed')), CHECK (expected_date >= order_date)
);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'ix_orders_product_date') CREATE INDEX ix_orders_product_date ON supply_chain.customer_orders(product_id, order_date);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'ix_sales_product_date') CREATE INDEX ix_sales_product_date ON supply_chain.sales(product_id, sale_date);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'ix_shipments_product_expected') CREATE INDEX ix_shipments_product_expected ON supply_chain.shipments(product_id, expected_date);
GO

IF NOT EXISTS (SELECT 1 FROM supply_chain.warehouses WHERE warehouse_id = 'WH001')
INSERT INTO supply_chain.warehouses (warehouse_id, warehouse_name, location) VALUES
('WH001','East Warehouse','New York, NY'), ('WH002','Central Warehouse','Chicago, IL'), ('WH003','West Warehouse','Los Angeles, CA');
GO
