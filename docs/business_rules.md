# Pricing rules (rule version 1.0.0)

1. Final net selling price = candidate price * (1 - discount_pct / 100), rounded to two decimal places.
2. Margin percentage = (net selling price - unit cost) / net selling price * 100. If net price is zero, margin is treated as -100% for rejection.
3. Candidate price must be at or below price ceiling. The candidate must be at or above the floor, and the final post-discount net price must also remain at or above the floor.
4. Post-discount margin must meet the product minimum margin.
5. Multiple promotions are rejected when stacking is not explicitly allowed.
6. Competitor observations older than 24 hours default to REVIEW_REQUIRED; the threshold is configurable.
7. No available stock defaults to REVIEW_REQUIRED.
8. Price-change reason is mandatory.
9. Decision precedence is: missing reason, floor, ceiling, promotion stacking, stale competitor, margin, stock, approved. This precedence is deterministic and documented.
10. Competitor observations are synthetic (`synthetic://...`) and not scraped from live sources.

This is a deterministic baseline rather than a trained ML model. Demand and inventory signals are generated from the synthetic source records and are available for policy extensions. Any additional demand-based price adjustment must be documented and tested before it affects final decisions.
