# Pricing and Promotion Intelligence System

A reproducible synthetic-data and pricing-rule application for the YottaFlex.ai Associate AI Forward Deployed Engineer Round 2 challenge. Stack: Python, Flask, MySQL, Pandas, NumPy, HTML/CSS/JavaScript, CSV/JSON/SQL, Pytest.

## 1. Prerequisites
- Python 3.11+ recommended
- MySQL 8.x server and MySQL Workbench (or another SQL client)
- VS Code (recommended)

## 2. Setup on Windows
```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```
Edit `.env` and set your local MySQL password. Do not commit `.env`.

## 3. Create database tables
Open `database/schema.sql` in MySQL Workbench and execute it. It creates `pricing_intelligence` and all core and supporting tables. Schema uses foreign keys, checks, enums, and effective-date fields.

## 4. Generate data
Start with a small dataset:
```powershell
python -m generator.generate_data --products 100 --days 30 --promotions 50 --seed 20261022
```
Full requested scale:
```powershell
python -m generator.generate_data --products 5000 --days 180 --promotions 2000 --seed 20261022
```
The full dataset contains 5,000 products and 900,000 product-days each for price history, competitor observations, inventory snapshots, and price decisions, plus costs, promotions, rules, orders and edge cases. The generator streams daily rows in batches to keep memory usage manageable; the full output still requires substantial disk space. Run the starter configuration first. Files are written under `data/`; the manifest is `outputs/run_manifest.json`. To create JSON Lines exports from the generated CSV tables, run `python -m database.export_json`; files are written under `data/json/` and checksums under `outputs/json_export_manifest.json`. To create executable MySQL INSERT seed data from the generated CSVs, run `python -m database.export_csv_sql_seed`; it writes `database/seed.sql`. The included seed file is based on the starter dataset; rerun the exporter after generating another scale.

## 5. Validate and evaluate
```powershell
python -m validation.validate_data
python -m evaluation.evaluate_results
python -m evaluation.reproducibility
pytest -q
```
The ground-truth labels are kept separately in `data/ground_truth.json`. The pricing engine consumes only `edge_case_inputs.csv`; evaluation joins outputs to ground truth afterward.

## 6. Run Flask
```powershell
python app.py
```
Open `http://127.0.0.1:5000`. The dashboard includes a pricing simulator and product search. `/api/health`, `/api/products`, `/api/simulate`, `/api/promotions/validate`, `/api/metrics`, and `/api/exceptions` are available. Product and metrics endpoints require MySQL and imported database records. The simulator can be used without a database connection.

## 7. Current scope and database loading
Import generated CSVs into MySQL in parent-first order:
```powershell
python -m database.import_csvs
```
This loads products first, maps SKU values to MySQL product IDs, then inserts costs, promotions, price history, competitor observations, inventory, orders, rules, decisions and bridge rows. The importer deletes existing rows in child-first order before reloading; use only on this project database. To export SQL INSERT seed data from the loaded database:
```powershell
python -m database.export_sql_seed
```
This writes `database/database_dump.sql` from the current MySQL contents. The CSV-based seed file is generated separately with `python -m database.export_csv_sql_seed`. The project should be run and checked against the target MySQL version before submission.

## API example
```powershell
curl -X POST http://127.0.0.1:5000/api/simulate -H "Content-Type: application/json" -d "{\"cost\":700,\"candidate_price\":1199,\"min_margin_pct\":20,\"price_floor\":875,\"price_ceiling\":1600,\"discount_pct\":10,\"competitor_price\":1099,\"competitor_age_hours\":4,\"stock_on_hand\":8,\"reason\":\"COMPETITOR_REVIEW\"}"
```

## Design notes
- All money fields are INR.
- Margin uses the net price after discount.
- The engine enforces floor/ceiling, stacking, freshness, margin, stock, and reason checks with deterministic precedence.
- No external data is scraped. All data is synthetic.
- See `docs/data_dictionary.md`, `docs/database_relationships.md`, `docs/business_rules.md`, and `docs/source_manifest.md`.
