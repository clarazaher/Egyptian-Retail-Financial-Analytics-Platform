"""
Clean the staging.reviews table and write the result to clean.reviews.

This script:
- Reads review data from the staging schema
- Converts review date columns to datetime
- Preserves missing review text while adding useful boolean flags
- Validates review scores
- Flags suspicious review response timelines
- Engineers response_time_days
- Removes exact duplicate rows defensively
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
    "review_creation_date",
    "review_answer_timestamp",
]


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


def calculate_days_between(df, end_column, start_column):
    """
    Calculate the number of days between two datetime columns.

    Missing dates produce missing results, which is correct because we should
    not invent response times where the raw data is incomplete.
    """
    return (
        (df[end_column] - df[start_column])
        .dt.total_seconds()
        .div(86400)
        .round(1)
    )


def clean_reviews(engine):
    """
    Clean staging.reviews and write the cleaned result to clean.reviews.
    """
    logging.info("Starting reviews cleaning process.")

    # ----- STEP 1: Load raw data from staging -----
    df = pd.read_sql("SELECT * FROM staging.reviews", engine)
    original_count = len(df)

    logging.info("Loaded %s rows from staging.reviews.", original_count)
    print(f"Loaded {original_count} rows from staging.reviews.")

    # ----- STEP 2: Convert date columns to datetime -----
    for column in DATE_COLUMNS:
        df[column] = pd.to_datetime(df[column], errors="coerce")

    # ----- STEP 3: Standardize text comment columns -----
    text_columns = ["review_comment_title", "review_comment_message"]

    for column in text_columns:
        df[column] = df[column].astype("string").str.strip()
        df[column] = df[column].replace("", pd.NA)

    # ----- STEP 4: Add comment availability flags -----
    df["has_review_title"] = df["review_comment_title"].notna()
    df["has_review_message"] = df["review_comment_message"].notna()

    # ----- STEP 5: Defensive exact duplicate removal -----
    before_dedup = len(df)
    df = df.drop_duplicates()
    duplicates_removed = before_dedup - len(df)

    if duplicates_removed > 0:
        logging.warning("Removed %s exact duplicate review rows.", duplicates_removed)

    # ----- STEP 6: Flag suspicious review response timelines -----
    df["answer_before_review_creation"] = (
        df["review_answer_timestamp"].notna()
        & df["review_creation_date"].notna()
        & (df["review_answer_timestamp"] < df["review_creation_date"])
    )

    # ----- STEP 7: Engineer response time feature -----
    df["response_time_days"] = calculate_days_between(
        df,
        "review_answer_timestamp",
        "review_creation_date",
    )

    # ----- STEP 8: Validate cleaned result -----
    assert df["review_id"].notna().all(), "review_id has null values."
    assert df["order_id"].notna().all(), "order_id has null values."
    assert df["review_score"].notna().all(), "review_score has null values."

    assert df["review_score"].between(1, 5).all(), (
        "review_score contains values outside the 1 to 5 range."
    )

    for column in DATE_COLUMNS:
        assert pd.api.types.is_datetime64_any_dtype(
            df[column]
        ), f"{column} was not converted to datetime."

    assert not df.duplicated().any(), "Exact duplicate review rows still exist."

    logging.info("Validation checks passed for clean.reviews.")

    # ----- STEP 9: Write to clean schema -----
    with engine.begin() as connection:
        connection.execute(text("CREATE SCHEMA IF NOT EXISTS clean"))

    df.to_sql(
        name="reviews",
        con=engine,
        schema="clean",
        if_exists="replace",
        index=False,
        chunksize=1000,
    )

    logging.info(
        "Finished reviews cleaning. Original rows: %s. Clean rows: %s. "
        "Duplicates removed: %s.",
        original_count,
        len(df),
        duplicates_removed,
    )

    print("Reviews cleaning completed successfully.")
    print(f"Original rows: {original_count}")
    print(f"Clean rows: {len(df)}")
    print(f"Duplicates removed: {duplicates_removed}")
    print("Written to PostgreSQL table: clean.reviews")


def main():
    """
    Run the reviews cleaning pipeline.
    """
    engine = get_database_engine()
    clean_reviews(engine)


if __name__ == "__main__":
    main()