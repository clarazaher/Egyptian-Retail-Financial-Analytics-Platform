"""
Clean the staging.products table and write the result to clean.products.

This script:
- Reads product data from the staging schema
- Reads category translation data from the staging schema
- Standardizes product category text
- Adds English product category names
- Handles missing category values
- Handles missing and invalid product dimensions
- Fills missing descriptive metadata values
- Removes duplicate product_id rows defensively
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


PHYSICAL_DIMENSION_COLUMNS = [
    "product_weight_g",
    "product_length_cm",
    "product_height_cm",
    "product_width_cm",
]

DESCRIPTIVE_METADATA_COLUMNS = [
    "product_name_lenght",
    "product_description_lenght",
    "product_photos_qty",
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


def standardize_category_column(series):
    """
    Standardize product category text by trimming spaces and converting to lowercase.
    """
    return series.astype("string").str.strip().str.lower()


def impute_by_category_then_global(df, column_name):
    """
    Impute missing values using the median within each product category.

    If a product category has no valid median, fall back to the global median.
    """
    category_median = df.groupby("product_category_name")[column_name].transform(
        lambda values: values.fillna(values.median())
    )

    global_median = df[column_name].median()

    return category_median.fillna(global_median)


def clean_products(engine):
    """
    Clean staging.products and write the cleaned result to clean.products.
    """
    logging.info("Starting products cleaning process.")

    # ----- STEP 1: Load raw products and category translations -----
    products = pd.read_sql("SELECT * FROM staging.products", engine)
    categories = pd.read_sql("SELECT * FROM staging.categories", engine)

    original_count = len(products)

    logging.info("Loaded %s rows from staging.products.", original_count)
    print(f"Loaded {original_count} rows from staging.products.")

    # ----- STEP 2: Defensive duplicate removal -----
    before_dedup = len(products)
    products = products.drop_duplicates(subset=["product_id"])
    duplicates_removed = before_dedup - len(products)

    if duplicates_removed > 0:
        logging.warning("Removed %s duplicate product_id rows.", duplicates_removed)

    # ----- STEP 3: Standardize category text before joining -----
    products["product_category_name"] = standardize_category_column(
        products["product_category_name"]
    )

    categories["product_category_name"] = standardize_category_column(
        categories["product_category_name"]
    )

    # ----- STEP 4: Preserve missing category information -----
    products["is_product_category_missing"] = products["product_category_name"].isna()

    products["product_category_name"] = products["product_category_name"].fillna(
        "unknown"
    )

    # ----- STEP 5: Join English category names -----
    products = products.merge(
        categories,
        on="product_category_name",
        how="left",
    )

    products["product_category_name_english"] = products[
        "product_category_name_english"
    ].fillna("unknown")

    # ----- STEP 6: Convert numeric columns safely -----
    for column in PHYSICAL_DIMENSION_COLUMNS + DESCRIPTIVE_METADATA_COLUMNS:
        products[column] = pd.to_numeric(products[column], errors="coerce")

    # ----- STEP 7: Flag missing physical dimensions before imputation -----
    products["had_missing_physical_dimension"] = products[
        PHYSICAL_DIMENSION_COLUMNS
    ].isna().any(axis=1)

    # ----- STEP 8: Convert invalid physical dimensions to missing -----
    for column in PHYSICAL_DIMENSION_COLUMNS:
        invalid_count = (products[column] <= 0).sum()

        if invalid_count > 0:
            logging.warning(
                "Converted %s invalid values in %s to missing before imputation.",
                invalid_count,
                column,
            )

        products.loc[products[column] <= 0, column] = pd.NA

    # ----- STEP 9: Impute physical dimensions by category median -----
    for column in PHYSICAL_DIMENSION_COLUMNS:
        products[column] = impute_by_category_then_global(products, column)

    # ----- STEP 10: Fill descriptive metadata missing values -----
    for column in DESCRIPTIVE_METADATA_COLUMNS:
        products[column] = products[column].fillna(0)

    # ----- STEP 11: Engineer simple metadata flag -----
    products["has_product_metadata"] = (
        (products["product_name_lenght"] > 0)
        | (products["product_description_lenght"] > 0)
        | (products["product_photos_qty"] > 0)
    )

    # ----- STEP 12: Validate cleaned result -----
    assert products["product_id"].notna().all(), "product_id has null values."
    assert products["product_id"].is_unique, "product_id is not unique after cleaning."

    assert products["product_category_name"].notna().all(), (
        "product_category_name still has null values."
    )

    assert products["product_category_name_english"].notna().all(), (
        "product_category_name_english still has null values."
    )

    for column in PHYSICAL_DIMENSION_COLUMNS:
        assert products[column].notna().all(), f"{column} still has missing values."
        assert (products[column] > 0).all(), f"{column} contains zero or negative values."

    for column in DESCRIPTIVE_METADATA_COLUMNS:
        assert products[column].notna().all(), f"{column} still has missing values."
        assert (products[column] >= 0).all(), f"{column} contains negative values."

    logging.info("Validation checks passed for clean.products.")

    # ----- STEP 13: Write to clean schema -----
    with engine.begin() as connection:
        connection.execute(text("CREATE SCHEMA IF NOT EXISTS clean"))

    products.to_sql(
        name="products",
        con=engine,
        schema="clean",
        if_exists="replace",
        index=False,
        chunksize=1000,
    )

    logging.info(
        "Finished products cleaning. Original rows: %s. Clean rows: %s. "
        "Duplicates removed: %s.",
        original_count,
        len(products),
        duplicates_removed,
    )

    print("Products cleaning completed successfully.")
    print(f"Original rows: {original_count}")
    print(f"Clean rows: {len(products)}")
    print(f"Duplicates removed: {duplicates_removed}")
    print("Written to PostgreSQL table: clean.products")


def main():
    """
    Run the products cleaning pipeline.
    """
    engine = get_database_engine()
    clean_products(engine)


if __name__ == "__main__":
    main()