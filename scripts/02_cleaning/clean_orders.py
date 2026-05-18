"""
Clean the staging.orders table and write the result to clean.orders.

This script performs the first Phase 2 cleaning task:
- Reads raw orders from PostgreSQL staging schema
- Converts timestamp columns from text to datetime
- Preserves business-meaningful nulls using boolean flags
- Flags suspicious timeline values
- Engineers delivery-related features
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


DATE_COLUMNS = [
    "order_purchase_timestamp",
    "order_approved_at",
    "order_delivered_carrier_date",
    "order_delivered_customer_date",
    "order_estimated_delivery_date",
]


def get_database_engine():
    """
    Create and return a SQLAlchemy database engine.

    The password is read from the DB_PASSWORD environment variable to avoid
    hardcoding credentials in source code.
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


def calculate_days_between(df, end_column, start_column):
    """
    Calculate the number of days between two datetime columns.

    Missing dates produce missing results, which is correct because we should
    not invent dates or durations where the raw data is incomplete.
    """
    return (
        (df[end_column] - df[start_column])
        .dt.total_seconds()
        .div(86400)
        .round(1)
    )


def clean_orders(engine):
    """
    Clean staging.orders and write the cleaned result to clean.orders.
    """
    logging.info("Starting orders cleaning process.")

    # ----- STEP 1: Load raw data from staging -----
    df = pd.read_sql("SELECT * FROM staging.orders", engine)
    original_count = len(df)

    logging.info("Loaded %s rows from staging.orders.", original_count)
    print(f"Loaded {original_count} rows from staging.orders.")

    # ----- STEP 2: Convert timestamp columns from text to datetime -----
    for column in DATE_COLUMNS:
        df[column] = pd.to_datetime(df[column], errors="coerce")

    logging.info("Converted order timestamp columns to datetime.")

    # ----- STEP 3: Create business flags for meaningful nulls -----
    df["is_approved"] = df["order_approved_at"].notna()
    df["is_delivered_to_carrier"] = df["order_delivered_carrier_date"].notna()
    df["is_delivered_to_customer"] = df["order_delivered_customer_date"].notna()

    # ----- STEP 4: Defensive duplicate removal -----
    before_dedup = len(df)
    df = df.drop_duplicates(subset=["order_id"])
    duplicates_removed = before_dedup - len(df)

    if duplicates_removed > 0:
        logging.warning("Removed %s duplicate order_id rows.", duplicates_removed)

    # ----- STEP 5: Flag suspicious timeline values -----
    df["approved_before_purchase"] = (
        df["order_approved_at"].notna()
        & df["order_purchase_timestamp"].notna()
        & (df["order_approved_at"] < df["order_purchase_timestamp"])
    )

    df["carrier_before_purchase"] = (
        df["order_delivered_carrier_date"].notna()
        & df["order_purchase_timestamp"].notna()
        & (df["order_delivered_carrier_date"] < df["order_purchase_timestamp"])
    )

    df["customer_delivery_before_purchase"] = (
        df["order_delivered_customer_date"].notna()
        & df["order_purchase_timestamp"].notna()
        & (df["order_delivered_customer_date"] < df["order_purchase_timestamp"])
    )

    df["customer_delivery_before_carrier"] = (
        df["order_delivered_customer_date"].notna()
        & df["order_delivered_carrier_date"].notna()
        & (df["order_delivered_customer_date"] < df["order_delivered_carrier_date"])
    )

    df["estimated_delivery_before_purchase"] = (
        df["order_estimated_delivery_date"].notna()
        & df["order_purchase_timestamp"].notna()
        & (df["order_estimated_delivery_date"] < df["order_purchase_timestamp"])
    )

    timeline_issue_columns = [
        "approved_before_purchase",
        "carrier_before_purchase",
        "customer_delivery_before_purchase",
        "customer_delivery_before_carrier",
        "estimated_delivery_before_purchase",
    ]

    df["has_timeline_issue"] = df[timeline_issue_columns].any(axis=1)

    # ----- STEP 6: Engineer useful time-based features -----
    df["days_to_approve"] = calculate_days_between(
        df, "order_approved_at", "order_purchase_timestamp"
    )

    df["days_to_carrier"] = calculate_days_between(
        df, "order_delivered_carrier_date", "order_purchase_timestamp"
    )

    df["days_to_deliver"] = calculate_days_between(
        df, "order_delivered_customer_date", "order_purchase_timestamp"
    )

    df["days_carrier_to_customer"] = calculate_days_between(
        df, "order_delivered_customer_date", "order_delivered_carrier_date"
    )

    df["delivered_on_time"] = (
        df["order_delivered_customer_date"].notna()
        & df["order_estimated_delivery_date"].notna()
        & (df["order_delivered_customer_date"] <= df["order_estimated_delivery_date"])
    )

    # ----- STEP 7: Validate cleaned result -----
    assert df["order_id"].notna().all(), "order_id has null values."
    assert df["order_id"].is_unique, "order_id is not unique after cleaning."

    for column in DATE_COLUMNS:
        assert pd.api.types.is_datetime64_any_dtype(
            df[column]
        ), f"{column} was not converted to datetime."

    assert (
        df["days_to_deliver"].dropna() >= 0
    ).all(), "days_to_deliver contains negative values."

    logging.info("Validation checks passed for clean.orders.")

    # ----- STEP 8: Write to clean schema -----
    with engine.begin() as connection:
        connection.execute(text("CREATE SCHEMA IF NOT EXISTS clean"))

    df.to_sql(
        name="orders",
        con=engine,
        schema="clean",
        if_exists="replace",
        index=False,
        chunksize=1000,
    )

    logging.info(
        "Finished orders cleaning. Original rows: %s. Clean rows: %s. Duplicates removed: %s.",
        original_count,
        len(df),
        duplicates_removed,
    )

    print("Orders cleaning completed successfully.")
    print(f"Original rows: {original_count}")
    print(f"Clean rows: {len(df)}")
    print(f"Duplicates removed: {duplicates_removed}")
    print("Written to PostgreSQL table: clean.orders")


def main():
    """
    Run the orders cleaning pipeline.
    """
    engine = get_database_engine()
    clean_orders(engine)


if __name__ == "__main__":
    main()