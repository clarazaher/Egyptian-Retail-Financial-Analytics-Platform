"""
Load the warehouse star schema from the clean schema.

This script:
- Loads warehouse dimension tables from cleaned data
- Assigns surrogate keys to customers, products, and sellers
- Builds natural-key to surrogate-key mapping tables
- Loads the central warehouse.fact_order_items table
- Validates key relationships and important metrics

The database password is read from the DB_PASSWORD environment variable.
"""

import logging
import os
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text


DB_HOST = "localhost"
DB_PORT = "5432"
DB_NAME = "egyptian_retail_db"
DB_USER = "postgres"
DB_PASSWORD = os.environ.get("DB_PASSWORD")

LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    filename=LOG_DIR / "warehouse.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)


def get_database_engine():
    """
    Create and return a SQLAlchemy database engine.
    """
    if not DB_PASSWORD:
        raise EnvironmentError(
            "DB_PASSWORD environment variable is not set. "
            "Run: export DB_PASSWORD='your_password_here'"
        )

    connection_string = (
        f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    )

    return create_engine(connection_string)


def truncate_warehouse_tables(engine):
    """
    Clear warehouse dimension and fact tables before loading fresh data.

    dim_date is not truncated here because it is populated separately by
    02_populate_dim_date.py.
    """
    logging.info("Truncating warehouse tables before reload.")

    with engine.begin() as connection:
        connection.execute(
            text(
                """
                TRUNCATE TABLE
                    warehouse.fact_order_items,
                    warehouse.dim_customer,
                    warehouse.dim_product,
                    warehouse.dim_seller
                RESTART IDENTITY CASCADE
                """
            )
        )


def date_to_key(series):
    """
    Convert a datetime-like pandas Series to YYYYMMDD integer date keys.

    Missing dates remain missing, which is important for undelivered orders.
    """
    return pd.to_datetime(series, errors="coerce").dt.strftime("%Y%m%d").astype("Int64")


def load_dim_customer(engine):
    """
    Load warehouse.dim_customer and return customer_id to customer_key mapping.
    """
    query = """
        SELECT DISTINCT
            customer_id,
            customer_unique_id,
            customer_zip_code_prefix,
            customer_city,
            customer_state,
            customer_city_state
        FROM clean.customers
    """

    df = pd.read_sql(query, engine)

    df = df.sort_values("customer_id").reset_index(drop=True)
    df["customer_key"] = df.index + 1

    dim_customer = df[
        [
            "customer_key",
            "customer_id",
            "customer_unique_id",
            "customer_zip_code_prefix",
            "customer_city",
            "customer_state",
            "customer_city_state",
        ]
    ]

    assert dim_customer["customer_key"].is_unique, "customer_key is not unique."
    assert dim_customer["customer_id"].is_unique, "customer_id is not unique."

    dim_customer.to_sql(
        name="dim_customer",
        con=engine,
        schema="warehouse",
        if_exists="append",
        index=False,
        chunksize=1000,
    )

    print(f"Loaded {len(dim_customer)} rows into warehouse.dim_customer.")
    logging.info("Loaded %s rows into warehouse.dim_customer.", len(dim_customer))

    return dim_customer[["customer_id", "customer_key"]]


def load_dim_product(engine):
    """
    Load warehouse.dim_product and return product_id to product_key mapping.
    """
    query = """
        SELECT DISTINCT
            product_id,
            product_category_name,
            product_category_name_english,
            product_weight_g,
            product_length_cm,
            product_height_cm,
            product_width_cm,
            has_product_metadata
        FROM clean.products
    """

    df = pd.read_sql(query, engine)

    df = df.sort_values("product_id").reset_index(drop=True)
    df["product_key"] = df.index + 1

    dim_product = df[
        [
            "product_key",
            "product_id",
            "product_category_name",
            "product_category_name_english",
            "product_weight_g",
            "product_length_cm",
            "product_height_cm",
            "product_width_cm",
            "has_product_metadata",
        ]
    ]

    assert dim_product["product_key"].is_unique, "product_key is not unique."
    assert dim_product["product_id"].is_unique, "product_id is not unique."

    dim_product.to_sql(
        name="dim_product",
        con=engine,
        schema="warehouse",
        if_exists="append",
        index=False,
        chunksize=1000,
    )

    print(f"Loaded {len(dim_product)} rows into warehouse.dim_product.")
    logging.info("Loaded %s rows into warehouse.dim_product.", len(dim_product))

    return dim_product[["product_id", "product_key"]]


