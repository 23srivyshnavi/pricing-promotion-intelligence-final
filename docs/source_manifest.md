# Source manifest and lawful provenance

All generated records in this project are synthetic and created locally with NumPy's seeded random generator. No personal data, confidential data, external retail dataset, or live competitor website is collected. Competitor source URLs are placeholders using `synthetic://competitor-observation`; they are not claims about real market observations. Seed defaults to `20261022`. The generator records configuration, row counts, and SHA-256 checksums in `outputs/run_manifest.json`.

After importing records into MySQL, run `python -m database.export_sql_seed` to export the current database as `database/seed.sql`. `database/schema.sql` defines the schema; `database/import_csvs.py` loads generated CSV data in parent-first order.
