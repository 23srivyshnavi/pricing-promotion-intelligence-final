"""Validate CSV primary/foreign keys, enums, dates, arithmetic, and lifecycle rules."""
import json
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUT = ROOT / "outputs"
BASE_DATE = pd.Timestamp("2026-01-01")


def validate():
    report = {"checks": [], "errors": []}
    def check(name, passed, detail):
        report["checks"].append({"name": name, "passed": bool(passed), "detail": detail})
        if not passed:
            report["errors"].append({"name": name, "detail": detail})

    required = {
        "products.csv": ["sku", "price_floor", "price_ceiling", "min_margin_pct", "status"],
        "cost_records.csv": ["cost_id", "sku", "unit_cost", "effective_from", "effective_to"],
        "price_history.csv": ["price_id", "sku", "selling_price", "effective_at"],
        "competitor_observations.csv": ["observation_id", "sku", "competitor_price", "source_timestamp", "retrieved_at"],
        "inventory_snapshots.csv": ["snapshot_id", "sku", "snapshot_date", "stock_on_hand", "reserved_units", "demand_units", "stockout"],
        "promotions.csv": ["promotion_id", "promotion_type", "discount_value", "starts_at", "ends_at", "status"],
        "promotion_rules.csv": ["rule_id", "promotion_id", "rule_type", "rule_value"],
        "promotion_products.csv": ["promotion_id", "sku"],
        "orders.csv": ["order_id", "sku", "quantity", "unit_price", "discount_amount", "order_total"],
        "price_decisions.csv": ["decision_id", "sku", "cost_id", "price_id", "observation_id", "snapshot_id", "candidate_price", "decision_status"],
        "audit_events.csv": ["event_id", "entity_type", "entity_id", "event_type", "reason", "event_timestamp", "actor"],
    }
    frames = {}
    for filename, columns in required.items():
        path = DATA / filename
        if not path.exists():
            check(f"file:{filename}", False, "Missing required file")
            continue
        frame = pd.read_csv(path)
        frames[filename] = frame
        check(f"columns:{filename}", set(columns).issubset(frame.columns), f"Required columns: {columns}")
    if "products.csv" not in frames:
        report["summary"] = {"files_checked": len(frames), "checks_passed": 0, "checks_failed": len(report["errors"])}
        return report

    products = frames["products.csv"]
    product_skus = set(products["sku"].dropna().astype(str))
    check("products_sku_unique", products["sku"].is_unique, "Product SKU must be unique")
    check("product_price_bounds", ((products["price_floor"] >= 0) & (products["price_ceiling"] >= products["price_floor"]) & (products["min_margin_pct"] >= 0) & (products["min_margin_pct"] < 100)).all(), "Floors, ceilings and margins must be in valid ranges")
    check("product_status_enum", products["status"].isin(["ACTIVE", "INACTIVE", "DISCONTINUED"]).all(), "Product status must be an allowed enum")

    primary_keys = {"cost_records.csv":"cost_id", "price_history.csv":"price_id", "competitor_observations.csv":"observation_id", "inventory_snapshots.csv":"snapshot_id", "promotions.csv":"promotion_id", "promotion_rules.csv":"rule_id", "orders.csv":"order_id", "price_decisions.csv":"decision_id"}
    for filename, key in primary_keys.items():
        if filename in frames:
            check(f"pk_unique:{key}", frames[filename][key].is_unique, f"{key} must be unique")

    for filename in ["cost_records.csv", "price_history.csv", "competitor_observations.csv", "inventory_snapshots.csv", "orders.csv", "price_decisions.csv", "promotion_products.csv"]:
        if filename in frames:
            child_skus = set(frames[filename]["sku"].dropna().astype(str))
            check(f"fk_sku:{filename}", child_skus.issubset(product_skus), "Every child SKU must reference an existing product")

    if "cost_records.csv" in frames:
        costs = frames["cost_records.csv"].copy()
        costs["effective_from"] = pd.to_datetime(costs["effective_from"], errors="coerce")
        costs["effective_to"] = pd.to_datetime(costs["effective_to"], errors="coerce")
        check("cost_nonnegative", (frames["cost_records.csv"]["unit_cost"] >= 0).all(), "Unit cost must be nonnegative")
        check("cost_dates_valid", (costs["effective_from"].notna() & (costs["effective_to"].isna() | (costs["effective_to"] >= costs["effective_from"]))).all(), "Cost date ranges must be valid")
        overlap = False
        for _, group in costs.sort_values("effective_from").groupby("sku"):
            previous_end = None
            for row in group.to_dict("records"):
                if previous_end is not None and row["effective_from"] <= previous_end:
                    overlap = True
                previous_end = row["effective_to"]
        check("cost_effective_ranges_no_overlap", not overlap, "Cost effective ranges for the same SKU must not overlap")

    if "price_history.csv" in frames:
        prices = frames["price_history.csv"]
        check("price_nonnegative", (prices["selling_price"] >= 0).all(), "Selling prices must be nonnegative")
        check("price_ids_date_consistent", prices["price_id"].str.match(r"^PRC-SKU-\d{6}-\d{8}$").all(), "Price history IDs must follow PRC-SKU-000001-YYYYMMDD")

    if "competitor_observations.csv" in frames:
        comp = frames["competitor_observations.csv"].copy()
        source = pd.to_datetime(comp["source_timestamp"], errors="coerce")
        retrieved = pd.to_datetime(comp["retrieved_at"], errors="coerce")
        check("competitor_price_nonnegative", (comp["competitor_price"] >= 0).all(), "Competitor prices must be nonnegative")
        check("competitor_timestamps_valid", (source.notna() & retrieved.notna() & (retrieved >= source)).all(), "Retrieved timestamp must not precede source timestamp")

    if "inventory_snapshots.csv" in frames:
        inv = frames["inventory_snapshots.csv"]
        check("inventory_nonnegative", (inv[["stock_on_hand", "reserved_units", "demand_units"]] >= 0).all().all(), "Inventory quantities cannot be negative")
        check("inventory_product_date_unique", not inv.duplicated(["sku", "snapshot_date"]).any(), "One snapshot per SKU/date")
        expected_stockout = (inv["stock_on_hand"] - inv["reserved_units"]).clip(lower=0) <= 0
        check("stockout_derived", (expected_stockout == inv["stockout"].astype(bool)).all(), "Stockout label must derive from available stock")

    if "promotions.csv" in frames:
        promo = frames["promotions.csv"].copy()
        promo["starts_at"] = pd.to_datetime(promo["starts_at"], errors="coerce")
        promo["ends_at"] = pd.to_datetime(promo["ends_at"], errors="coerce")
        check("promotion_type_enum", promo["promotion_type"].isin(["PERCENT", "FIXED"]).all(), "Promotion type enum")
        check("promotion_status_enum", promo["status"].isin(["DRAFT", "ACTIVE", "EXPIRED", "CANCELLED"]).all(), "Promotion status enum")
        check("promotion_dates_valid", (promo["starts_at"].notna() & promo["ends_at"].notna() & (promo["ends_at"] >= promo["starts_at"])).all(), "Promotion end must not precede start")
        expected_status = promo.apply(lambda r: "ACTIVE" if r["starts_at"] <= BASE_DATE <= r["ends_at"] else ("DRAFT" if r["starts_at"] > BASE_DATE else "EXPIRED"), axis=1)
        check("promotion_lifecycle_consistent", (expected_status == promo["status"]).all(), "Promotion status must be consistent as of the synthetic reference date")

    if "promotion_rules.csv" in frames and "promotions.csv" in frames:
        promo_ids = set(frames["promotions.csv"]["promotion_id"].astype(str))
        rules = frames["promotion_rules.csv"]
        check("fk_promotion_rules", set(rules["promotion_id"].astype(str)).issubset(promo_ids), "Every rule references an existing promotion")
        check("promotion_rule_enum", rules["rule_type"].isin(["STACKING", "EXCLUSION", "MIN_MARGIN", "MIN_ORDER", "CATEGORY"]).all(), "Rule type must be an allowed enum")
        exclusions = set(rules.loc[rules["rule_type"] == "EXCLUSION", "rule_value"].astype(str))
        check("promotion_exclusions_reference_existing_ids", exclusions.issubset(promo_ids), "Exclusion rules must reference existing promotions")

    if "promotion_products.csv" in frames and "promotions.csv" in frames:
        check("fk_promotion_products", set(frames["promotion_products.csv"]["promotion_id"].astype(str)).issubset(set(frames["promotions.csv"]["promotion_id"].astype(str))), "Promotion-product bridge must reference existing promotions")

    if "orders.csv" in frames:
        orders = frames["orders.csv"]
        expected_total = (orders["unit_price"] * orders["quantity"] - orders["discount_amount"]).clip(lower=0).round(2)
        check("order_totals_reconcile", (expected_total - orders["order_total"].round(2)).abs().le(0.02).all(), "Order totals must reconcile")
        check("order_quantities_valid", (orders["quantity"] > 0).all(), "Order quantity must be positive")

    if "audit_events.csv" in frames:
        events = frames["audit_events.csv"]
        check("audit_event_id_unique", events["event_id"].is_unique, "Audit event IDs must be unique")
        check("audit_event_required_fields", (events[["entity_type", "entity_id", "event_type", "reason", "actor"]].notna() & (events[["entity_type", "entity_id", "event_type", "reason", "actor"]].astype(str) != "")).all().all(), "Audit event identity and reason fields are required")
        json_valid = True
        for field in ["old_state", "new_state"]:
            for value in events[field].dropna().astype(str):
                try:
                    json.loads(value)
                except json.JSONDecodeError:
                    json_valid = False
                    break
        check("audit_state_json_valid", json_valid, "Audit old_state/new_state must contain valid JSON when present")

    if "price_decisions.csv" in frames:
        decisions = frames["price_decisions.csv"]
        for filename, field in [("cost_records.csv", "cost_id"), ("price_history.csv", "price_id"), ("competitor_observations.csv", "observation_id"), ("inventory_snapshots.csv", "snapshot_id")]:
            if filename in frames:
                allowed = set(frames[filename][field].astype(str))
                check(f"fk_decisions_{field}", set(decisions[field].dropna().astype(str)).issubset(allowed), f"Every decision {field} must exist")
        check("decision_status_enum", decisions["decision_status"].isin(["APPROVED", "REJECTED", "REVIEW_REQUIRED"]).all(), "Decision status enum")
        approved = decisions["decision_status"] == "APPROVED"
        check("approved_has_final_price", decisions.loc[approved, "final_price"].notna().all(), "Approved decisions must have a final price")
        check("rejected_not_finalized", decisions.loc[~approved, "final_price"].isna().all(), "Rejected/review decisions must not finalize a price")

    report["summary"] = {"files_checked": len(frames), "checks_passed": sum(item["passed"] for item in report["checks"]), "checks_failed": sum(not item["passed"] for item in report["checks"])}
    OUT.mkdir(exist_ok=True)
    (OUT / "validation_summary.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report

if __name__ == "__main__":
    result = validate()
    print(json.dumps(result["summary"], indent=2))
    raise SystemExit(1 if result["errors"] else 0)
