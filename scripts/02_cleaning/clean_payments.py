"""
Clean the staging.payments table and write the result to clean.payments.

This script:
- Reads payment data from the staging schema
- Standardizes payment_type
- Removes invalid payment values
- Removes invalid installment and payment sequence values
- Removes duplicate payment records defensively
- Engineers payment behavior features
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


def standardize_payment_type(series):
    """
    Standardize payment type values by trimming spaces and converting to lowercase.
    """
    return series.astype("string").str.strip().str.lower()


def clean_payments(engine):
    """
    Clean staging.payments and write the cleaned result to clean.payments.
    """
    logging.info("Starting payments cleaning process.")

    # ----- STEP 1: Load raw data from staging -----
    df = pd.read_sql("SELECT * FROM staging.payments", engine)
    original_count = len(df)

    logging.info("Loaded %s rows from staging.payments.", original_count)
    print(f"Loaded {original_count} rows from staging.payments.")

    # ----- STEP 2: Standardize payment_type -----
    df["payment_type"] = standardize_payment_type(df["payment_type"])
    df["payment_type"] = df["payment_type"].fillna("unknown")

    # ----- STEP 3: Convert numeric columns safely -----
    numeric_columns = [
        "payment_sequential",
        "payment_installments",
        "payment_value",
    ]

    for column in numeric_columns:
        df[column] = pd.to_numeric(df[column], errors="coerce")

    # ----- STEP 4: Remove rows with missing critical numeric values -----
    before_missing_filter = len(df)
    df = df.dropna(subset=numeric_columns).copy()
    missing_numeric_rows_removed = before_missing_filter - len(df)

    if missing_numeric_rows_removed > 0:
        logging.warning(
            "Removed %s rows with missing critical numeric payment values.",
            missing_numeric_rows_removed,
        )

    # ----- STEP 5: Remove invalid payment sequence values -----
    before_sequence_filter = len(df)
    df = df[df["payment_sequential"] > 0].copy()
    invalid_sequence_rows_removed = before_sequence_filter - len(df)

    if invalid_sequence_rows_removed > 0:
        logging.warning(
            "Removed %s rows with invalid payment_sequential.",
            invalid_sequence_rows_removed,
        )

    # ----- STEP 6: Remove invalid installment values -----
    before_installment_filter = len(df)
    df = df[df["payment_installments"] >= 0].copy()
    invalid_installment_rows_removed = before_installment_filter - len(df)

    if invalid_installment_rows_removed > 0:
        logging.warning(
            "Removed %s rows with negative payment_installments.",
            invalid_installment_rows_removed,
        )

    # ----- STEP 7: Remove invalid payment values -----
    before_payment_value_filter = len(df)
    df = df[df["payment_value"] > 0].copy()
    invalid_payment_value_rows_removed = before_payment_value_filter - len(df)

    if invalid_payment_value_rows_removed > 0:
        logging.warning(
            "Removed %s rows with zero or negative payment_value.",
            invalid_payment_value_rows_removed,
        )

    # ----- STEP 8: Defensive duplicate removal -----
    before_dedup = len(df)
    df = df.drop_duplicates(subset=["order_id", "payment_sequential"])
    duplicates_removed = before_dedup - len(df)

    if duplicates_removed > 0:
        logging.warning(
            "Removed %s duplicate order_id/payment_sequential rows.",
            duplicates_removed,
        )

    # ----- STEP 9: Engineer payment features -----
    df["is_installment_payment"] = df["payment_installments"] > 1

    df["payment_value_per_installment"] = df.apply(
        lambda row: (
            round(row["payment_value"] / row["payment_installments"], 2)
            if row["payment_installments"] > 0
            else pd.NA
        ),
        axis=1,
    )

    # ----- STEP 10: Validate cleaned result -----
    assert df["order_id"].notna().all(), "order_id has null values."
    assert df["payment_type"].notna().all(), "payment_type has null values."
    assert df["payment_sequential"].notna().all(), (
        "payment_sequential has null values."
    )
    assert df["payment_installments"].notna().all(), (
        "payment_installments has null values."
    )
    assert df["payment_value"].notna().all(), "payment_value has null values."

    assert (df["payment_sequential"] > 0).all(), (
        "payment_sequential contains zero or negative values."
    )
    assert (df["payment_installments"] >= 0).all(), (
        "payment_installments contains negative values."
    )
    assert (df["payment_value"] > 0).all(), (
        "payment_value contains zero or negative values."
    )

    assert not df.duplicated(
        subset=["order_id", "payment_sequential"]
    ).any(), "Duplicate order_id/payment_sequential combinations still exist."

    logging.info("Validation checks passed for clean.payments.")

    # ----- STEP 11: Write to clean schema -----
    with engine.begin() as connection:
        connection.execute(text("CREATE SCHEMA IF NOT EXISTS clean"))

    df.to_sql(
        name="payments",
        con=engine,
        schema="clean",
        if_exists="replace",
        index=False,
        chunksize=1000,
    )

    logging.info(
        "Finished payments cleaning. Original rows: %s. Clean rows: %s. "
        "Missing numeric rows removed: %s. Invalid sequence rows removed: %s. "
        "Invalid installment rows removed: %s. Invalid payment value rows removed: %s. "
        "Duplicates removed: %s.",
        original_count,
        len(df),
        missing_numeric_rows_removed,
        invalid_sequence_rows_removed,
        invalid_installment_rows_removed,
        invalid_payment_value_rows_removed,
        duplicates_removed,
    )

    print("Payments cleaning completed successfully.")
    print(f"Original rows: {original_count}")
    print(f"Clean rows: {len(df)}")
    print(f"Missing numeric rows removed: {missing_numeric_rows_removed}")
    print(f"Invalid sequence rows removed: {invalid_sequence_rows_removed}")
    print(f"Invalid installment rows removed: {invalid_installment_rows_removed}")
    print(f"Invalid payment value rows removed: {invalid_payment_value_rows_removed}")
    print(f"Duplicates removed: {duplicates_removed}")
    print("Written to PostgreSQL table: clean.payments")


def main():
    """
    Run the payments cleaning pipeline.
    """
    engine = get_database_engine()
    clean_payments(engine)


if __name__ == "__main__":
    main()