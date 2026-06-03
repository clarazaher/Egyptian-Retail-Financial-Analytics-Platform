# Dashboard Design

This document describes the interactive BI dashboard for the Egyptian Retail & Financial Analytics Platform.

The original project plan included Power BI. Because the development environment is macOS-based and Power BI Desktop is not natively available on macOS, the dashboard layer was implemented using Streamlit instead.

Streamlit was selected because it supports Python-native dashboard development, direct PostgreSQL querying through SQLAlchemy, interactive filters, KPI cards, charts, and portfolio-ready web applications.

---

## Dashboard Tool

- Tool: Streamlit
- Language: Python
- Data Source: PostgreSQL
- Database: `egyptian_retail_db`
- Main Schema: `warehouse`
- Supporting Schema: `clean`

---

## Dashboard Sections

The dashboard is organized into the following sections:

1. Executive Overview
2. Revenue Trends
3. Product Category Performance
4. Geography Analysis
5. Delivery Performance
6. Payment Insights
7. Forecasting Summary

---

## Data Model Used

The dashboard uses the warehouse star schema:

- `warehouse.fact_order_items`
- `warehouse.dim_date`
- `warehouse.dim_customer`
- `warehouse.dim_product`
- `warehouse.dim_seller`

Payment analysis uses:

- `clean.payments`

Payment data is analyzed from the cleaned payments table because payments are stored at order-payment level, while the main fact table is stored at order-item level. This avoids duplicating payment values across multiple order items.

---

## Core Metrics

The dashboard includes the following business metrics:

- Total Revenue
- Total Orders
- Average Order Value
- Total Items Sold
- Average Days to Deliver
- On-Time Delivery Rate
- Revenue by Month
- Revenue by Product Category
- Revenue by Customer State
- Revenue by Seller State
- Payment Value by Payment Type

---

## Design Goal

The dashboard is designed for business users who need to monitor revenue, customer behavior, product performance, delivery reliability, and payment preferences in one interactive application.