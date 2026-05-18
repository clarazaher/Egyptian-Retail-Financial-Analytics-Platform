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