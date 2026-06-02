# Data Quality Log

This document records the cleaning decisions made during Phase 2 of the Egyptian Retail & Financial Analytics Platform.

The purpose of this log is to document not only what was cleaned, but why each cleaning decision was made. This makes the pipeline reproducible, auditable, and easier to explain in interviews or project reviews.

---

## Table: orders

### Column(s): `order_purchase_timestamp`, `order_approved_at`, `order_delivered_carrier_date`, `order_delivered_customer_date`, `order_estimated_delivery_date`

Issue: These columns were loaded into the staging schema as `text`, although they represent date/time values.

Decision: Convert all order timestamp columns to proper datetime values using `pd.to_datetime(..., errors='coerce')`.

Action: Applied in `scripts/02_cleaning/clean_orders.py`.

Reason: Datetime conversion is required before calculating delivery duration, approval time, late delivery, and other time-based metrics.

---

### Column: `order_approved_at`

Issue: `order_approved_at` has 160 missing values out of 99,441 orders.

Decision: Keep the missing values. Do not impute or delete them.

Action: Create a boolean flag column called `is_approved`.

Reason: A missing approval timestamp may carry business meaning, such as an order that was not approved or was cancelled. Replacing it with a fake date would create misleading data.

---

### Column: `order_delivered_carrier_date`

Issue: `order_delivered_carrier_date` has 1,783 missing values out of 99,441 orders.

Decision: Keep the missing values. Do not impute or delete them.

Action: Create a boolean flag column called `is_delivered_to_carrier`.

Reason: A missing carrier delivery timestamp may indicate that the order never reached the shipping/carrier stage. This is important operational information.

---

### Column: `order_delivered_customer_date`

Issue: `order_delivered_customer_date` has 2,965 missing values out of 99,441 orders.

Decision: Keep the missing values. Do not impute or delete them.

Action: Create a boolean flag column called `is_delivered_to_customer`.

Reason: A missing customer delivery timestamp may indicate an undelivered, canceled, unavailable, or incomplete order. This should be represented explicitly instead of hidden.

---

### Table-level issue: duplicate rows

Issue: No exact duplicate rows were identified in the profiling stage.

Decision: Still include a defensive duplicate-removal step based on `order_id`.

Action: Apply `drop_duplicates(subset=['order_id'])` in the cleaning script.

Reason: Even if no duplicates currently exist, defensive checks make the pipeline safer if new raw data is loaded later.

---

### Table-level issue: suspicious timeline values

Issue: SQL validation identified:
- 166 orders where `order_delivered_carrier_date` occurs before `order_purchase_timestamp`.
- 23 orders where `order_delivered_customer_date` occurs before `order_delivered_carrier_date`.

Decision: Do not delete these rows during the first cleaning pass. Flag them for downstream review.

Action: Create boolean timeline issue columns:
- `carrier_before_purchase`
- `customer_delivery_before_carrier`
- `has_timeline_issue`

Reason: These records may reflect data entry issues, timestamp inconsistencies, or operational system errors. They should be visible for analysis rather than silently removed.

---

### Engineered feature: `days_to_deliver`

Issue: Delivery duration is not available directly in the raw data.

Decision: Create `days_to_deliver` by calculating the difference between `order_delivered_customer_date` and `order_purchase_timestamp`.

Action: Add `days_to_deliver` in the cleaning script.

Reason: Delivery duration is a key operational metric for later analysis and Power BI reporting.

---

### Engineered feature: `delivered_on_time`

Issue: The raw data does not directly tell us whether a delivered order arrived on time.

Decision: Create a boolean `delivered_on_time` flag.

Action: Compare `order_delivered_customer_date` with `order_estimated_delivery_date`.

Reason: On-time delivery rate is an important business KPI for logistics and customer experience analysis.

---

## Table: customers

### Column(s): `customer_city`, `customer_state`

Issue: Customer city and state values are text fields that may contain inconsistent capitalization or extra whitespace.

Decision: Standardize `customer_city` by trimming leading/trailing spaces and converting values to title case. Standardize `customer_state` by trimming leading/trailing spaces and converting values to uppercase.

Action: Apply `.str.strip().str.title()` to `customer_city` and `.str.strip().str.upper()` to `customer_state` in `scripts/02_cleaning/clean_customers.py`.

Reason: Standardized geographic fields are required for accurate grouping, filtering, and dashboard analysis. Without standardization, values such as `cairo`, `Cairo`, and ` Cairo ` may be treated as different cities.

---

### Table-level issue: duplicate customer IDs

Issue: No duplicate issue is expected for `customer_id`, but customer identifiers should be validated before warehouse loading.

Decision: Apply a defensive duplicate-removal step based on `customer_id`.

Action: Use `drop_duplicates(subset=["customer_id"])`.

Reason: `customer_id` should uniquely identify each customer row. Defensive validation protects the pipeline if future raw data contains duplicates.

---

### Engineered feature: `customer_city_state`

Issue: The raw table stores city and state in separate columns.

Decision: Create a combined `customer_city_state` field.

