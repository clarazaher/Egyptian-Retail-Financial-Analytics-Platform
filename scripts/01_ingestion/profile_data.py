"""
Data profiling script for the Egyptian Retail & Financial Analytics Platform.

This script reads all raw staging tables from PostgreSQL, generates automated
HTML profiling reports using ydata-profiling, and saves them locally under
reports/profiling/.

The generated HTML reports are intentionally not committed to GitHub because
they are large and machine-generated.
"""

import os
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine
from ydata_profiling import ProfileReport


DB_HOST = "localhost"
DB_PORT = "5432"
DB_NAME = "egyptian_retail_db"
DB_USER = "postgres"
DB_PASSWORD = os.environ.get("DB_PASSWORD")

REPORT_DIR = Path("reports/profiling")

TABLES_TO_PROFILE = [
    "customers",
    "geolocation",
    "order_items",
    "payments",
    "reviews",
    "orders",
    "products",
    "sellers",
    "categories",
]


def get_database_engine():
    """
    Create and return a SQLAlchemy database engine.

    The database password is read from the DB_PASSWORD environment variable
    so that the password is not hardcoded in the script or committed to GitHub.
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


def profile_table(table_name, engine):
    """
    Read one staging table from PostgreSQL and generate an HTML profile report.

    Args:
        table_name: Name of the table inside the staging schema.
        engine: SQLAlchemy engine connected to the PostgreSQL database.
    """
    print(f"Profiling staging.{table_name}...")

    query = f"SELECT * FROM staging.{table_name}"
    df = pd.read_sql(query, engine)

    profile = ProfileReport(
        df,
        title=f"Data Profile: staging.{table_name}",
        explorative=True,
        minimal=False,
    )

    output_path = REPORT_DIR / f"{table_name}_profile.html"
    profile.to_file(output_path)

    print(f"Saved report: {output_path}")


def main():
    """
    Generate profiling reports for all staging tables.
    """
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    engine = get_database_engine()

    for table_name in TABLES_TO_PROFILE:
        profile_table(table_name, engine)

    print("All profiling reports generated successfully.")


if __name__ == "__main__":
    main()