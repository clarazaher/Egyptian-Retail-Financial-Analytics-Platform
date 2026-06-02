"""
Clean the staging.order_items table and write the result to clean.order_items.

This script:
- Reads order item data from the staging schema
- Converts shipping_limit_date to datetime
- Removes invalid price and freight values
- Removes duplicate order item rows defensively
- Creates total_item_value
- Validates the cleaned result
- Writes the cleaned table to the clean schema

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
    filename=LOG_DIR / "cleaning.log",
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


def clean_order_items(engine):
    """
    Clean staging.order_items and write the cleaned result to clean.order_items.
    """
    logging.info("Starting order_items cleaning process.")

    # ----- STEP 1: Load raw data from staging -----
    df = pd.read_sql("SELECT * FROM staging.order_items", engine)
    original_count = len(df)

    logging.info("Loaded %s rows from staging.order_items.", original_count)
    print(f"Loaded {original_count} rows from staging.order_items.")

    # ----- STEP 2: Convert shipping_limit_date to datetime -----
    df["shipping_limit_date"] = pd.to_datetime(
        df["shipping_limit_date"],
        errors="coerce",
    )

    # ----- STEP 3: Remove invalid price values -----
    before_price_filter = len(df)
    df = df[df["price"] > 0].copy()
    invalid_price_rows_removed = before_price_filter - len(df)

    if invalid_price_rows_removed > 0:
        logging.warning(
            "Removed %s rows with zero or negative price.",
            invalid_price_rows_removed,
        )

    # ----- STEP 4: Remove invalid freight values -----
    before_freight_filter = len(df)
    df = df[df["freight_value"] >= 0].copy()
    invalid_freight_rows_removed = before_freight_filter - len(df)

    if invalid_freight_rows_removed > 0:
        logging.warning(
            "Removed %s rows with negative freight_value.",
            invalid_freight_rows_removed,
        )

    # ----- STEP 5: Defensive duplicate removal -----
    before_dedup = len(df)
    df = df.drop_duplicates(subset=["order_id", "order_item_id"])
    duplicates_removed = before_dedup - len(df)

    if duplicates_removed > 0:
        logging.warning(
            "Removed %s duplicate order_id/order_item_id rows.",
            duplicates_removed,
        )

    # ----- STEP 6: Engineer total item value -----
    df["total_item_value"] = (df["price"] + df["freight_value"]).round(2)

    # ----- STEP 7: Validate cleaned result -----
    assert df["order_id"].notna().all(), "order_id has null values."
    assert df["order_item_id"].notna().all(), "order_item_id has null values."
    assert df["product_id"].notna().all(), "product_id has null values."
    assert df["seller_id"].notna().all(), "seller_id has null values."

    assert pd.api.types.is_datetime64_any_dtype(
        df["shipping_limit_date"]
    ), "shipping_limit_date was not converted to datetime."

    assert (df["price"] > 0).all(), "price contains zero or negative values."
    assert (df["freight_value"] >= 0).all(), "freight_value contains negative values."
    assert (df["total_item_value"] > 0).all(), "total_item_value contains invalid values."

    assert not df.duplicated(subset=["order_id", "order_item_id"]).any(), (
        "Duplicate order_id/order_item_id combinations still exist."
    )

    logging.info("Validation checks passed for clean.order_items.")

    # ----- STEP 8: Write to clean schema -----
    with engine.begin() as connection:
        connection.execute(text("CREATE SCHEMA IF NOT EXISTS clean"))

    df.to_sql(
        name="order_items",
        con=engine,
        schema="clean",
        if_exists="replace",
        index=False,
        chunksize=1000,
    )

    logging.info(
        "Finished order_items cleaning. Original rows: %s. Clean rows: %s. "
        "Invalid price rows removed: %s. Invalid freight rows removed: %s. "
        "Duplicates removed: %s.",
        original_count,
        len(df),
        invalid_price_rows_removed,
        invalid_freight_rows_removed,
        duplicates_removed,
    )

    print("Order items cleaning completed successfully.")
    print(f"Original rows: {original_count}")
    print(f"Clean rows: {len(df)}")
    print(f"Invalid price rows removed: {invalid_price_rows_removed}")
    print(f"Invalid freight rows removed: {invalid_freight_rows_removed}")
    print(f"Duplicates removed: {duplicates_removed}")
    print("Written to PostgreSQL table: clean.order_items")


def main():
    """
    Run the order_items cleaning pipeline.
    """
    engine = get_database_engine()
    clean_order_items(engine)


if __name__ == "__main__":
    main()