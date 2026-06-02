CREATE SCHEMA IF NOT EXISTS warehouse;

DROP TABLE IF EXISTS warehouse.fact_order_items;
DROP TABLE IF EXISTS warehouse.dim_customer;
DROP TABLE IF EXISTS warehouse.dim_product;
DROP TABLE IF EXISTS warehouse.dim_seller;
DROP TABLE IF EXISTS warehouse.dim_date;

CREATE TABLE warehouse.dim_date (
    date_key INTEGER PRIMARY KEY,
    full_date DATE NOT NULL,
    year INTEGER NOT NULL,
    quarter INTEGER NOT NULL,
    quarter_name VARCHAR(10) NOT NULL,
    month_num INTEGER NOT NULL,
    month_name VARCHAR(20) NOT NULL,
    week_of_year INTEGER NOT NULL,
    day_of_week INTEGER NOT NULL,
    day_name VARCHAR(20) NOT NULL,
    is_weekend BOOLEAN NOT NULL,
    is_holiday BOOLEAN DEFAULT FALSE
);

CREATE TABLE warehouse.dim_customer (
    customer_key INTEGER PRIMARY KEY,
    customer_id VARCHAR(50) NOT NULL UNIQUE,
    customer_unique_id VARCHAR(50),
    customer_zip_code_prefix INTEGER,
    customer_city VARCHAR(100),
    customer_state VARCHAR(10),
    customer_city_state VARCHAR(120)
);

CREATE TABLE warehouse.dim_product (
    product_key INTEGER PRIMARY KEY,
    product_id VARCHAR(50) NOT NULL UNIQUE,
    product_category_name VARCHAR(100),
    product_category_name_english VARCHAR(100),
    product_weight_g NUMERIC(10,2),
    product_length_cm NUMERIC(10,2),
    product_height_cm NUMERIC(10,2),
    product_width_cm NUMERIC(10,2),
    has_product_metadata BOOLEAN
);

CREATE TABLE warehouse.dim_seller (
    seller_key INTEGER PRIMARY KEY,
    seller_id VARCHAR(50) NOT NULL UNIQUE,
    seller_zip_code_prefix INTEGER,
    seller_city VARCHAR(100),
    seller_state VARCHAR(10),
    seller_city_state VARCHAR(120)
);

CREATE TABLE warehouse.fact_order_items (
    order_item_sk SERIAL PRIMARY KEY,
    order_id VARCHAR(50) NOT NULL,
    order_item_id INTEGER NOT NULL,
    customer_key INTEGER REFERENCES warehouse.dim_customer(customer_key),
    product_key INTEGER REFERENCES warehouse.dim_product(product_key),
    seller_key INTEGER REFERENCES warehouse.dim_seller(seller_key),
    purchase_date_key INTEGER REFERENCES warehouse.dim_date(date_key),
    delivery_date_key INTEGER REFERENCES warehouse.dim_date(date_key),
    price NUMERIC(10,2),
    freight_value NUMERIC(10,2),
    total_item_value NUMERIC(10,2),
    days_to_deliver NUMERIC(10,1),
    delivered_on_time BOOLEAN,
    has_timeline_issue BOOLEAN
);