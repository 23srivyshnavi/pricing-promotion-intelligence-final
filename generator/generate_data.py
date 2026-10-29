"""Deterministic, parameterized synthetic data generator.
Starter: python -m generator.generate_data --products 100 --days 30 --promotions 50 --seed 20261022
Full:    python -m generator.generate_data --products 5000 --days 180 --promotions 2000 --seed 20261022
"""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from generator.id_generator import sku_id, cost_id, price_id, promotion_id, decision_id
from services.pricing_engine import evaluate_candidate, recommend_candidate_price

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
OUTPUT_DIR = ROOT / "outputs"
BASE_DATE = pd.Timestamp("2026-01-01")
CATEGORIES = ["Electronics", "Home", "Sports", "Books", "Beauty", "Kitchen"]
DAILY_FILES = {
    "price_history.csv": ["price_id", "sku", "selling_price", "effective_at", "reason", "source"],
    "competitor_observations.csv": ["observation_id", "sku", "competitor_name", "competitor_price", "currency", "source_url", "source_timestamp", "retrieved_at"],
    "inventory_snapshots.csv": ["snapshot_id", "sku", "snapshot_date", "stock_on_hand", "reserved_units", "demand_units", "stockout"],
    "price_decisions.csv": ["decision_id", "sku", "cost_id", "price_id", "observation_id", "snapshot_id", "candidate_price", "final_price", "discount_pct", "margin_pct", "decision_status", "reason_code", "explanation", "rule_version", "created_at"],
    "orders.csv": ["order_id", "sku", "quantity", "unit_price", "discount_amount", "order_total", "ordered_at", "order_status"],
}

def write_frame(frame, filename):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    frame.to_csv(DATA_DIR / filename, index=False, date_format="%Y-%m-%d %H:%M:%S")
    path = DATA_DIR / filename
    return {"file": filename, "rows": int(len(frame)), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}

def append_frame(rows, filename, columns, first_write=False):
    if not rows:
        return
    path = DATA_DIR / filename
    pd.DataFrame(rows, columns=columns).to_csv(path, mode="w" if first_write else "a", header=first_write, index=False)

