"""Evaluate the five required edge cases against separate ground-truth labels."""
import json
from pathlib import Path
import pandas as pd
from services.pricing_engine import evaluate_candidate
ROOT=Path(__file__).resolve().parents[1]; DATA=ROOT/"data"; OUT=ROOT/"outputs"

def evaluate():
    inputs=pd.read_csv(DATA/"edge_case_inputs.csv").fillna("")
    truth={r["case_id"]:r for r in json.loads((DATA/"ground_truth.json").read_text(encoding="utf-8"))}
    results=[]
    for row in inputs.to_dict(orient="records"):
        try: promo_ids=json.loads(row["promotion_ids"]) if row["promotion_ids"] else []
        except json.JSONDecodeError: promo_ids=[]
        result=evaluate_candidate(cost=float(row["cost"]),candidate_price=float(row["candidate_price"]),min_margin_pct=float(row["min_margin_pct"]),price_floor=float(row["price_floor"]),price_ceiling=float(row["price_ceiling"]),discount_pct=float(row["discount_pct"]),competitor_price=float(row["competitor_price"]) if row["competitor_price"] != "" else None,competitor_age_hours=float(row["competitor_age_hours"]) if row["competitor_age_hours"] != "" else None,stock_on_hand=int(row["stock_on_hand"]),reason=str(row["reason"]),promotion_ids=promo_ids,stack_allowed=str(row["stack_allowed"]).lower()=="true")
        expected=truth[row["case_id"]]["expected_status"]
        results.append({"case_id":row["case_id"],"expected_status":expected,"actual_status":result["decision_status"],"issue_type":truth[row["case_id"]]["issue_type"],"passed":expected==result["decision_status"],"reason_code":result["reason_code"],"explanation":result["explanation"]})
    report={"total_cases":len(results),"passed":sum(r["passed"] for r in results),"failed":sum(not r["passed"] for r in results),"accuracy":round(sum(r["passed"] for r in results)/len(results),4) if results else None,"results":results}
    OUT.mkdir(exist_ok=True); (OUT/"evaluation_report.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    return report
if __name__=="__main__":
    result=evaluate(); print(json.dumps({k:v for k,v in result.items() if k!="results"},indent=2)); raise SystemExit(1 if result["failed"] else 0)
