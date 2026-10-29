"""Import generated CSVs into MySQL in parent-first order.
Run after schema.sql and after generator.generate_data has created CSV files.
For full scale, this performs chunked inserts to limit memory use.
"""
import csv
from pathlib import Path
import pandas as pd
from database.connection import get_connection

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
CHUNK_SIZE = 5000


def clean(value):
    if pd.isna(value):
        return None
    if hasattr(value, "item"):
        value = value.item()
    if isinstance(value, bool):
        return int(value)
    return value



def insert_frame(conn, table, columns, rows):
    if not rows:
        return 0

    placeholders = ",".join(["%s"] * len(columns))
    sql = f"INSERT INTO {table} ({','.join(columns)}) VALUES ({placeholders})"

    cur = conn.cursor()
    count = 0
    batch_size = 5000

    try:
        for start in range(0, len(rows), batch_size):
            batch = rows[start:start + batch_size]

            clean_rows = [
                tuple(clean(value) for value in row)
                for row in batch
            ]

            cur.executemany(sql, clean_rows)
            count += cur.rowcount

        return count
    finally:
        cur.close()



def read_chunks(filename):
    path = DATA / filename
    if not path.exists():
        raise FileNotFoundError(f"Missing {path}. Run the generator first.")
    return pd.read_csv(path, chunksize=CHUNK_SIZE)


def import_data():
    conn = get_connection()
    report = {}
    try:
        # Clear in child-to-parent order to support repeatable local imports.
        cur = conn.cursor()
        for table in ["promotion_applications", "promotion_products", "price_decisions", "orders", "inventory_snapshots", "competitor_observations", "price_history", "promotion_rules", "promotions", "cost_records", "audit_events", "products"]:
            cur.execute(f"DELETE FROM {table}")
        conn.commit()
        cur.close()

        # Parent/master table first.
        total = 0
        for chunk in read_chunks("products.csv"):
            rows = [tuple(row[c] for c in ["sku","name","category","currency","price_floor","price_ceiling","min_margin_pct","status","created_at"]) for row in chunk.to_dict("records")]
            total += insert_frame(conn, "products", ["sku","name","category","currency","price_floor","price_ceiling","min_margin_pct","status","created_at"], rows)
            conn.commit()
        report["products"] = total

        cur = conn.cursor()
        cur.execute("SELECT sku, product_id FROM products")
        product_ids = {sku: pid for sku, pid in cur.fetchall()}
        cur.close()

        # Parent entities for child records.
        total = 0
        for chunk in read_chunks("promotions.csv"):
            cols = ["promotion_id","name","promotion_type","discount_value","starts_at","ends_at","status","stack_allowed","min_order_value"]
            rows = [tuple(row[c] for c in cols) for row in chunk.to_dict("records")]
            total += insert_frame(conn,"promotions",cols,rows); conn.commit()
        report["promotions"] = total

        total = 0
        for chunk in read_chunks("cost_records.csv"):
            cols=["cost_id","sku","unit_cost","currency","effective_from","effective_to","source"]
            rows=[(r["cost_id"],product_ids[r["sku"]],r["unit_cost"],r["currency"],r["effective_from"],r["effective_to"],r["source"]) for r in chunk.to_dict("records")]
            total += insert_frame(conn,"cost_records",["cost_id","product_id","unit_cost","currency","effective_from","effective_to","source"],rows); conn.commit()
        report["cost_records"] = total

        total = 0
        for chunk in read_chunks("price_history.csv"):
            cols=["price_id","sku","selling_price","effective_at","reason","source"]
            rows=[(r["price_id"],product_ids[r["sku"]],r["selling_price"],r["effective_at"],r["reason"],None,r["source"]) for r in chunk.to_dict("records")]
            total += insert_frame(conn,"price_history",["price_id","product_id","selling_price","effective_at","reason","decision_id","source"],rows); conn.commit()
        report["price_history"] = total

        total = 0
        for chunk in read_chunks("competitor_observations.csv"):
            rows=[(r["observation_id"],product_ids[r["sku"]],r["competitor_name"],r["competitor_price"],r["currency"],r["source_url"],r["source_timestamp"],r["retrieved_at"]) for r in chunk.to_dict("records")]
            total += insert_frame(conn,"competitor_observations",["observation_id","product_id","competitor_name","competitor_price","currency","source_url","source_timestamp","retrieved_at"],rows); conn.commit()
        report["competitor_observations"] = total

        total = 0
        for chunk in read_chunks("inventory_snapshots.csv"):
            rows=[(r["snapshot_id"],product_ids[r["sku"]],r["snapshot_date"],r["stock_on_hand"],r["reserved_units"],r["demand_units"],r["stockout"]) for r in chunk.to_dict("records")]
            total += insert_frame(conn,"inventory_snapshots",["snapshot_id","product_id","snapshot_date","stock_on_hand","reserved_units","demand_units","stockout"],rows); conn.commit()
        report["inventory_snapshots"] = total

        total = 0
        for chunk in read_chunks("orders.csv"):
            rows=[(r["order_id"],product_ids[r["sku"]],r["quantity"],r["unit_price"],r["discount_amount"],r["order_total"],r["ordered_at"],r["order_status"]) for r in chunk.to_dict("records")]
            total += insert_frame(conn,"orders",["order_id","product_id","quantity","unit_price","discount_amount","order_total","ordered_at","order_status"],rows); conn.commit()
        report["orders"] = total

        total = 0
        for chunk in read_chunks("promotion_rules.csv"):
            cols=["rule_id","promotion_id","rule_type","rule_value","effective_from","effective_to"]
            rows=[tuple(r[c] for c in cols) for r in chunk.to_dict("records")]
            total += insert_frame(conn,"promotion_rules",cols,rows); conn.commit()
        report["promotion_rules"] = total

        total = 0
        for chunk in read_chunks("price_decisions.csv"):
            rows=[]
            for r in chunk.to_dict("records"):
                rows.append((r["decision_id"],product_ids[r["sku"]],r["cost_id"],r["price_id"],r["observation_id"],r["snapshot_id"],r["candidate_price"],r["final_price"],r["discount_pct"],r["margin_pct"],r["decision_status"],r["reason_code"],r["explanation"],r["rule_version"],r["created_at"]))
            total += insert_frame(conn,"price_decisions",["decision_id","product_id","cost_id","price_id","observation_id","snapshot_id","candidate_price","final_price","discount_pct","margin_pct","decision_status","reason_code","explanation","rule_version","created_at"],rows); conn.commit()
        report["price_decisions"] = total

        total = 0
        for chunk in read_chunks("promotion_products.csv"):
            rows=[(r["promotion_id"],product_ids[r["sku"]]) for r in chunk.to_dict("records")]
            total += insert_frame(conn,"promotion_products",["promotion_id","product_id"],rows); conn.commit()
        report["promotion_products"] = total

        total = 0
        for chunk in read_chunks("audit_events.csv"):
            cols=["event_id","entity_type","entity_id","event_type","old_state","new_state","reason","event_timestamp","actor"]
            rows=[tuple(r[c] for c in cols) for r in chunk.to_dict("records")]
            total += insert_frame(conn,"audit_events",cols,rows); conn.commit()
        report["audit_events"] = total
        report["promotion_applications"] = 0
        return report
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    import json
    result = import_data()
    print(json.dumps({"status":"imported","row_counts":result}, indent=2))
