# Project Summary

The Egyptian Retail & Financial Analytics Platform is an end-to-end analytics project that simulates a professional retail data pipeline.

The project begins with raw CSV files and loads them into PostgreSQL staging tables using Python. Automated data profiling is then used to identify missing values, data type issues, duplicates, outliers, and useful categorical fields. Cleaning decisions are documented in a data quality log and implemented through reusable Python scripts.

After cleaning, the data is loaded into a warehouse star schema with dimension tables for date, customer, product, and seller information, and a central fact table for order-item level analysis. Query performance is tested using `EXPLAIN ANALYZE`, and indexes are added to support analytical queries.

The analysis phase includes monthly revenue trends, RFM customer segmentation, product category performance, delivery performance, payment method analysis, A/B test simulation, and Prophet-based revenue forecasting.

The final dashboard is implemented using Streamlit instead of Power BI because the development environment is macOS-based. The dashboard connects directly to PostgreSQL and provides interactive business intelligence views for revenue, products, geography, delivery, payments, and forecasting.

This project demonstrates practical skills in Python, PostgreSQL, ETL development, data cleaning, dimensional modelling, analytics, forecasting, dashboarding, and GitHub-based project documentation.