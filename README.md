# Supply Chain Inventory Forecasting

Starter scaffold for demand forecasting, inventory analysis, and replenishment planning.

## Status

Day 2 data collection is implemented with reproducible synthetic products, suppliers, inventory snapshots, orders, sales, and shipments. Forecasting, database, and Airflow components remain placeholders.

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