Action: Combine `customer_city` and `customer_state`.

Reason: A combined location field is useful for readable geographic analysis and dashboard filters.

---

## Table: order_items

### Column: `shipping_limit_date`

Issue: `shipping_limit_date` was loaded from the staging schema as a raw date/time-like field and must be validated as a proper datetime column before analysis.

Decision: Convert `shipping_limit_date` to a proper datetime value using `pd.to_datetime(..., errors='coerce')`.

Action: Applied in `scripts/02_cleaning/clean_order_items.py`.

Reason: Shipping deadline analysis requires this column to behave as a real datetime field. If it remains text, we cannot safely compare it with other date fields or use it in time-based analysis.

---

### Column: `price`

Issue: Product item prices should be positive values. Zero or negative prices would not be valid for revenue analysis.

Decision: Remove rows where `price` is less than or equal to zero.

Action: Filter out invalid rows in `scripts/02_cleaning/clean_order_items.py` and log how many rows were removed.

Reason: Invalid prices would distort revenue, average order value, and profitability calculations.

---

### Column: `freight_value`

Issue: Freight/shipping value should not be negative.

Decision: Remove rows where `freight_value` is negative.

Action: Filter out invalid rows in `scripts/02_cleaning/clean_order_items.py` and log how many rows were removed.

Reason: Negative shipping values would distort total item value and logistics analysis.

---

### Table-level issue: duplicate order item rows

Issue: Each item within an order should be uniquely identified by the combination of `order_id` and `order_item_id`.

Decision: Apply a defensive duplicate-removal step based on `order_id` and `order_item_id`.

Action: Use `drop_duplicates(subset=["order_id", "order_item_id"])`.

Reason: The combination of order ID and item ID should uniquely identify each line item. Defensive deduplication protects the pipeline if future raw data contains repeated rows.

---

### Engineered feature: `total_item_value`

Issue: The raw table stores item price and freight value separately.

Decision: Create `total_item_value` as `price + freight_value`.

Action: Add a new column called `total_item_value`.

Reason: This represents the full item-level amount paid by the customer and will later be used in revenue analysis and the warehouse fact table.

---

## Table: products

### Column: `product_category_name`

Issue: `product_category_name` contains missing values.

Decision: Preserve the missing-category information using a boolean flag, then replace missing category values with `unknown` for downstream warehouse loading.

Action: Create `is_product_category_missing`, then fill missing `product_category_name` values with `unknown`.

Reason: Missing product categories are important data quality information, but warehouse dimensions should not contain null category labels.

---

### Column: `product_category_name_english`

Issue: Product category names are originally stored in Portuguese. Business dashboards and reports should use readable English category names.

Decision: Join `staging.products` with `staging.categories` to add the English category name.

Action: Merge products with the category translation table using `product_category_name`.

Reason: English category names make the final warehouse and Power BI dashboard easier to understand.

---

### Columns: `product_weight_g`, `product_length_cm`, `product_height_cm`, `product_width_cm`

Issue: Product physical dimension columns contain missing values and some invalid weight values.

Decision: Convert invalid zero or negative physical dimensions to missing values, then impute missing physical dimensions using the median value within each product category. If a category median is unavailable, use the global median.

Action: Apply category-level median imputation in `scripts/02_cleaning/clean_products.py`.

Reason: Physical dimensions are needed for logistics and shipping analysis. Median imputation is preferred because it is less affected by extreme values than the mean.

---

### Columns: `product_name_lenght`, `product_description_lenght`, `product_photos_qty`

Issue: Product descriptive metadata columns contain missing values.

Decision: Fill missing descriptive metadata values with `0`.

Action: Apply `.fillna(0)` to descriptive metadata columns.

Reason: These columns represent counts or lengths. A missing value means the product metadata is unavailable, so `0` is a safer placeholder than inventing an average description length.

---

### Table-level issue: duplicate product IDs

Issue: Each product should be uniquely identified by `product_id`.

Decision: Apply a defensive duplicate-removal step based on `product_id`.

Action: Use `drop_duplicates(subset=["product_id"])`.

Reason: `product_id` should uniquely identify each product before loading into the warehouse product dimension.

---

## Table: sellers

### Column(s): `seller_city`, `seller_state`

Issue: Seller city and state values are text fields that may contain inconsistent capitalization or extra whitespace.

Decision: Standardize `seller_city` by trimming leading/trailing spaces and converting values to title case. Standardize `seller_state` by trimming leading/trailing spaces and converting values to uppercase.

Action: Apply `.str.strip().str.title()` to `seller_city` and `.str.strip().str.upper()` to `seller_state` in `scripts/02_cleaning/clean_sellers.py`.

Reason: Standardized geographic fields are required for accurate grouping, filtering, and seller-location analysis.

---

### Table-level issue: duplicate seller IDs

Issue: Each seller should be uniquely identified by `seller_id`.

Decision: Apply a defensive duplicate-removal step based on `seller_id`.

Action: Use `drop_duplicates(subset=["seller_id"])`.

Reason: `seller_id` should uniquely identify each seller before loading into the warehouse seller dimension.

