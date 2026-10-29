
from datetime import datetime
from flask import Flask, jsonify, render_template, request

from database.connection import get_connection
from services.pricing_engine import evaluate_candidate
from services.promotion_service import validate_promotion_selection

app = Flask(__name__)
DEFAULT_SIMULATION_TIME = "2026-03-01T12:00:00"


def _fetch_promotions(cur, promotion_ids):
    placeholders = ",".join(["%s"] * len(promotion_ids))
    cur.execute(f"SELECT * FROM promotions WHERE promotion_id IN ({placeholders})", tuple(promotion_ids))
    promotions = cur.fetchall()
    cur.execute(f"SELECT * FROM promotion_rules WHERE promotion_id IN ({placeholders})", tuple(promotion_ids))
    rules = cur.fetchall()
    return promotions, rules


@app.get("/")
def home():
    return render_template("index.html")


@app.get("/api/health")
def health():
    try:
        conn = get_connection()
        conn.close()
        return jsonify({"status": "ok", "database": "connected"})
    except Exception:
        return jsonify({"status": "degraded", "database": "unavailable"}), 503


@app.get("/api/products")
def products():
    limit = min(max(request.args.get("limit", default=100, type=int), 1), 1000)
    search = request.args.get("search", "").strip()
    conn = get_connection()
    try:
        cur = conn.cursor(dictionary=True)
        if search:
            cur.execute("SELECT product_id, sku, name, category, currency, price_floor, price_ceiling, min_margin_pct, status FROM products WHERE sku LIKE %s OR name LIKE %s ORDER BY sku LIMIT %s", (f"%{search}%", f"%{search}%", limit))
        else:
            cur.execute("SELECT product_id, sku, name, category, currency, price_floor, price_ceiling, min_margin_pct, status FROM products ORDER BY sku LIMIT %s", (limit,))
        return jsonify(cur.fetchall())
    finally:
        conn.close()


@app.post("/api/simulate")
def simulate():
    payload = request.get_json(silent=True) or {}
    required = ["cost", "candidate_price", "min_margin_pct"]
    missing = [key for key in required if key not in payload]
    if missing:
        return jsonify({"error": "Missing required fields", "fields": missing}), 400
    try:
        cost = float(payload["cost"])
        candidate_price = float(payload["candidate_price"])
        min_margin_pct = float(payload["min_margin_pct"])
        discount_pct = float(payload.get("discount_pct", 0))
        promotion_ids = payload.get("promotion_ids", [])
        if not isinstance(promotion_ids, list):
            return jsonify({"error": "promotion_ids must be a list"}), 400
        stack_allowed = bool(payload.get("stack_allowed", False))

        if promotion_ids:
            sku = str(payload.get("sku", "")).strip()
            if not sku:
                return jsonify({"error": "sku is required when promotion_ids are selected"}), 400
            conn = get_connection()
            try:
                cur = conn.cursor(dictionary=True)
                cur.execute("SELECT product_id, category FROM products WHERE sku=%s", (sku,))
                product = cur.fetchone()
                if not product:
                    return jsonify({"error": "Unknown SKU"}), 404
                promotions, rules = _fetch_promotions(cur, promotion_ids)
                if len(promotions) != len(set(promotion_ids)):
                    return jsonify({"error": "One or more promotion IDs do not exist"}), 404
                placeholders = ",".join(["%s"] * len(promotion_ids))
                cur.execute(f"SELECT promotion_id FROM promotion_products WHERE product_id=%s AND promotion_id IN ({placeholders})", (product["product_id"], *promotion_ids))
                mapped_ids = {row["promotion_id"] for row in cur.fetchall()}
                evaluation_at = payload.get("evaluation_at", DEFAULT_SIMULATION_TIME)
                promotion_result = validate_promotion_selection(promotions, rules, evaluation_at=evaluation_at, order_value=candidate_price, category=product["category"], cost=cost, product_is_eligible=set(promotion_ids).issubset(mapped_ids))
                if not promotion_result["eligible"]:
                    return jsonify({"decision_status": "REJECTED", "reason_code": promotion_result["reason_code"], "candidate_price": round(candidate_price, 2), "final_price": None, "net_price_after_discount": round(candidate_price, 2), "margin_pct": None, "explanation": promotion_result["explanation"], "promotion_validation": promotion_result, "rule_version": "1.0.0"})
                discount_pct = (promotion_result["discount_amount"] / candidate_price * 100) if candidate_price > 0 else 0
                stack_allowed = True  # Promotion service has already checked stacking and exclusions.
            finally:
                conn.close()

        result = evaluate_candidate(
            cost=cost,
            candidate_price=candidate_price,
            min_margin_pct=min_margin_pct,
            price_floor=float(payload.get("price_floor", 0)),
            price_ceiling=float(payload.get("price_ceiling", 1e12)),
            discount_pct=discount_pct,
            competitor_price=(float(payload["competitor_price"]) if payload.get("competitor_price") is not None else None),
            competitor_age_hours=(float(payload.get("competitor_age_hours", 0)) if payload.get("competitor_price") is not None else None),
            stock_on_hand=int(payload.get("stock_on_hand", 0)),
            reason=str(payload.get("reason", "MANUAL_SIMULATION")),
            promotion_ids=promotion_ids,
            stack_allowed=stack_allowed,
            freshness_threshold_hours=float(payload.get("freshness_threshold_hours", 24)),
        )
        if promotion_ids:
            result["promotion_validation"] = promotion_result
        return jsonify(result)
    except (TypeError, ValueError) as exc:
        return jsonify({"error": str(exc)}), 400


