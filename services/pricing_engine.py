from datetime import datetime, timezone

def recommend_candidate_price(*, current_price, competitor_price=None, competitor_age_hours=None, demand_units=0, available_stock=0, price_floor=0, price_ceiling=1e12, freshness_threshold_hours=24):
    """Produce a deterministic candidate from current price, fresh competitor data, demand and stock."""
    current_price = float(current_price)
    target = current_price
    competitor_is_fresh = competitor_price is not None and competitor_age_hours is not None and float(competitor_age_hours) <= float(freshness_threshold_hours)
    if competitor_is_fresh and float(competitor_price) > 0:
        # Move toward a competitive price without blindly copying a competitor.
        if float(competitor_price) < target:
            target = min(target, float(competitor_price) * 1.01)
    if int(available_stock) > 30 and int(demand_units) <= 2:
        target *= 0.97  # High stock and weak demand: modest markdown.
    elif 0 < int(available_stock) <= 3 and int(demand_units) >= 5:
        target *= 1.03  # Low stock and strong demand: modest increase.
    return round(min(max(target, float(price_floor)), float(price_ceiling)), 2)


def evaluate_candidate(*, cost, candidate_price, min_margin_pct, price_floor=0, price_ceiling=1e12, discount_pct=0, competitor_price=None, competitor_age_hours=None, stock_on_hand=0, reason="", promotion_ids=None, stack_allowed=False, freshness_threshold_hours=24):
    """Apply documented deterministic guardrails; returns an auditable decision."""
    values = {"cost": cost, "candidate_price": candidate_price, "min_margin_pct": min_margin_pct, "price_floor": price_floor, "price_ceiling": price_ceiling, "discount_pct": discount_pct}
    for key, value in values.items():
        if value is None or float(value) < 0: raise ValueError(f"{key} must be a non-negative number")
    if float(min_margin_pct) >= 100: raise ValueError("min_margin_pct must be below 100")
    if float(discount_pct) > 100: raise ValueError("discount_pct cannot exceed 100")
    if float(price_ceiling) < float(price_floor): raise ValueError("price_ceiling cannot be below price_floor")
    ids = promotion_ids or []
    net_price = round(float(candidate_price) * (1 - float(discount_pct) / 100), 2)
    margin_pct = round(((net_price - float(cost)) / net_price) * 100, 3) if net_price > 0 else -100.0
    status, reason_code, explanations = "APPROVED", "RULES_PASSED", []
    if not str(reason).strip():
        status, reason_code = "REJECTED", "MISSING_PRICE_CHANGE_REASON"; explanations.append("Price change reason is required.")
    elif float(candidate_price) < float(price_floor):
        status, reason_code = "REJECTED", "PRICE_BELOW_FLOOR"; explanations.append(f"Candidate price {candidate_price:.2f} is below floor {price_floor:.2f}.")
    elif float(candidate_price) > float(price_ceiling):
        status, reason_code = "REJECTED", "PRICE_ABOVE_CEILING"; explanations.append(f"Candidate price {candidate_price:.2f} exceeds ceiling {price_ceiling:.2f}.")
    elif len(ids) > 1 and not stack_allowed:
        status, reason_code = "REJECTED", "PROMOTION_STACK_VIOLATION"; explanations.append("Multiple promotions selected but stacking is prohibited.")
    elif competitor_price is not None and competitor_age_hours is not None and float(competitor_age_hours) > float(freshness_threshold_hours):
        status, reason_code = "REVIEW_REQUIRED", "STALE_COMPETITOR_OBSERVATION"; explanations.append(f"Competitor observation is {float(competitor_age_hours):.1f} hours old; threshold is {freshness_threshold_hours:.1f} hours.")
    elif net_price + 1e-9 < float(price_floor):
        status, reason_code = "REJECTED", "FINAL_PRICE_BELOW_FLOOR"; explanations.append(f"Post-discount price {net_price:.2f} is below floor {price_floor:.2f}.")
    elif margin_pct + 1e-9 < float(min_margin_pct):
        status, reason_code = "REJECTED", "MARGIN_AFTER_DISCOUNT_BELOW_MINIMUM"; explanations.append(f"Post-discount margin {margin_pct:.2f}% is below required {min_margin_pct:.2f}%.")
    elif int(stock_on_hand) <= 0:
        status, reason_code = "REVIEW_REQUIRED", "NO_AVAILABLE_STOCK"; explanations.append("No available stock; promotion/sale should be reviewed.")
    else:
        explanations.append("Candidate passes price guardrails, promotion stacking, freshness, stock and post-discount margin checks.")
    return {"decision_status":status,"reason_code":reason_code,"candidate_price":round(float(candidate_price),2),"final_price":net_price if status=="APPROVED" else None,"net_price_after_discount":net_price,"margin_pct":margin_pct,"minimum_margin_pct":float(min_margin_pct),"explanation":" ".join(explanations),"rule_version":"1.0.0","evaluated_at":datetime.now(timezone.utc).isoformat(timespec="seconds")}