def generate(products=100, days=30, promotions=50, seed=20261022):
    if products < 1 or days < 1 or promotions < 0:
        raise ValueError("products/days must be positive and promotions cannot be negative")
    rng = np.random.default_rng(seed)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    manifest = {"seed": seed, "products": products, "days": days, "promotions": promotions, "files": []}
    skus = [sku_id(i) for i in range(1, products + 1)]

    # Step 1: create parent/master records before dependent records.
    product_rows, cost_rows, params, audit_rows = [], [], {}, []
    audit_counter = 0
    base_costs = rng.uniform(80, 4000, products).round(2)
    initial_prices = (base_costs / rng.uniform(0.45, 0.75, products)).round(2)
    margins = rng.choice([15.0, 20.0, 25.0, 30.0], products)
    for i, sku in enumerate(skus):
        cost = float(base_costs[i])
        margin = float(margins[i])
        floor = round(cost / (1 - margin / 100), 2)
        ceiling = round(max(floor * 1.25, float(initial_prices[i]) * 1.8), 2)
        change_day = int(rng.integers(max(1, days // 3), days)) if days >= 3 and rng.random() < 0.12 else None
        changed_cost = round(cost * float(rng.uniform(0.92, 1.12)), 2) if change_day is not None else None
        product_name = f"Synthetic Product {i+1:05d}"
        product_category = str(rng.choice(CATEGORIES))
        product_rows.append({"sku": sku, "name": product_name, "category": product_category, "currency": "INR", "price_floor": floor, "price_ceiling": ceiling, "min_margin_pct": margin, "status": "ACTIVE", "created_at": BASE_DATE.strftime("%Y-%m-%d 00:00:00")})
        audit_counter += 1
        audit_rows.append({"event_id":f"EVT-{audit_counter:09d}","entity_type":"Product","entity_id":sku,"event_type":"PRODUCT_CREATED","old_state":"","new_state":json.dumps({"sku":sku,"name":product_name,"category":product_category,"status":"ACTIVE"},separators=(",",":")),"reason":"SYNTHETIC_MASTER_DATA_GENERATION","event_timestamp":BASE_DATE.strftime("%Y-%m-%d 00:00:00"),"actor":"SYNTHETIC_GENERATOR"})
        initial_cost_id = cost_id(sku, BASE_DATE.strftime("%Y-%m"))
        changed_cost_id = None
        initial_end = (BASE_DATE + pd.Timedelta(days=change_day - 1)).date().isoformat() if change_day is not None else None
        cost_rows.append({"cost_id": initial_cost_id, "sku": sku, "unit_cost": cost, "currency": "INR", "effective_from": BASE_DATE.date().isoformat(), "effective_to": initial_end, "source": "SYNTHETIC_GENERATOR"})
        audit_counter += 1
        audit_rows.append({"event_id":f"EVT-{audit_counter:09d}","entity_type":"CostRecord","entity_id":initial_cost_id,"event_type":"COST_RECORD_CREATED","old_state":"","new_state":json.dumps({"cost_id":initial_cost_id,"sku":sku,"unit_cost":cost,"effective_from":BASE_DATE.date().isoformat()},separators=(",",":")),"reason":"INITIAL_COST_RECORD","event_timestamp":BASE_DATE.strftime("%Y-%m-%d 00:00:00"),"actor":"SYNTHETIC_GENERATOR"})
        if change_day is not None:
            changed_date = BASE_DATE + pd.Timedelta(days=change_day)
            changed_cost_id = f"COST-{sku}-{changed_date.strftime('%Y-%m')}-02"
            cost_rows.append({"cost_id": changed_cost_id, "sku": sku, "unit_cost": changed_cost, "currency": "INR", "effective_from": changed_date.date().isoformat(), "effective_to": None, "source": "SYNTHETIC_COST_CHANGE"})
            audit_counter += 1
            audit_rows.append({"event_id":f"EVT-{audit_counter:09d}","entity_type":"CostRecord","entity_id":changed_cost_id,"event_type":"COST_CHANGED","old_state":json.dumps({"unit_cost":cost},separators=(",",":")),"new_state":json.dumps({"cost_id":changed_cost_id,"sku":sku,"unit_cost":changed_cost,"effective_from":changed_date.date().isoformat()},separators=(",",":")),"reason":"SYNTHETIC_COST_CHANGE","event_timestamp":changed_date.strftime("%Y-%m-%d 00:00:00"),"actor":"SYNTHETIC_GENERATOR"})
        params[sku] = {"base_cost": cost, "changed_cost": changed_cost, "change_day": change_day, "initial_cost_id": initial_cost_id, "changed_cost_id": changed_cost_id, "initial_price": float(initial_prices[i]), "margin": margin, "floor": floor, "ceiling": ceiling}

    manifest["files"].append(write_frame(pd.DataFrame(product_rows), "products.csv"))
    manifest["files"].append(write_frame(pd.DataFrame(cost_rows), "cost_records.csv"))

    # Prepare empty files so the generator is valid even if a table has zero rows.
    for filename, columns in DAILY_FILES.items():
        pd.DataFrame(columns=columns).to_csv(DATA_DIR / filename, index=False)

    # Step 2: write dependent daily events in small chunks to keep full-scale RAM usage reasonable.
    daily_buffers = {name: [] for name in DAILY_FILES}
    batch_products = 0
    order_counter = 0
    for i, sku in enumerate(skus):
        p = params[sku]
        for d in range(days):
            day = BASE_DATE + pd.Timedelta(days=d)
            date8 = day.strftime("%Y%m%d")
            active_cost = p["changed_cost"] if p["change_day"] is not None and d >= p["change_day"] else p["base_cost"]
            active_cost_id = p["changed_cost_id"] if p["change_day"] is not None and d >= p["change_day"] else p["initial_cost_id"]
            demand = max(0, int(rng.poisson(4)))
            stock = max(0, int(rng.poisson(18)))
            if rng.random() < 0.025:
                stock = 0
            reserved = int(rng.integers(0, min(stock, 4) + 1)) if stock else 0
            available = max(0, stock - reserved)
            stockout = available <= 0
            price = round(float(np.clip(p["initial_price"] * rng.uniform(0.96, 1.04), p["floor"], p["ceiling"])), 2)
            pid = price_id(sku, date8)
            sid = f"INV-{sku}-{date8}"
            oid = f"COMP-{sku}-{date8}"
            source_age = int(rng.integers(30, 121)) if rng.random() < 0.04 else int(rng.integers(0, 13))
            source_time = day + pd.Timedelta(hours=12) - pd.Timedelta(hours=source_age)
            comp_price = round(price * float(rng.uniform(0.88, 1.12)), 2)
            daily_buffers["price_history.csv"].append({"price_id": pid, "sku": sku, "selling_price": price, "effective_at": day.strftime("%Y-%m-%d 12:00:00"), "reason": "BASELINE_DAILY_PRICE", "source": "SYNTHETIC_GENERATOR"})
            daily_buffers["competitor_observations.csv"].append({"observation_id": oid, "sku": sku, "competitor_name": str(rng.choice(["Competitor A", "Competitor B", "Competitor C"])), "competitor_price": comp_price, "currency": "INR", "source_url": "synthetic://competitor-observation", "source_timestamp": source_time.strftime("%Y-%m-%d %H:%M:%S"), "retrieved_at": day.strftime("%Y-%m-%d 12:00:00")})
            daily_buffers["inventory_snapshots.csv"].append({"snapshot_id": sid, "sku": sku, "snapshot_date": day.date().isoformat(), "stock_on_hand": stock, "reserved_units": reserved, "demand_units": demand, "stockout": stockout})
            candidate_price = recommend_candidate_price(current_price=price, competitor_price=comp_price, competitor_age_hours=source_age, demand_units=demand, available_stock=available, price_floor=p["floor"], price_ceiling=p["ceiling"], freshness_threshold_hours=24)
            outcome = evaluate_candidate(cost=active_cost, candidate_price=candidate_price, min_margin_pct=p["margin"], price_floor=p["floor"], price_ceiling=p["ceiling"], discount_pct=0, competitor_price=comp_price, competitor_age_hours=source_age, stock_on_hand=available, reason="BASELINE_DAILY_REVIEW", promotion_ids=[], stack_allowed=False, freshness_threshold_hours=24)
            decision_num = i * days + d + 1
            daily_buffers["price_decisions.csv"].append({"decision_id": decision_id(decision_num), "sku": sku, "cost_id": active_cost_id, "price_id": pid, "observation_id": oid, "snapshot_id": sid, "candidate_price": candidate_price, "final_price": outcome["final_price"], "discount_pct": 0, "margin_pct": outcome["margin_pct"], "decision_status": outcome["decision_status"], "reason_code": outcome["reason_code"], "explanation": outcome["explanation"], "rule_version": "1.0.0", "created_at": day.strftime("%Y-%m-%d 12:05:00")})
            if available > 0 and rng.random() < 0.12:
                quantity = int(rng.integers(1, min(4, available) + 1))
                discount = round(price * float(rng.choice([0, 0.05, 0.10])), 2)
                total = round(max(0, price * quantity - discount), 2)
                order_counter += 1
                daily_buffers["orders.csv"].append({"order_id": f"ORD-{order_counter:09d}", "sku": sku, "quantity": quantity, "unit_price": price, "discount_amount": discount, "order_total": total, "ordered_at": day.strftime("%Y-%m-%d %H:%M:%S"), "order_status": "FULFILLED"})
        batch_products += 1
        if batch_products >= 25 or i == len(skus) - 1:
            for filename, columns in DAILY_FILES.items():
                append_frame(daily_buffers[filename], filename, columns, first_write=False)
                daily_buffers[filename].clear()
            batch_products = 0

    # Step 3: promotion masters, then promotion rules and product bridge rows.
    promo_rows, rule_rows, promo_products = [], [], []
    for n in range(1, promotions + 1):
        start = BASE_DATE + pd.Timedelta(days=int(rng.integers(0, max(1, days))))
        end = start + pd.Timedelta(days=int(rng.integers(1, 31)))
        typ = str(rng.choice(["PERCENT", "FIXED"], p=[0.85, 0.15]))
        value = round(float(rng.uniform(5, 25) if typ == "PERCENT" else rng.uniform(50, 300)), 2)
        pid = promotion_id(n)
        stack = bool(rng.random() < 0.2)
        promo_rows.append({"promotion_id": pid, "name": f"Synthetic Promotion {n:06d}", "promotion_type": typ, "discount_value": value, "starts_at": start.strftime("%Y-%m-%d 00:00:00"), "ends_at": end.strftime("%Y-%m-%d 23:59:59"), "status": ("ACTIVE" if start <= BASE_DATE <= end else ("DRAFT" if start > BASE_DATE else "EXPIRED")), "stack_allowed": stack, "min_order_value": round(float(rng.choice([0, 500, 1000])), 2)})
        audit_counter += 1
        audit_rows.append({"event_id":f"EVT-{audit_counter:09d}","entity_type":"Promotion","entity_id":pid,"event_type":"PROMOTION_CREATED","old_state":"","new_state":json.dumps({"promotion_id":pid,"status":("ACTIVE" if start <= BASE_DATE <= end else ("DRAFT" if start > BASE_DATE else "EXPIRED")),"starts_at":start.strftime("%Y-%m-%d %H:%M:%S"),"ends_at":end.strftime("%Y-%m-%d %H:%M:%S")},separators=(",",":")),"reason":"SYNTHETIC_PROMOTION_GENERATION","event_timestamp":BASE_DATE.strftime("%Y-%m-%d 00:00:00"),"actor":"SYNTHETIC_GENERATOR"})
        rule_rows.append({"rule_id": f"RULE-{n:06d}-STACK", "promotion_id": pid, "rule_type": "STACKING", "rule_value": str(stack).lower(), "effective_from": start.strftime("%Y-%m-%d 00:00:00"), "effective_to": end.strftime("%Y-%m-%d 23:59:59")})
        if rng.random() < 0.2:
            rule_rows.append({"rule_id": f"RULE-{n:06d}-MARGIN", "promotion_id": pid, "rule_type": "MIN_MARGIN", "rule_value": "20", "effective_from": start.strftime("%Y-%m-%d 00:00:00"), "effective_to": end.strftime("%Y-%m-%d 23:59:59")})
        if promotions > 1 and n < promotions and rng.random() < 0.08:
            excluded_id = promotion_id(n + 1)
            rule_rows.append({"rule_id": f"RULE-{n:06d}-EXCL", "promotion_id": pid, "rule_type": "EXCLUSION", "rule_value": excluded_id, "effective_from": start.strftime("%Y-%m-%d 00:00:00"), "effective_to": end.strftime("%Y-%m-%d 23:59:59")})
        promo_products.append({"promotion_id": pid, "sku": str(rng.choice(skus))})
    manifest["files"].append(write_frame(pd.DataFrame(promo_rows, columns=["promotion_id","name","promotion_type","discount_value","starts_at","ends_at","status","stack_allowed","min_order_value"]), "promotions.csv"))
    manifest["files"].append(write_frame(pd.DataFrame(rule_rows, columns=["rule_id","promotion_id","rule_type","rule_value","effective_from","effective_to"]), "promotion_rules.csv"))
    manifest["files"].append(write_frame(pd.DataFrame(promo_products, columns=["promotion_id","sku"]), "promotion_products.csv"))
    manifest["files"].append(write_frame(pd.DataFrame(columns=["application_id","promotion_id","order_id","decision_id","discount_amount","applied_at"]), "promotion_applications.csv"))
    manifest["files"].append(write_frame(pd.DataFrame(audit_rows, columns=["event_id","entity_type","entity_id","event_type","old_state","new_state","reason","event_timestamp","actor"]), "audit_events.csv"))

    # Step 4: negative test inputs are separate from ground-truth labels.
    edge_inputs = [
        {"case_id":"EDGE-000001","cost":100.0,"candidate_price":90.0,"min_margin_pct":20.0,"price_floor":125.0,"price_ceiling":300.0,"discount_pct":0.0,"competitor_price":110.0,"competitor_age_hours":2,"stock_on_hand":10,"reason":"TEST_PRICE_FLOOR","promotion_ids":[],"stack_allowed":False},
        {"case_id":"EDGE-000002","cost":100.0,"candidate_price":160.0,"min_margin_pct":20.0,"price_floor":125.0,"price_ceiling":300.0,"discount_pct":0.0,"competitor_price":155.0,"competitor_age_hours":2,"stock_on_hand":10,"reason":"TEST_STACKING","promotion_ids":["PROMO-2026-000001","PROMO-2026-000002"],"stack_allowed":False},
        {"case_id":"EDGE-000003","cost":100.0,"candidate_price":160.0,"min_margin_pct":20.0,"price_floor":125.0,"price_ceiling":300.0,"discount_pct":0.0,"competitor_price":155.0,"competitor_age_hours":72,"stock_on_hand":10,"reason":"TEST_STALE_COMPETITOR","promotion_ids":[],"stack_allowed":False},
        {"case_id":"EDGE-000004","cost":100.0,"candidate_price":160.0,"min_margin_pct":20.0,"price_floor":110.0,"price_ceiling":300.0,"discount_pct":25.0,"competitor_price":130.0,"competitor_age_hours":2,"stock_on_hand":10,"reason":"TEST_POST_DISCOUNT_MARGIN","promotion_ids":[],"stack_allowed":False},
        {"case_id":"EDGE-000005","cost":100.0,"candidate_price":160.0,"min_margin_pct":20.0,"price_floor":125.0,"price_ceiling":300.0,"discount_pct":0.0,"competitor_price":155.0,"competitor_age_hours":2,"stock_on_hand":10,"reason":"","promotion_ids":[],"stack_allowed":False},
    ]
    for row in edge_inputs:
        row["promotion_ids"] = json.dumps(row["promotion_ids"])
    manifest["files"].append(write_frame(pd.DataFrame(edge_inputs), "edge_case_inputs.csv"))
    ground_truth = [
        {"case_id":"EDGE-000001","issue_type":"PRICE_BELOW_FLOOR","expected_status":"REJECTED"},
        {"case_id":"EDGE-000002","issue_type":"PROMOTION_STACK_VIOLATION","expected_status":"REJECTED"},
        {"case_id":"EDGE-000003","issue_type":"STALE_COMPETITOR_OBSERVATION","expected_status":"REVIEW_REQUIRED"},
        {"case_id":"EDGE-000004","issue_type":"MARGIN_AFTER_DISCOUNT_VIOLATION","expected_status":"REJECTED"},
        {"case_id":"EDGE-000005","issue_type":"MISSING_PRICE_CHANGE_REASON","expected_status":"REJECTED"},
    ]
    truth_path = DATA_DIR / "ground_truth.json"
    truth_path.write_text(json.dumps(ground_truth, indent=2), encoding="utf-8")
    manifest["files"].append({"file":"ground_truth.json","rows":len(ground_truth),"sha256":hashlib.sha256(truth_path.read_bytes()).hexdigest(),"role":"evaluation_only_not_engine_input"})

    # Recalculate checksums/row counts for all CSVs after streaming writes.
    csv_files = ["products.csv","cost_records.csv","price_history.csv","competitor_observations.csv","inventory_snapshots.csv","promotions.csv","promotion_rules.csv","promotion_products.csv","orders.csv","price_decisions.csv","promotion_applications.csv","audit_events.csv","edge_case_inputs.csv"]
    by_name = {entry["file"]: entry for entry in manifest["files"]}
    for filename in csv_files:
        path = DATA_DIR / filename
        with path.open("rb") as handle:
            digest = hashlib.sha256(handle.read()).hexdigest()
        with path.open("r",encoding="utf-8",newline="") as handle:
            rows_count = max(0, sum(1 for _ in handle)-1)
        by_name[filename] = {"file":filename,"rows":rows_count,"sha256":digest}
    manifest["files"] = [by_name[name] for name in csv_files] + [entry for entry in manifest["files"] if entry["file"] == "ground_truth.json"]
    (OUTPUT_DIR / "run_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--products", type=int, default=100)
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--promotions", type=int, default=50)
    parser.add_argument("--seed", type=int, default=20261022)
    args = parser.parse_args()
    manifest = generate(args.products, args.days, args.promotions, args.seed)
    print(json.dumps({"status":"generated","seed":args.seed,"files":len(manifest["files"]),"output":str(DATA_DIR)}, indent=2))

if __name__ == "__main__":
    main()
