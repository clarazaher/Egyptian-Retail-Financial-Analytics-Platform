"""
Load raw Olist CSV files into PostgreSQL staging tables.

This script:
1. Connects to the local PostgreSQL database.
2. Creates the staging schema if it does not exist.
3. Reads each CSV file from data/raw/.
4. Adds a metadata column called _loaded_at.
5. Loads each file into PostgreSQL staging tables.
"""

import logging
import os
from datetime import datetime
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text


# ------------------------------------------------------------
# Logging setup
# ------------------------------------------------------------
Path("logs").mkdir(exist_ok=True)

logging.basicConfig(
    filename="logs/ingestion.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)


# ------------------------------------------------------------
# Database connection settings
# ------------------------------------------------------------
DB_HOST = "localhost"
DB_PORT = "5432"
DB_NAME = "egyptian_retail_db"
DB_USER = "postgres"
DB_PASSWORD = os.environ.get("DB_PASSWORD")

if not DB_PASSWORD:
    raise ValueError(
        "DB_PASSWORD environment variable is not set. "
        "Run this in the VS Code terminal first: "
        "export DB_PASSWORD='your_postgres_password'"
    )

connection_string = (
    f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)

engine = create_engine(connection_string)


# ------------------------------------------------------------
# Data loading function
# ------------------------------------------------------------
def load_csv_to_staging(filepath: str, table_name: str) -> None:
    """
    Load one CSV file into one PostgreSQL staging table.

    Args:
        filepath: Path to the CSV file.
        table_name: Name of the target table inside the staging schema.
    """
    try:
        if not Path(filepath).exists():
            raise FileNotFoundError(f"File not found: {filepath}")

        df = pd.read_csv(filepath)
        row_count = len(df)

        df["_loaded_at"] = datetime.now()

        df.to_sql(
            name=table_name,
            con=engine,
            schema="staging",
            if_exists="replace",
            index=False,
            chunksize=1000,
        )

        logging.info("Loaded %s rows into staging.%s", row_count, table_name)
        print(f"SUCCESS: {row_count} rows loaded into staging.{table_name}")

    except Exception as error:
        logging.error("FAILED loading %s: %s", table_name, str(error))
        print(f"ERROR: Failed to load {table_name}. See logs/ingestion.log.")
        raise


# ------------------------------------------------------------
# Main execution
# ------------------------------------------------------------
def main() -> None:
    """
    Create the staging schema and load all raw CSV files.
    """
    with engine.connect() as conn:
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS staging"))
        conn.commit()

    files_to_load = {
        "customers": "data/raw/olist_customers_dataset.csv",
        "geolocation": "data/raw/olist_geolocation_dataset.csv",
        "order_items": "data/raw/olist_order_items_dataset.csv",
        "payments": "data/raw/olist_order_payments_dataset.csv",
        "reviews": "data/raw/olist_order_reviews_dataset.csv",
        "orders": "data/raw/olist_orders_dataset.csv",
        "products": "data/raw/olist_products_dataset.csv",
        "sellers": "data/raw/olist_sellers_dataset.csv",
        "categories": "data/raw/product_category_name_translation.csv",
    }

    print("Starting data ingestion...")

    for table_name, filepath in files_to_load.items():
        load_csv_to_staging(filepath, table_name)

    print("All files loaded successfully.")


if __name__ == "__main__":
    main()