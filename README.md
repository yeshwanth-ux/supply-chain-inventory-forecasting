# Supply Chain Inventory Forecasting

Starter scaffold for demand forecasting, inventory analysis, and replenishment planning.

## Status

Data collection, database setup, Pandas ETL, and SQL reporting analysis are implemented. Forecasting and Airflow components remain placeholders.

## Structure

- data/raw, data/processed, data/synthetic: input, cleaned, and generated datasets
- notebooks: exploration, inventory analysis, and forecasting starter notebooks
- src/data: ingestion and cleaning
- src/database: PostgreSQL and SQL Server helpers
- src/features: feature engineering
- src/forecasting: training, prediction, and evaluation
- src/inventory: replenishment
- src/pipeline: pipeline entry point
- sql/schema, sql/queries, sql/views: SQL definitions
- airflow/dags: scheduling placeholder
- powerbi: planned measures and data model
- models, reports/figures: generated artifacts
- tests, config: future tests and configuration
- docker/Dockerfile and docker-compose.yml: scaffold container

Empty directories contain .gitkeep files; Python packages contain __init__.py.

## Setup (PowerShell)

Use Python 3.11 or later, from the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python -m src.pipeline.run_pipeline
```

Configure .env before implementing database connections. SQL Server requires an appropriate system ODBC driver. Launch notebooks with `jupyter lab`.

After creating .env, run `docker compose up --build` to execute the scaffold entry point. It prints a status message and exits. Database and Airflow services are not configured. Install Airflow separately using constraints for your chosen Python and Airflow versions.

## Next steps

Define data contracts and SQL schemas, implement ingestion and cleaning, build forecasting baselines with chronological validation, implement replenishment, then connect pipeline stages and add tests and scheduling.

Local secrets, datasets, model outputs, and generated figures are ignored by Git.

## Day 2: data collection

Generate and validate the development datasets from the repository root:

```powershell
py -m src.data.generate_synthetic --output-dir data/synthetic --seed 42
```

This creates `products.csv`, `suppliers.csv`, `inventory.csv`, `orders.csv`, `sales.csv`, and `shipments.csv`. The fixed seed makes output reproducible. See `config/data_dictionary.md` for grain and relationships. Place unchanged external sources in `data/raw`; local dataset contents remain ignored to avoid committing sensitive or large files.

Run tests with `py -m unittest discover -s tests -v`.
## Day 3: database setup

Copy `.env.example` to `.env`, replace both example passwords, and start the databases:

```powershell
Copy-Item .env.example .env
docker compose up -d postgres sqlserver sqlserver-init
docker compose ps
```

PostgreSQL initializes `sql/schema/postgres.sql` on its first empty data volume. The one-shot `sqlserver-init` service waits for SQL Server and applies `sql/schema/sqlserver.sql`. Both schemas contain suppliers, products, warehouses, inventory snapshots, customer orders, sales, and shipments with primary keys, foreign keys, checks, and query indexes.

Python connections are provided by `src.database.postgres.create_postgres_engine` and `src.database.sqlserver.create_sqlserver_engine`. SQL Server also requires Microsoft ODBC Driver 18 when Python runs directly on the host. Use each module's `check_connection` helper for a live connectivity check.

```powershell
py -m src.database.check_connections --database both
```

To recreate databases from scratch, stop the services and explicitly remove their named volumes before starting them again. This deletes database contents, so only do it when the stored data is disposable.

## Day 4: data cleaning and ETL

Run extraction, cleaning, and processed CSV output with:

```powershell
py -m src.pipeline.run_etl --input-dir data/synthetic --output-dir data/processed
```

The pipeline standardizes column names, IDs, dates, statuses, integers, and monetary fields. It fills optional inventory reservations, removes records with invalid required values, keeps the latest duplicate primary key, removes orphaned foreign-key rows, and writes `data/processed/etl_report.json` with quality counts.

After the PostgreSQL schema is initialized and `.env` contains valid credentials, load the cleaned data with idempotent upserts:

```powershell
py -m src.pipeline.run_etl --input-dir data/synthetic --output-dir data/processed --load-postgres
```

Tables are loaded in dependency order inside a transaction. Existing primary keys are updated, allowing safe reruns without duplicate records.

## Day 5: SQL analysis

Reporting views are defined for both databases:

- `vw_product_sales`: sales, demand, returns, and last sale by product
- `vw_inventory_availability`: latest stock, availability, status, and recommended reorder quantity
- `vw_monthly_sales`: monthly sales and unit trend
- `vw_product_performance`: combined sales and inventory ranking
- `vw_supplier_performance`: delivery counts, on-time rate, and schedule variance

PostgreSQL queries are in `sql/queries/postgres_analysis.sql`; SQL Server queries are in `sql/queries/sqlserver_analysis.sql`. They cover total sales and demand, stock availability, top-selling and slow-moving products, monthly trends, and inventory valuation.

Fresh Docker database volumes create the views automatically. For an existing PostgreSQL database, apply `sql/views/postgres_views.sql` with `psql`. For an existing SQL Server database, run `sql/views/sqlserver_views.sql` with SQLCMD mode enabled and supply the `DatabaseName` variable.
