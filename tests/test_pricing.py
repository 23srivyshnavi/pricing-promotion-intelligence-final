from services.pricing_engine import evaluate_candidate

def base(**overrides):
    data=dict(cost=100,candidate_price=160,min_margin_pct=20,price_floor=125,price_ceiling=300,discount_pct=0,competitor_price=155,competitor_age_hours=2,stock_on_hand=10,reason="TEST",promotion_ids=[],stack_allowed=False)
    data.update(overrides)
    return evaluate_candidate(**data)

def test_valid_price_approved():
    assert base()["decision_status"] == "APPROVED"

def test_below_floor_rejected():
    result=base(candidate_price=90,price_floor=125)
    assert result["decision_status"] == "REJECTED"
    assert result["reason_code"] == "PRICE_BELOW_FLOOR"

def test_promotion_stack_rejected():
    result=base(promotion_ids=["P1","P2"],stack_allowed=False)
    assert result["reason_code"] == "PROMOTION_STACK_VIOLATION"

def test_stale_competitor_requires_review():
    result=base(competitor_age_hours=72)
    assert result["decision_status"] == "REVIEW_REQUIRED"
    assert result["reason_code"] == "STALE_COMPETITOR_OBSERVATION"

def test_margin_uses_discounted_price():
    result=base(candidate_price=160,price_floor=110,discount_pct=25)
    assert result["margin_pct"] == 16.667
    assert result["decision_status"] == "REJECTED"
    assert result["reason_code"] == "MARGIN_AFTER_DISCOUNT_BELOW_MINIMUM"

def test_reason_required():
    result=base(reason="")
    assert result["reason_code"] == "MISSING_PRICE_CHANGE_REASON"

def test_no_stock_requires_review():
    assert base(stock_on_hand=0)["reason_code"] == "NO_AVAILABLE_STOCK"

def test_candidate_price_uses_fresh_competitor_and_guardrails():
    from services.pricing_engine import recommend_candidate_price
    result = recommend_candidate_price(current_price=200, competitor_price=150, competitor_age_hours=2, demand_units=1, available_stock=40, price_floor=140, price_ceiling=300)
    assert result == 146.95

def test_candidate_price_ignores_stale_competitor():
    from services.pricing_engine import recommend_candidate_price
    result = recommend_candidate_price(current_price=200, competitor_price=100, competitor_age_hours=72, demand_units=1, available_stock=10, price_floor=140, price_ceiling=300)
    assert result == 200


def test_discounted_price_below_floor_is_rejected():
    result = base(candidate_price=160, price_floor=125, discount_pct=25)
    assert result["reason_code"] == "FINAL_PRICE_BELOW_FLOOR"
