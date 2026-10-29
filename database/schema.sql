CREATE DATABASE IF NOT EXISTS pricing_intelligence CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE pricing_intelligence;

CREATE TABLE IF NOT EXISTS products (
  product_id BIGINT PRIMARY KEY AUTO_INCREMENT, sku VARCHAR(32) NOT NULL UNIQUE, name VARCHAR(160) NOT NULL, category VARCHAR(80) NOT NULL, currency CHAR(3) NOT NULL DEFAULT 'INR',
  price_floor DECIMAL(12,2) NOT NULL, price_ceiling DECIMAL(12,2) NOT NULL, min_margin_pct DECIMAL(5,2) NOT NULL, status ENUM('ACTIVE','INACTIVE','DISCONTINUED') NOT NULL DEFAULT 'ACTIVE', created_at DATETIME NOT NULL,
  CHECK (price_floor >= 0), CHECK (price_ceiling >= price_floor), CHECK (min_margin_pct >= 0 AND min_margin_pct < 100)
);
CREATE TABLE IF NOT EXISTS cost_records (
  cost_id VARCHAR(80) PRIMARY KEY, product_id BIGINT NOT NULL, unit_cost DECIMAL(12,2) NOT NULL, currency CHAR(3) NOT NULL DEFAULT 'INR', effective_from DATE NOT NULL, effective_to DATE NULL, source VARCHAR(80) NOT NULL,
  FOREIGN KEY (product_id) REFERENCES products(product_id), CHECK (unit_cost >= 0), CHECK (effective_to IS NULL OR effective_to >= effective_from), INDEX idx_cost_product_dates(product_id,effective_from,effective_to)
);
CREATE TABLE IF NOT EXISTS price_history (
  price_id VARCHAR(96) PRIMARY KEY, product_id BIGINT NOT NULL, selling_price DECIMAL(12,2) NOT NULL, effective_at DATETIME NOT NULL, reason VARCHAR(255) NOT NULL, decision_id VARCHAR(40) NULL, source VARCHAR(80) NOT NULL,
  FOREIGN KEY (product_id) REFERENCES products(product_id), CHECK (selling_price >= 0), INDEX idx_price_product_date(product_id,effective_at)
);
CREATE TABLE IF NOT EXISTS competitor_observations (
  observation_id VARCHAR(96) PRIMARY KEY, product_id BIGINT NOT NULL, competitor_name VARCHAR(100) NOT NULL, competitor_price DECIMAL(12,2) NOT NULL, currency CHAR(3) NOT NULL DEFAULT 'INR', source_url VARCHAR(500) NOT NULL, source_timestamp DATETIME NOT NULL, retrieved_at DATETIME NOT NULL,
  FOREIGN KEY (product_id) REFERENCES products(product_id), CHECK (competitor_price >= 0), CHECK (retrieved_at >= source_timestamp), INDEX idx_comp_product_time(product_id,source_timestamp)
);
CREATE TABLE IF NOT EXISTS inventory_snapshots (
  snapshot_id VARCHAR(96) PRIMARY KEY, product_id BIGINT NOT NULL, snapshot_date DATE NOT NULL, stock_on_hand INT NOT NULL, reserved_units INT NOT NULL DEFAULT 0, demand_units INT NOT NULL DEFAULT 0, stockout BOOLEAN NOT NULL,
  FOREIGN KEY (product_id) REFERENCES products(product_id), CHECK (stock_on_hand >= 0), CHECK (reserved_units >= 0), CHECK (demand_units >= 0), UNIQUE KEY uq_inventory_product_date(product_id,snapshot_date)
);
CREATE TABLE IF NOT EXISTS promotions (
  promotion_id VARCHAR(40) PRIMARY KEY, name VARCHAR(160) NOT NULL, promotion_type ENUM('PERCENT','FIXED') NOT NULL, discount_value DECIMAL(8,2) NOT NULL, starts_at DATETIME NOT NULL, ends_at DATETIME NOT NULL, status ENUM('DRAFT','ACTIVE','EXPIRED','CANCELLED') NOT NULL, stack_allowed BOOLEAN NOT NULL DEFAULT FALSE, min_order_value DECIMAL(12,2) NOT NULL DEFAULT 0,
  CHECK (discount_value >= 0), CHECK (promotion_type <> 'PERCENT' OR discount_value <= 100), CHECK (ends_at >= starts_at), CHECK (min_order_value >= 0)
);
CREATE TABLE IF NOT EXISTS promotion_rules (
  rule_id VARCHAR(48) PRIMARY KEY, promotion_id VARCHAR(40) NOT NULL, rule_type ENUM('STACKING','EXCLUSION','MIN_MARGIN','MIN_ORDER','CATEGORY') NOT NULL, rule_value VARCHAR(255) NOT NULL, effective_from DATETIME NOT NULL, effective_to DATETIME NULL,
  FOREIGN KEY (promotion_id) REFERENCES promotions(promotion_id), CHECK (effective_to IS NULL OR effective_to >= effective_from)
);
CREATE TABLE IF NOT EXISTS orders (
  order_id VARCHAR(48) PRIMARY KEY, product_id BIGINT NOT NULL, quantity INT NOT NULL, unit_price DECIMAL(12,2) NOT NULL, discount_amount DECIMAL(12,2) NOT NULL DEFAULT 0, order_total DECIMAL(14,2) NOT NULL, ordered_at DATETIME NOT NULL, order_status ENUM('PLACED','FULFILLED','CANCELLED','RETURNED') NOT NULL,
  FOREIGN KEY (product_id) REFERENCES products(product_id), CHECK (quantity > 0), CHECK (unit_price >= 0), CHECK (discount_amount >= 0), CHECK (order_total >= 0)
);
CREATE TABLE IF NOT EXISTS price_decisions (
  decision_id VARCHAR(40) PRIMARY KEY, product_id BIGINT NOT NULL, cost_id VARCHAR(80) NULL, price_id VARCHAR(96) NULL, observation_id VARCHAR(96) NULL, snapshot_id VARCHAR(96) NULL, candidate_price DECIMAL(12,2) NOT NULL, final_price DECIMAL(12,2) NULL, discount_pct DECIMAL(5,2) NOT NULL DEFAULT 0, margin_pct DECIMAL(7,3) NULL, decision_status ENUM('APPROVED','REJECTED','REVIEW_REQUIRED') NOT NULL, reason_code VARCHAR(80) NOT NULL, explanation TEXT NOT NULL, rule_version VARCHAR(40) NOT NULL, created_at DATETIME NOT NULL,
  FOREIGN KEY (product_id) REFERENCES products(product_id), FOREIGN KEY (cost_id) REFERENCES cost_records(cost_id), FOREIGN KEY (price_id) REFERENCES price_history(price_id), FOREIGN KEY (observation_id) REFERENCES competitor_observations(observation_id), FOREIGN KEY (snapshot_id) REFERENCES inventory_snapshots(snapshot_id), CHECK (candidate_price >= 0), CHECK (final_price IS NULL OR final_price >= 0), CHECK (discount_pct >= 0 AND discount_pct <= 100), INDEX idx_decision_product_date(product_id,created_at)
);
CREATE TABLE IF NOT EXISTS promotion_products (
  promotion_id VARCHAR(40) NOT NULL, product_id BIGINT NOT NULL, PRIMARY KEY(promotion_id,product_id), FOREIGN KEY (promotion_id) REFERENCES promotions(promotion_id), FOREIGN KEY (product_id) REFERENCES products(product_id)
);
CREATE TABLE IF NOT EXISTS promotion_applications (
  application_id VARCHAR(48) PRIMARY KEY, promotion_id VARCHAR(40) NOT NULL, order_id VARCHAR(48) NULL, decision_id VARCHAR(40) NULL, discount_amount DECIMAL(12,2) NOT NULL, applied_at DATETIME NOT NULL,
  FOREIGN KEY (promotion_id) REFERENCES promotions(promotion_id), FOREIGN KEY (order_id) REFERENCES orders(order_id), FOREIGN KEY (decision_id) REFERENCES price_decisions(decision_id), CHECK (discount_amount >= 0), CHECK (order_id IS NOT NULL OR decision_id IS NOT NULL)
);
CREATE TABLE IF NOT EXISTS audit_events (
  event_id VARCHAR(48) PRIMARY KEY, entity_type VARCHAR(80) NOT NULL, entity_id VARCHAR(96) NOT NULL, event_type VARCHAR(80) NOT NULL, old_state JSON NULL, new_state JSON NULL, reason VARCHAR(255) NOT NULL, event_timestamp DATETIME NOT NULL, actor VARCHAR(80) NOT NULL
);
