# Data dictionary

**Conventions:** Money is in INR; percentages are percentage points (e.g. `20` means 20%); quantities are whole units. CSV timestamps use `YYYY-MM-DD HH:MM:SS`; dates use `YYYY-MM-DD`. `effective_from` is inclusive. `effective_to` is inclusive when populated; NULL means open-ended. IDs are immutable. Synthetic source URLs are placeholders, not real websites.

## Product (`products.csv` / `products`)

| Field | Type | Required | Allowed values / units | Unique / validation |
|---|---|---:|---|---|
| `sku` | string | Yes | `SKU-000001` pattern | Unique primary business key; immutable |
| `name` | string | Yes | Non-empty product name | Non-empty |
| `category` | string | Yes | Electronics, Home, Sports, Books, Beauty, Kitchen | Non-empty |
| `currency` | char(3) | Yes | ISO-style currency code; INR in this dataset | Exactly 3 characters |
| `price_floor` | decimal | Yes | INR | >= 0; derived from cost and minimum margin |
| `price_ceiling` | decimal | Yes | INR | >= `price_floor` |
| `min_margin_pct` | decimal | Yes | [0, 100) percent | < 100 |
| `status` | enum | Yes | ACTIVE, INACTIVE, DISCONTINUED | Must follow product lifecycle |
| `created_at` | datetime | Yes | Timestamp | Must not be later than record's simulated creation timeline |

## CostRecord (`cost_records.csv` / `cost_records`)

| Field | Type | Required | Allowed values / units | Unique / validation |
|---|---|---:|---|---|
| `cost_id` | string | Yes | `COST-<sku>-YYYY-MM`; suffix used if multiple records in a month | Unique primary key |
| `sku` / `product_id` | string / BIGINT | Yes | Existing product | FK to Product; CSV uses SKU, MySQL uses `product_id` |
| `unit_cost` | decimal | Yes | INR per unit | >= 0 |
| `currency` | char(3) | Yes | INR for this dataset | Exactly 3 characters |
| `effective_from` | date | Yes | ISO date | Required; inclusive |
| `effective_to` | date | Optional | ISO date or NULL | Must be >= `effective_from`; intervals for one SKU must not overlap |
| `source` | string | Yes | SYNTHETIC_GENERATOR, SYNTHETIC_COST_CHANGE | Provenance label |

## PriceHistory (`price_history.csv` / `price_history`)

| Field | Type | Required | Allowed values / units | Unique / validation |
|---|---|---:|---|---|
| `price_id` | string | Yes | `PRC-<sku>-YYYYMMDD` | Unique primary key; one generated price row per SKU/date |
| `sku` / `product_id` | string / BIGINT | Yes | Existing product | FK to Product |
| `selling_price` | decimal | Yes | INR per unit | >= 0 |
| `effective_at` | datetime | Yes | Timestamp | Must be ordered for each SKU |
| `reason` | string | Yes | Reason code or text | Non-empty for any approved price change |
| `decision_id` | string | Optional | Existing decision ID or NULL | Optional link; NULL for initial source price rows |
| `source` | string | Yes | SYNTHETIC_GENERATOR or application source | Provenance label |

## CompetitorObservation (`competitor_observations.csv` / `competitor_observations`)

| Field | Type | Required | Allowed values / units | Unique / validation |
|---|---|---:|---|---|
| `observation_id` | string | Yes | `COMP-<sku>-YYYYMMDD` | Unique primary key |
| `sku` / `product_id` | string / BIGINT | Yes | Existing product | FK to Product |
| `competitor_name` | string | Yes | Competitor A/B/C in synthetic data | Non-empty |
| `competitor_price` | decimal | Yes | INR per unit | >= 0 |
| `currency` | char(3) | Yes | INR | Exactly 3 characters |
| `source_url` | string | Yes | `synthetic://competitor-observation` | Synthetic placeholder; no external collection |
| `source_timestamp` | datetime | Yes | Time represented by observation | Must not be after retrieval time |
| `retrieved_at` | datetime | Yes | Retrieval timestamp | >= `source_timestamp`; age controls freshness |

## InventorySnapshot (`inventory_snapshots.csv` / `inventory_snapshots`)

| Field | Type | Required | Allowed values / units | Unique / validation |
|---|---|---:|---|---|
| `snapshot_id` | string | Yes | `INV-<sku>-YYYYMMDD` | Unique primary key |
| `sku` / `product_id` | string / BIGINT | Yes | Existing product | FK to Product |
| `snapshot_date` | date | Yes | ISO date | Unique with SKU; chronological per SKU |
| `stock_on_hand` | integer | Yes | Units | >= 0 |
| `reserved_units` | integer | Yes | Units | >= 0; available stock is max(0, on-hand minus reserved) |
| `demand_units` | integer | Yes | Units demanded in simulated day | >= 0 |
| `stockout` | boolean | Yes | true / false | Derived from available stock <= 0 |

## Promotion (`promotions.csv` / `promotions`)

