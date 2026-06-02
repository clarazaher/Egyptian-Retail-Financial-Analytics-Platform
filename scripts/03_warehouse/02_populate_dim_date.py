"""
Populate the warehouse.dim_date table.

This script:
- Generates one row per calendar day from 2016-01-01 to 2026-12-31
- Creates useful date attributes for reporting and Power BI
- Truncates the existing warehouse.dim_date table
- Inserts the generated date dimension rows

The database password is read from the DB_PASSWORD environment variable.
"""

import os
from pathlib import Path
import logging

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


def build_dim_date(start_date="2016-01-01", end_date="2026-12-31"):
    """
    Build a date dimension DataFrame.

    Args:
        start_date: First date to include.
        end_date: Last date to include.

    Returns:
        pandas DataFrame containing one row per date.
    """
    dates = pd.date_range(start=start_date, end=end_date, freq="D")

    dim_date = pd.DataFrame(
        {
            "date_key": dates.strftime("%Y%m%d").astype(int),
            "full_date": dates.date,
            "year": dates.year,
            "quarter": dates.quarter,
            "quarter_name": "Q"
            + dates.quarter.astype(str)
            + " "
            + dates.year.astype(str),
            "month_num": dates.month,
            "month_name": dates.strftime("%B"),
            "week_of_year": dates.isocalendar().week.astype(int),
            "day_of_week": dates.isocalendar().day.astype(int),
            "day_name": dates.strftime("%A"),
            "is_weekend": dates.dayofweek >= 5,
            "is_holiday": False,
        }
    )

    return dim_date


def populate_dim_date(engine):
    """
    Populate warehouse.dim_date.
    """
    logging.info("Starting dim_date population.")

    dim_date = build_dim_date()

    with engine.begin() as connection:
        connection.execute(text("CREATE SCHEMA IF NOT EXISTS warehouse"))
        connection.execute(text("TRUNCATE TABLE warehouse.dim_date CASCADE"))

    dim_date.to_sql(
        name="dim_date",
        con=engine,
        schema="warehouse",
        if_exists="append",
        index=False,
        chunksize=1000,
    )

    logging.info("Loaded %s rows into warehouse.dim_date.", len(dim_date))

    print("dim_date population completed successfully.")
    print(f"Rows loaded: {len(dim_date)}")
    print("Written to PostgreSQL table: warehouse.dim_date")


def main():
    """
    Run the dim_date population pipeline.
    """
    engine = get_database_engine()
    populate_dim_date(engine)


if __name__ == "__main__":
    main()