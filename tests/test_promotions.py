from datetime import datetime
from services.promotion_service import validate_promotion_selection

BASE = {"promotion_id":"PROMO-2026-000001","name":"Test promo","promotion_type":"PERCENT","discount_value":10,"starts_at":"2026-01-01 00:00:00","ends_at":"2026-12-31 23:59:59","status":"ACTIVE","stack_allowed":True,"min_order_value":100}

def test_promotion_eligible():
    result=validate_promotion_selection([BASE],[],evaluation_at="2026-03-01T12:00:00",order_value=500,margin_pct=30)
    assert result["eligible"] is True
    assert result["discount_amount"] == 50

def test_minimum_order_enforced():
    result=validate_promotion_selection([BASE],[],evaluation_at="2026-03-01T12:00:00",order_value=50)
    assert result["reason_code"] == "MIN_ORDER_VALUE_NOT_MET"

def test_stacking_requires_all_selected_to_allow():
    second={**BASE,"promotion_id":"PROMO-2026-000002","stack_allowed":False}
    result=validate_promotion_selection([BASE,second],[],evaluation_at="2026-03-01T12:00:00",order_value=500)
    assert result["reason_code"] == "PROMOTION_STACK_VIOLATION"

def test_exclusion_rule_enforced():
    second={**BASE,"promotion_id":"PROMO-2026-000002"}
    rule={"promotion_id":BASE["promotion_id"],"rule_type":"EXCLUSION","rule_value":second["promotion_id"],"effective_from":"2026-01-01 00:00:00","effective_to":"2026-12-31 23:59:59"}
    result=validate_promotion_selection([BASE,second],[rule],evaluation_at="2026-03-01T12:00:00",order_value=500)
    assert result["reason_code"] == "PROMOTION_EXCLUSION_VIOLATION"