@app.post("/api/promotions/validate")
def validate_promotions():
    payload = request.get_json(silent=True) or {}
    promotion_ids = payload.get("promotion_ids", [])
    if not isinstance(promotion_ids, list) or not promotion_ids:
        return jsonify({"error": "promotion_ids must be a non-empty list"}), 400
    try:
        order_value = float(payload.get("order_value", 0))
        margin_pct = float(payload["margin_pct"]) if payload.get("margin_pct") is not None else None
        evaluation_at = payload.get("evaluation_at", DEFAULT_SIMULATION_TIME)
        conn = get_connection()
        try:
            cur = conn.cursor(dictionary=True)
            promotions, rules = _fetch_promotions(cur, promotion_ids)
            if len(promotions) != len(set(promotion_ids)):
                return jsonify({"eligible": False, "reason_code": "PROMOTION_NOT_FOUND", "explanation": "One or more promotion IDs do not exist."}), 404
            product_is_eligible = True
            category = payload.get("category")
            sku = payload.get("sku")
            if sku:
                cur.execute("SELECT product_id, category FROM products WHERE sku=%s", (sku,))
                product = cur.fetchone()
                if not product:
                    return jsonify({"error": "Unknown SKU"}), 404
                placeholders = ",".join(["%s"] * len(promotion_ids))
                cur.execute(f"SELECT promotion_id FROM promotion_products WHERE product_id=%s AND promotion_id IN ({placeholders})", (product["product_id"], *promotion_ids))
                mapped = {row["promotion_id"] for row in cur.fetchall()}
                product_is_eligible = set(promotion_ids).issubset(mapped)
                category = product["category"]
            result = validate_promotion_selection(promotions, rules, evaluation_at=evaluation_at, order_value=order_value, category=category, margin_pct=margin_pct, product_is_eligible=product_is_eligible)
            return jsonify(result)
        finally:
            conn.close()
    except (TypeError, ValueError) as exc:
        return jsonify({"error": str(exc)}), 400



@app.get("/api/exceptions")
def exceptions():
    limit = min(max(request.args.get("limit", default=100, type=int), 1), 500)
    conn = get_connection()
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT d.decision_id, p.sku, p.name, d.candidate_price, d.decision_status, d.reason_code, d.explanation, d.created_at FROM price_decisions d JOIN products p ON p.product_id=d.product_id WHERE d.decision_status IN ('REJECTED','REVIEW_REQUIRED') ORDER BY d.created_at DESC LIMIT %s", (limit,))
        rows = cur.fetchall()
        for row in rows:
            if row.get("candidate_price") is not None:
                row["candidate_price"] = float(row["candidate_price"])
            if row.get("created_at") is not None:
                row["created_at"] = row["created_at"].isoformat(sep=" ")
        return jsonify(rows)
    finally:
        conn.close()

@app.get("/api/metrics")
def metrics():
    conn = get_connection()
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT COUNT(*) AS products FROM products")
        product_count = cur.fetchone()["products"]
        cur.execute("SELECT decision_status, COUNT(*) AS total FROM price_decisions GROUP BY decision_status")
        decisions = cur.fetchall()
        cur.execute("SELECT COUNT(*) AS promotions FROM promotions")
        promotion_count = cur.fetchone()["promotions"]
        return jsonify({"products": product_count, "promotions": promotion_count, "decisions_by_status": decisions})
    finally:
        conn.close()


if __name__ == "__main__":
    app.run(debug=False)
