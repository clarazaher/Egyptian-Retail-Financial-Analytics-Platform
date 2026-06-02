CREATE INDEX IF NOT EXISTS idx_fact_purchase_date
ON warehouse.fact_order_items(purchase_date_key);

CREATE INDEX IF NOT EXISTS idx_fact_delivery_date
ON warehouse.fact_order_items(delivery_date_key);

CREATE INDEX IF NOT EXISTS idx_fact_customer
ON warehouse.fact_order_items(customer_key);

CREATE INDEX IF NOT EXISTS idx_fact_product
ON warehouse.fact_order_items(product_key);

CREATE INDEX IF NOT EXISTS idx_fact_seller
ON warehouse.fact_order_items(seller_key);

CREATE INDEX IF NOT EXISTS idx_fact_order_id
ON warehouse.fact_order_items(order_id);