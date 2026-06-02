# Warehouse Design

This document describes the analytical data warehouse design for the Egyptian Retail & Financial Analytics Platform.

The warehouse uses a star schema, which is optimized for business intelligence, reporting, and analytical queries.

---

## 1. Purpose of the Warehouse

The cleaned data in the `clean` schema is still close to the original transactional structure. While this is useful for data preparation, it is not ideal for business reporting because many tables must be joined repeatedly.

The `warehouse` schema restructures the cleaned data into a star schema so that revenue, orders, delivery performance, customer behavior, and product performance can be analyzed more easily.

---

## 2. Star Schema Overview

The warehouse contains one central fact table and several dimension tables.

### Fact Table

- `warehouse.fact_order_items`

This table stores measurable business events at the order-item level. Each row represents one product item within an order.

### Dimension Tables

- `warehouse.dim_date`
- `warehouse.dim_customer`
- `warehouse.dim_product`
- `warehouse.dim_seller`

Dimension tables describe the business context of each fact row.

---

## 3. Fact Table Grain

The grain of `fact_order_items` is:

One row per order item.

This means that if one order contains three products, the fact table will contain three rows for that order.

---

## 4. Key Metrics

The fact table will support metrics such as:

- Total revenue
- Freight value
- Total item value
- Number of orders
- Number of sold items
- Delivery duration
- On-time delivery rate

---

## 5. Key Dimensions

The warehouse supports analysis by:

- Date
- Customer location
- Product category
- Seller location
- Delivery status

---

## 6. Warehouse Loading Process

The warehouse is loaded from the cleaned tables in the `clean` schema.

Dimension tables are loaded first:

- `warehouse.dim_customer`
- `warehouse.dim_product`
- `warehouse.dim_seller`
- `warehouse.dim_date`

The fact table, `warehouse.fact_order_items`, is loaded after the dimensions.

Natural keys from the cleaned data, such as `customer_id`, `product_id`, and `seller_id`, are mapped to warehouse surrogate keys, such as `customer_key`, `product_key`, and `seller_key`.

This design makes analytical queries easier because the fact table stores numeric measures while the dimension tables store descriptive business context.

---

## 7. Query Performance and Indexing

To evaluate query performance, an analytical monthly revenue query was tested using `EXPLAIN ANALYZE`.

The query was first executed before adding indexes to record the baseline execution time. Indexes were then added to the fact table foreign key columns, and the same query was executed again to compare performance.

### Query Tested

The query calculates monthly revenue and order count by joining `warehouse.fact_order_items` with `warehouse.dim_date`.

### Baseline Execution Time

* Before indexes: 125.515 ms

### Indexes Added

* `idx_fact_purchase_date`
* `idx_fact_delivery_date`
* `idx_fact_customer`
* `idx_fact_product`
* `idx_fact_seller`
* `idx_fact_order_id`

### Execution Time After Indexing

* After indexes: 128.877 ms

### Interpretation

After adding indexes, the monthly revenue query execution time changed from 125.515 ms to 128.877 ms. This means the indexed version was slightly slower for this specific query, with a difference of 3.362 ms.

This result is acceptable because the fact table currently contains a relatively small number of rows for PostgreSQL. For a full-table aggregation query like monthly revenue, PostgreSQL may still prefer scanning the full table instead of using indexes, because the query needs to read a large portion of the fact table anyway.

The indexes are still useful for future scalability and for more selective analytical queries, such as filtering by a specific date range, customer, product, seller, or order. As the dataset grows, these indexes can help improve join and filtering performance.
