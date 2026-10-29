# Database relationships and lifecycle

- Product 1:N CostRecord, PriceHistory, CompetitorObservation, InventorySnapshot, Order, and PriceDecision.
- Promotion 1:N PromotionRule.
- Product N:M Promotion through `promotion_products`.
- Promotion 1:N PromotionApplication; Order 0:N PromotionApplication; PriceDecision 0:N PromotionApplication.
- PriceDecision references one product and optionally the cost record, price-history row, competitor observation, and inventory snapshot used for the decision.
- AuditEvent is append-only and stores entity type/ID, event type, old/new state, actor, timestamp, and reason. It intentionally has no FK to all possible entity tables because it is a polymorphic event log.

Lifecycle states: products ACTIVE/INACTIVE/DISCONTINUED; promotions DRAFT/ACTIVE/EXPIRED/CANCELLED; orders PLACED/FULFILLED/CANCELLED/RETURNED; decisions APPROVED/REJECTED/REVIEW_REQUIRED. Promotion validity dates must be checked in addition to status. History rows are append-only; new prices and decisions create new records rather than overwriting prior events.