def load_dim_seller(engine):
    """
    Load warehouse.dim_seller and return seller_id to seller_key mapping.
    """
    query = """
        SELECT DISTINCT
            seller_id,
            seller_zip_code_prefix,
            seller_city,
            seller_state,
            seller_city_state
        FROM clean.sellers
    """

    df = pd.read_sql(query, engine)

    df = df.sort_values("seller_id").reset_index(drop=True)
    df["seller_key"] = df.index + 1

    dim_seller = df[
        [
            "seller_key",
            "seller_id",
            "seller_zip_code_prefix",
            "seller_city",
            "seller_state",
            "seller_city_state",
        ]
    ]

    assert dim_seller["seller_key"].is_unique, "seller_key is not unique."
    assert dim_seller["seller_id"].is_unique, "seller_id is not unique."

    dim_seller.to_sql(
        name="dim_seller",
        con=engine,
        schema="warehouse",
        if_exists="append",
        index=False,
        chunksize=1000,
    )

    print(f"Loaded {len(dim_seller)} rows into warehouse.dim_seller.")
    logging.info("Loaded %s rows into warehouse.dim_seller.", len(dim_seller))

    return dim_seller[["seller_id", "seller_key"]]


def validate_dim_date_exists(engine):
    """
    Validate that warehouse.dim_date has been populated.
    """
    count = pd.read_sql(
        "SELECT COUNT(*) AS row_count FROM warehouse.dim_date",
        engine,
    )["row_count"].iloc[0]

    assert count > 0, "warehouse.dim_date is empty. Run 02_populate_dim_date.py first."

    print(f"warehouse.dim_date already contains {count} rows.")
    logging.info("warehouse.dim_date contains %s rows.", count)


def load_fact_order_items(engine, customer_map, product_map, seller_map):
    """
    Load warehouse.fact_order_items using cleaned order and order-item data.
    """
    query = """
        SELECT
            oi.order_id,
            oi.order_item_id,
            o.customer_id,
            oi.product_id,
            oi.seller_id,
            o.order_purchase_timestamp,
            o.order_delivered_customer_date,
            oi.price,
            oi.freight_value,
            oi.total_item_value,
            o.days_to_deliver,
            o.delivered_on_time,
            o.has_timeline_issue
        FROM clean.order_items oi
        INNER JOIN clean.orders o
            ON oi.order_id = o.order_id
    """

    df = pd.read_sql(query, engine)

    original_count = len(df)

    df = df.merge(customer_map, on="customer_id", how="left")
    df = df.merge(product_map, on="product_id", how="left")
    df = df.merge(seller_map, on="seller_id", how="left")

    df["purchase_date_key"] = date_to_key(df["order_purchase_timestamp"])
    df["delivery_date_key"] = date_to_key(df["order_delivered_customer_date"])

    fact_df = df[
        [
            "order_id",
            "order_item_id",
            "customer_key",
            "product_key",
            "seller_key",
            "purchase_date_key",
            "delivery_date_key",
            "price",
            "freight_value",
            "total_item_value",
            "days_to_deliver",
            "delivered_on_time",
            "has_timeline_issue",
        ]
    ].copy()

    fact_df["order_item_id"] = fact_df["order_item_id"].astype(int)

    assert len(fact_df) == original_count, "Fact table row count changed unexpectedly."
    assert fact_df["customer_key"].notna().all(), "Some rows have missing customer_key."
    assert fact_df["product_key"].notna().all(), "Some rows have missing product_key."
    assert fact_df["seller_key"].notna().all(), "Some rows have missing seller_key."
    assert fact_df["purchase_date_key"].notna().all(), "Some rows have missing purchase_date_key."
    assert (fact_df["price"] > 0).all(), "Fact table contains invalid price values."
    assert (fact_df["freight_value"] >= 0).all(), "Fact table contains invalid freight values."
    assert (fact_df["total_item_value"] > 0).all(), (
        "Fact table contains invalid total_item_value values."
    )

    fact_df.to_sql(
        name="fact_order_items",
        con=engine,
        schema="warehouse",
        if_exists="append",
        index=False,
        chunksize=1000,
    )

    print(f"Loaded {len(fact_df)} rows into warehouse.fact_order_items.")
    logging.info("Loaded %s rows into warehouse.fact_order_items.", len(fact_df))


def load_warehouse(engine):
    """
    Run the full warehouse loading process.
    """
    logging.info("Starting warehouse load process.")

    validate_dim_date_exists(engine)
    truncate_warehouse_tables(engine)

    customer_map = load_dim_customer(engine)
    product_map = load_dim_product(engine)
    seller_map = load_dim_seller(engine)

    load_fact_order_items(
        engine=engine,
        customer_map=customer_map,
        product_map=product_map,
        seller_map=seller_map,
    )

    logging.info("Warehouse load completed successfully.")
    print("Warehouse load completed successfully.")


def main():
    """
    Run the warehouse load pipeline.
    """
    engine = get_database_engine()
    load_warehouse(engine)


if __name__ == "__main__":
    main()