---

### Engineered feature: `seller_city_state`

Issue: The raw table stores seller city and seller state in separate columns.

Decision: Create a combined `seller_city_state` field.

Action: Combine `seller_city` and `seller_state`.

Reason: A combined location field is useful for readable geographic analysis and dashboard filters.

---

## Table: reviews

### Column(s): `review_creation_date`, `review_answer_timestamp`

Issue: These columns were loaded into the staging schema as `text`, although they represent date/time values.

Decision: Convert both columns to proper datetime values using `pd.to_datetime(..., errors='coerce')`.

Action: Applied in `scripts/02_cleaning/clean_reviews.py`.

Reason: Datetime conversion is required before calculating review response time or validating the order of review events.

---

### Column: `review_score`

Issue: Review score should follow the expected customer rating scale from 1 to 5.

Decision: Validate that all review scores fall within the range 1 to 5.

Action: Add an assertion in `scripts/02_cleaning/clean_reviews.py`.

Reason: Invalid review scores would distort customer satisfaction analysis.

---

### Column(s): `review_comment_title`, `review_comment_message`

Issue: These columns contain many missing values.

Decision: Keep the missing values and create boolean flags to show whether a review includes a written title or message.

Action: Create `has_review_title` and `has_review_message`.

Reason: Missing review text is not necessarily a data error. Customers can submit numeric ratings without writing comments, so deleting or imputing these fields would be misleading.

---

### Table-level issue: duplicate review rows

Issue: Exact duplicate review rows may distort review counts and satisfaction metrics.

Decision: Apply a defensive exact-duplicate removal step.

Action: Use `drop_duplicates()`.

Reason: Exact duplicate rows do not add new information and should not be counted multiple times.

---

### Table-level issue: review response timeline

Issue: `review_answer_timestamp` should not occur before `review_creation_date`.

Decision: Do not delete records automatically. Create a boolean flag called `answer_before_review_creation`.

Action: Compare `review_answer_timestamp` with `review_creation_date`.

Reason: Timeline inconsistencies should remain visible for data quality review instead of being silently removed.

---

### Engineered feature: `response_time_days`

Issue: The raw table does not directly show how long it took to respond to a review.

Decision: Create `response_time_days` as the difference between `review_answer_timestamp` and `review_creation_date`.

Action: Add `response_time_days` in the cleaning script.

Reason: Review response time is useful for customer service and operational analysis.

---

## Table: payments

### Column: `payment_type`

Issue: `payment_type` is a categorical text field that may contain inconsistent capitalization or whitespace.

Decision: Standardize `payment_type` by trimming leading/trailing spaces and converting values to lowercase.

Action: Apply `.str.strip().str.lower()` in `scripts/02_cleaning/clean_payments.py`.

Reason: Standardizing payment types ensures that values such as `Credit_Card`, `credit_card`, and ` credit_card ` are treated as the same category during analysis.

---

### Column: `payment_value`

Issue: Payment value should be positive for valid revenue and payment analysis.

Decision: Remove rows where `payment_value` is less than or equal to zero.

Action: Filter invalid payment value rows in `scripts/02_cleaning/clean_payments.py` and log how many rows were removed.

Reason: Zero or negative payment values would distort revenue, average order value, and payment-method analysis.

---

### Column: `payment_installments`

Issue: Payment installments should not be negative.

Decision: Remove rows where `payment_installments` is less than zero.

Action: Filter invalid installment rows in `scripts/02_cleaning/clean_payments.py`.

Reason: Negative installment counts are not logically valid.

---

### Column: `payment_sequential`

Issue: `payment_sequential` should be a positive value that identifies the sequence of payment records within an order.

Decision: Remove rows where `payment_sequential` is less than or equal to zero.

Action: Filter invalid payment sequence rows in `scripts/02_cleaning/clean_payments.py`.

Reason: Invalid payment sequence values would make it difficult to uniquely identify payment records per order.

---

### Table-level issue: duplicate payment records

Issue: Each payment record should be uniquely identified by the combination of `order_id` and `payment_sequential`.

Decision: Apply a defensive duplicate-removal step based on `order_id` and `payment_sequential`.

Action: Use `drop_duplicates(subset=["order_id", "payment_sequential"])`.

Reason: The same payment sequence for the same order should not appear more than once.

---

### Engineered feature: `is_installment_payment`

Issue: The raw table stores the number of installments but does not directly flag whether the payment was paid in installments.

Decision: Create `is_installment_payment` as `payment_installments > 1`.

Action: Add a boolean column in `scripts/02_cleaning/clean_payments.py`.

Reason: This is useful for analyzing customer payment behavior.

---

### Engineered feature: `payment_value_per_installment`

Issue: The raw table does not directly show the average value per installment.

Decision: Create `payment_value_per_installment` by dividing `payment_value` by `payment_installments` when installments are greater than zero.

Action: Add `payment_value_per_installment` in `scripts/02_cleaning/clean_payments.py`.

Reason: This feature supports installment-level payment analysis while avoiding division by zero.