| Field | Type | Required | Allowed values / units | Unique / validation |
|---|---|---:|---|---|
| `promotion_id` | string | Yes | `PROMO-2026-000001` | Unique primary key |
| `name` | string | Yes | Synthetic promotion name | Non-empty |
| `promotion_type` | enum | Yes | PERCENT, FIXED | Must match discount interpretation |
| `discount_value` | decimal | Yes | Percent for PERCENT; INR for FIXED | >= 0; percentage <= 100 should be enforced for production |
| `starts_at` | datetime | Yes | Timestamp | <= `ends_at` |
| `ends_at` | datetime | Yes | Timestamp | >= `starts_at` |
| `status` | enum | Yes | DRAFT, ACTIVE, EXPIRED, CANCELLED | Must be consistent with validity at the reference time |
| `stack_allowed` | boolean | Yes | true / false | Stacking allowed only if all selected promotions permit it |
| `min_order_value` | decimal | Yes | INR | >= 0 |

## PromotionRule (`promotion_rules.csv` / `promotion_rules`)

| Field | Type | Required | Allowed values / units | Unique / validation |
|---|---|---:|---|---|
| `rule_id` | string | Yes | `RULE-000001-STACK` style | Unique primary key |
| `promotion_id` | string | Yes | Existing promotion | FK to Promotion |
| `rule_type` | enum | Yes | STACKING, EXCLUSION, MIN_MARGIN, MIN_ORDER, CATEGORY | Must be implemented/documented |
| `rule_value` | string | Yes | Boolean text, other promotion ID, percentage, amount or category list | Must parse according to rule type |
| `effective_from` | datetime | Yes | Timestamp | Inclusive; required |
| `effective_to` | datetime | Optional | Timestamp or NULL | >= `effective_from` |

## Order (`orders.csv` / `orders`)

| Field | Type | Required | Allowed values / units | Unique / validation |
|---|---|---:|---|---|
| `order_id` | string | Yes | `ORD-000000001` | Unique primary key |
| `sku` / `product_id` | string / BIGINT | Yes | Existing product | FK to Product |
| `quantity` | integer | Yes | Units | > 0 |
| `unit_price` | decimal | Yes | INR per unit before order-level discount | >= 0 |
| `discount_amount` | decimal | Yes | INR per order line | >= 0 and <= gross amount in production |
| `order_total` | decimal | Yes | INR | Must equal max(0, unit_price * quantity - discount_amount) |
| `ordered_at` | datetime | Yes | Timestamp | Within the synthetic timeline |
| `order_status` | enum | Yes | PLACED, FULFILLED, CANCELLED, RETURNED | Must follow allowed lifecycle transitions |

## PriceDecision (`price_decisions.csv` / `price_decisions`)

| Field | Type | Required | Allowed values / units | Unique / validation |
|---|---|---:|---|---|
| `decision_id` | string | Yes | `DEC-2026-000001` | Unique primary key |
| `sku` / `product_id` | string / BIGINT | Yes | Existing product | FK to Product |
| `cost_id` | string | Yes in generated decisions | Existing CostRecord | FK to CostRecord |
| `price_id` | string | Yes in generated decisions | Existing PriceHistory | FK to PriceHistory |
| `observation_id` | string | Yes in generated decisions | Existing CompetitorObservation | FK to CompetitorObservation |
| `snapshot_id` | string | Yes in generated decisions | Existing InventorySnapshot | FK to InventorySnapshot |
| `candidate_price` | decimal | Yes | INR | >= 0; within guardrails to be approved |
| `final_price` | decimal | Optional | INR or NULL | Present only for approved decision in this implementation |
| `discount_pct` | decimal | Yes | [0,100] percent | Must represent the total effective discount consistently |
| `margin_pct` | decimal | Optional | Percent | Derived using post-discount net price and cost |
| `decision_status` | enum | Yes | APPROVED, REJECTED, REVIEW_REQUIRED | Derived by rule engine; never randomly assigned |
| `reason_code` | string | Yes | Rule-defined code | Non-empty |
| `explanation` | text | Yes | Human-readable reason | Must reference the decision outcome |
| `rule_version` | string | Yes | Version string, e.g. 1.0.0 | Enables traceability |
| `created_at` | datetime | Yes | Timestamp | Append-only decision event time |

## Supporting tables and files

- `promotion_products`: bridge table; `(promotion_id, product_id)` is the composite primary key. Both are required foreign keys.
- `promotion_applications`: application ID is unique; promotion is required; order ID or decision ID must be present; discount amount >= 0; applied timestamp required.
- `audit_events`: event ID is unique; entity type/ID, event type, reason, timestamp and actor are required; old/new state JSON is optional. It is append-only.
- `edge_case_inputs.csv`: test-case ID is unique; input fields are required according to the pricing engine; contains no issue label.
- `ground_truth.json`: evaluation-only `case_id`, `issue_type`, and `expected_status`; labels must never be included in engine inputs.
- `run_manifest.json`: seed, scale parameters, row counts and SHA-256 checksums for reproducibility.
