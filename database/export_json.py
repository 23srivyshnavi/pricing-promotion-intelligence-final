"""Export generated CSV tables to JSON Lines without loading the whole file into memory.
Run: python -m database.export_json
Output: data/json/*.jsonl
"""
import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
JSON_DIR = DATA / "json"
CSV_FILES = [
    "products.csv", "cost_records.csv", "price_history.csv", "competitor_observations.csv",
    "inventory_snapshots.csv", "promotions.csv", "promotion_rules.csv", "promotion_products.csv",
    "orders.csv", "price_decisions.csv", "promotion_applications.csv", "audit_events.csv", "edge_case_inputs.csv",
]

def export():
    JSON_DIR.mkdir(parents=True, exist_ok=True)
    manifest = {"format": "JSON Lines (one JSON object per line)", "files": []}
    for filename in CSV_FILES:
        source = DATA / filename
        if not source.exists():
            raise FileNotFoundError(f"Missing {source}; run the data generator first.")
        target = JSON_DIR / (source.stem + ".jsonl")
        rows = 0
        with source.open("r", encoding="utf-8-sig", newline="") as src, target.open("w", encoding="utf-8", newline="\n") as dst:
            reader = csv.DictReader(src)
            for row in reader:
                normalized = {key: (None if value == "" else value) for key, value in row.items()}
                dst.write(json.dumps(normalized, ensure_ascii=False, separators=(",", ":")) + "\n")
                rows += 1
        digest = hashlib.sha256(target.read_bytes()).hexdigest()
        manifest["files"].append({"file": target.name, "rows": rows, "sha256": digest})
    manifest_path = ROOT / "outputs" / "json_export_manifest.json"
    manifest_path.parent.mkdir(exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest

if __name__ == "__main__":
    result = export()
    print(json.dumps({"status": "exported", "files": len(result["files"]), "output": str(JSON_DIR)}, indent=2))
