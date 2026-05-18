"""
Clean the staging.customers table and write the result to clean.customers.

This script:
- Reads customer data from the staging schema
- Standardizes city and state text fields
- Creates a combined customer_city_state field
- Removes duplicate customer_id rows defensively
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


def standardize_city_column(series):
    """
    Standardize city names by trimming spaces and converting to title case.
    """
    return series.astype("string").str.strip().str.title()


def standardize_state_column(series):
    """
    Standardize state abbreviations by trimming spaces and converting to uppercase.
    """
    return series.astype("string").str.strip().str.upper()


def clean_customers(engine):
    """
    Clean staging.customers and write the cleaned result to clean.customers.
    """
    logging.info("Starting customers cleaning process.")

    # ----- STEP 1: Load raw data from staging -----
    df = pd.read_sql("SELECT * FROM staging.customers", engine)
    original_count = len(df)

    logging.info("Loaded %s rows from staging.customers.", original_count)
    print(f"Loaded {original_count} rows from staging.customers.")

    # ----- STEP 2: Standardize city and state text -----
    df["customer_city"] = standardize_city_column(df["customer_city"])
    df["customer_state"] = standardize_state_column(df["customer_state"])

    # ----- STEP 3: Create combined location field -----
    df["customer_city_state"] = (
        df["customer_city"] + ", " + df["customer_state"]
    )

    # ----- STEP 4: Defensive duplicate removal -----
    before_dedup = len(df)
    df = df.drop_duplicates(subset=["customer_id"])
    duplicates_removed = before_dedup - len(df)

    if duplicates_removed > 0:
        logging.warning("Removed %s duplicate customer_id rows.", duplicates_removed)

    # ----- STEP 5: Validate cleaned result -----
    assert df["customer_id"].notna().all(), "customer_id has null values."
    assert df["customer_id"].is_unique, "customer_id is not unique after cleaning."
    assert df["customer_unique_id"].notna().all(), "customer_unique_id has null values."
    assert df["customer_city"].notna().all(), "customer_city has null values."
    assert df["customer_state"].notna().all(), "customer_state has null values."
    assert df["customer_city_state"].notna().all(), "customer_city_state has null values."

    logging.info("Validation checks passed for clean.customers.")

    # ----- STEP 6: Write to clean schema -----
    with engine.begin() as connection:
        connection.execute(text("CREATE SCHEMA IF NOT EXISTS clean"))

    df.to_sql(
        name="customers",
        con=engine,
        schema="clean",
        if_exists="replace",
        index=False,
        chunksize=1000,
    )

    logging.info(
        "Finished customers cleaning. Original rows: %s. Clean rows: %s. "
        "Duplicates removed: %s.",
        original_count,
        len(df),
        duplicates_removed,
    )

    print("Customers cleaning completed successfully.")
    print(f"Original rows: {original_count}")
    print(f"Clean rows: {len(df)}")
    print(f"Duplicates removed: {duplicates_removed}")
    print("Written to PostgreSQL table: clean.customers")


def main():
    """
    Run the customers cleaning pipeline.
    """
    engine = get_database_engine()
    clean_customers(engine)


if __name__ == "__main__":
    main()