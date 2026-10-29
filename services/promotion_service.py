from datetime import datetime


def validate_promotion_selection(promotions, rules, *, evaluation_at, order_value, category=None, margin_pct=None, cost=None, product_is_eligible=True):
    """Validate selected promotion records and compute their combined discount.

    `promotions` and `rules` are dictionaries from the database. The ground-truth
    labels are intentionally not accepted by this function.
    """
    if isinstance(evaluation_at, str):
        evaluation_at = datetime.fromisoformat(evaluation_at.replace("Z", "+00:00")).replace(tzinfo=None)
    selected_ids = {str(p["promotion_id"]) for p in promotions}
    if not promotions:
        return {"eligible": False, "reason_code": "NO_PROMOTIONS_SELECTED", "explanation": "Select at least one promotion."}
    if len(selected_ids) != len(promotions):
        return {"eligible": False, "reason_code": "DUPLICATE_PROMOTION_ID", "explanation": "The same promotion was selected more than once."}

    for promotion in promotions:
        starts, ends = promotion["starts_at"], promotion["ends_at"]
        if isinstance(starts, str): starts = datetime.fromisoformat(starts)
        if isinstance(ends, str): ends = datetime.fromisoformat(ends)
        if promotion["status"] in {"CANCELLED", "EXPIRED"} or not (starts <= evaluation_at <= ends):
            return {"eligible": False, "reason_code": "PROMOTION_NOT_ACTIVE", "explanation": f"Promotion {promotion['promotion_id']} is not active at the evaluation time."}
        # A DRAFT promotion becomes effectively active inside its validity window.
        if float(order_value) < float(promotion.get("min_order_value", 0)):
            return {"eligible": False, "reason_code": "MIN_ORDER_VALUE_NOT_MET", "explanation": f"Order value is below the minimum for {promotion['promotion_id']} .".replace("  ", " ")}

    if not product_is_eligible:
        return {"eligible": False, "reason_code": "PRODUCT_NOT_ELIGIBLE", "explanation": "The product is not mapped to every selected promotion."}
    if len(promotions) > 1 and any(not bool(p["stack_allowed"]) for p in promotions):
        return {"eligible": False, "reason_code": "PROMOTION_STACK_VIOLATION", "explanation": "At least one selected promotion prohibits stacking."}

    # Calculate discounts before checking promotion-specific margin requirements.
    remaining = float(order_value)
    total_discount = 0.0
    for promotion in promotions:
        value = float(promotion["discount_value"])
        if promotion["promotion_type"] == "PERCENT":
            discount = remaining * value / 100
        elif promotion["promotion_type"] == "FIXED":
            discount = value
        else:
            return {"eligible": False, "reason_code": "UNKNOWN_PROMOTION_TYPE", "explanation": f"Unknown promotion type for {promotion['promotion_id']}."}
        discount = min(max(discount, 0.0), remaining)
        total_discount += discount
        remaining -= discount
    total_discount = round(total_discount, 2)
    remaining = round(remaining, 2)
    calculated_margin = margin_pct
    if cost is not None:
        calculated_margin = round(((remaining - float(cost)) / remaining) * 100, 3) if remaining > 0 else -100.0

    for rule in rules:
        starts = rule["effective_from"]
        ends = rule.get("effective_to")
        if isinstance(starts, str): starts = datetime.fromisoformat(starts)
        if isinstance(ends, str): ends = datetime.fromisoformat(ends) if ends else None
        if evaluation_at < starts or (ends is not None and evaluation_at > ends):
            continue
        rule_type, value = rule["rule_type"], str(rule["rule_value"])
        if rule_type == "EXCLUSION" and value in selected_ids:
            return {"eligible": False, "reason_code": "PROMOTION_EXCLUSION_VIOLATION", "explanation": f"Promotion {rule['promotion_id']} excludes {value}."}
        if rule_type == "MIN_MARGIN" and calculated_margin is not None and float(calculated_margin) < float(value):
            return {"eligible": False, "reason_code": "PROMOTION_MIN_MARGIN_NOT_MET", "explanation": f"Selected promotion requires at least {float(value):.2f}% post-discount margin."}
        if rule_type == "MIN_ORDER" and float(order_value) < float(value):
            return {"eligible": False, "reason_code": "MIN_ORDER_VALUE_NOT_MET", "explanation": f"Selected promotion requires a minimum order value of {float(value):.2f}."}
        if rule_type == "CATEGORY" and category is not None and category not in [item.strip() for item in value.split(",")]:
            return {"eligible": False, "reason_code": "PROMOTION_CATEGORY_NOT_ELIGIBLE", "explanation": f"Category {category} is not eligible for {rule['promotion_id']}."}

    return {"eligible": True, "reason_code": "PROMOTIONS_ELIGIBLE", "explanation": "All selected promotions passed status, dates, product eligibility, stacking, exclusion and margin checks.", "order_value": round(float(order_value), 2), "discount_amount": total_discount, "net_order_value": remaining, "margin_pct_after_discount": calculated_margin, "selected_promotion_ids": sorted(selected_ids)}
