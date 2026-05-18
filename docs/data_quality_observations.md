# Data Quality Observations

This document records the initial profiling findings for the raw staging layer of the Egyptian Retail & Financial Analytics Platform.

The purpose of this stage is to understand the raw data before cleaning. No cleaning decisions are applied here. Cleaning decisions will be documented later in `docs/data_quality_log.md`.

---

## 1. staging.customers

### Missing Values
- 

### Data Types
- 

### Duplicates
- 

### Outliers or Suspicious Values
- 

### Cardinality
- 

---

## 2. staging.geolocation

### Missing Values
- 

### Data Types
- 

### Duplicates
- 

### Outliers or Suspicious Values
- 

### Cardinality
- 

---

## 3. staging.order_items

### Missing Values
- 

### Data Types
- 

### Duplicates
- 

### Outliers or Suspicious Values
- 

### Cardinality
- 

---

## 4. staging.payments

### Missing Values
- 

### Data Types
- 

### Duplicates
- 

### Outliers or Suspicious Values
- 

### Cardinality
- 

---

## 5. staging.reviews

### Missing Values
- review_comment_title we have 87656 missing values 
review_comment_message we have 58247 missing values 

### Data Types
- ### Data Types
- The columns `review_creation_date` and `review_answer_timestamp` are stored as `text`, although they represent date/time values.
- These columns should be converted to proper datetime/timestamp fields during the cleaning phase.
- `review_score` is stored as `bigint`, which is appropriate because it represents a numeric rating.

### Duplicates
- No exact duplicate business rows were identified.

### Outliers or Suspicious Values
- SQL validation confirmed that all `review_score` values fall within the expected 1 to 5 rating range.
- The minimum `review_score` is 1 and the maximum `review_score` is 5.
- No cases were identified where `review_answer_timestamp` occurs before `review_creation_date`.
- Missing review comment titles and messages are not necessarily suspicious because customers can submit a numeric rating without writing a text review.

### Cardinality
- `review_score` is a useful low-cardinality categorical/numeric column because it represents a fixed rating scale from 1 to 5.
- This column will be useful later for customer satisfaction analysis.
- `review_id` has high cardinality, which is expected because it identifies individual reviews.

---

## 6. staging.orders
### Data Types
- The columns `order_purchase_timestamp`, `order_approved_at`, `order_delivered_carrier_date`, `order_delivered_customer_date`, and `order_estimated_delivery_date` are stored as `text`, although they represent date/time values.
- These columns should be converted to proper datetime/timestamp fields during the cleaning phase.

### Missing Values
- order_approved_at variable has 160 missing values  order_delivered_carrier_date has 1783 missing values  order_delivered_customer_date has 1783 missing values 
The rest of the variables have 0 missing values  

### Data Types
- Timestamp columns such as `order_purchase_timestamp`, `order_approved_at`, `order_delivered_carrier_date`, `order_delivered_customer_date`, and `order_estimated_delivery_date` are currently loaded as text/object columns instead of datetime columns. These should be converted during the cleaning phase.

### Duplicates
-  No exact duplicate business rows were identified.

### Outliers or Suspicious Values
- SQL timeline validation identified 166 orders where `order_delivered_carrier_date` occurs before `order_purchase_timestamp`. This is logically suspicious because an order should not be handed to the carrier before it is purchased.
- SQL timeline validation identified 23 orders where `order_delivered_customer_date` occurs before `order_delivered_carrier_date`. This is logically suspicious because an order should not be delivered to the customer before it reaches the carrier stage.
- No cases were identified where `order_approved_at` occurs before `order_purchase_timestamp`.
- No cases were identified where `order_delivered_customer_date` occurs before `order_purchase_timestamp`.
- No cases were identified where `order_estimated_delivery_date` occurs before `order_purchase_timestamp`.
- These suspicious timeline records should be reviewed during the cleaning phase before calculating delivery performance metrics.

### Cardinality
- `order_status` is a useful low-cardinality categorical column because it groups orders by business status, such as delivered, shipped, canceled, unavailable, invoiced, or processing.
- This column will be useful later for filtering orders and analyzing operational performance by order state.
- Identifier columns such as `order_id` and `customer_id` have high cardinality, which is expected because they identify individual orders and customers.
---

## 7. staging.products

### Missing Values
- product_category_name we have 610 missing values 
product_name_lenght we have 610 missing values product_description_length we have 610 missing values  products_photos_qty we have 610 missing values 
product_weight_g we have 2 missing values 
product_lenght_cm we have 2 missing values 
product_width_cm we have 2 missing values 

### Data Types
- ### Data Types
- No obvious wrong data types were identified.
- Product dimension and descriptive-length columns are stored as numeric fields using `double precision`.
- `product_id` and `product_category_name` are stored as `text`, which is appropriate because they represent identifiers and categories.

### Duplicates
-  No exact duplicate business rows were identified.

### Outliers or Suspicious Values
- SQL validation identified 4 products with zero or negative values in `product_weight_g`. Product weight should be positive, so these records should be reviewed during cleaning.
- No zero or negative values were identified in `product_length_cm`, `product_height_cm`, or `product_width_cm`.
- The maximum observed product weight is 40,425 grams, which is approximately 40.4 kg. This is an extreme value and should be reviewed before using product weight in shipping or logistics analysis.
- The maximum observed dimensions are 105 cm for length, 105 cm for height, and 118 cm for width. These values are large but may be valid depending on the product category.
- The top-weight and top-height inspections also showed some products with missing category or dimension values. These missing records should be handled carefully during cleaning, especially before category-level or logistics analysis.

### Cardinality
- `product_category_name` is a useful categorical column because it groups products into business categories.
- This column will be important later for category-level analysis, such as revenue by product category and product mix analysis.
- `product_id` has high cardinality, which is expected because it identifies individual products.

---

## 8. staging.sellers

### Missing Values
- 

### Data Types
- 

### Duplicates
- 

### Outliers or Suspicious Values
- 

### Cardinality
- Seller city and state fields may become useful geographic dimensions.

---

## 9. staging.categories

### Missing Values
- 

### Data Types
- 

### Duplicates
- 

### Outliers or Suspicious Values
- 

### Cardinality
- This is a lookup table that maps Portuguese product category names to English category names.