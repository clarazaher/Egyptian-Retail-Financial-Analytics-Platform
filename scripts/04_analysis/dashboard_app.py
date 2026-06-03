"""
Interactive Streamlit BI dashboard for the Egyptian Retail & Financial Analytics Platform.

This dashboard:
- Connects to PostgreSQL using SQLAlchemy
- Reads warehouse fact and dimension tables
- Provides interactive filters
- Displays KPI cards, charts, and tables
- Includes revenue, product, geography, delivery, payment, and forecast sections

The database password is read from the DB_PASSWORD environment variable.
"""

import os
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st
from sqlalchemy import create_engine
from sqlalchemy.engine import URL


DB_HOST = "localhost"
DB_PORT = 5432
DB_NAME = "egyptian_retail_db"
DB_USER = "postgres"
DB_PASSWORD = os.environ.get("DB_PASSWORD")


st.set_page_config(
    page_title="Egyptian Retail Analytics Dashboard",
    page_icon="📊",
    layout="wide",
)


@st.cache_resource
def get_database_engine():
    """
    Create and cache the SQLAlchemy database engine.
    """
    if not DB_PASSWORD:
        st.error(
            "DB_PASSWORD environment variable is not set. "
            "Stop the app, run `export DB_PASSWORD='your_password'`, then start it again."
        )
        st.stop()

    connection_url = URL.create(
        drivername="postgresql+psycopg2",
        username=DB_USER,
        password=DB_PASSWORD,
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
    )

    return create_engine(connection_url)


@st.cache_data(show_spinner="Loading warehouse data...")
def load_fact_data():
    """
    Load the main warehouse dataset used by the dashboard.
    """
    engine = get_database_engine()

    query = """
    SELECT
        f.order_id,
        f.order_item_id,
        d.full_date,
        d.year,
        d.month_num,
        d.month_name,
        p.product_category_name_english,
        c.customer_state,
        c.customer_city_state,
        s.seller_state,
        s.seller_city_state,
        f.price,
        f.freight_value,
        f.total_item_value,
        f.days_to_deliver,
        f.delivered_on_time,
        f.delivery_date_key,
        f.has_timeline_issue
    FROM warehouse.fact_order_items f
    JOIN warehouse.dim_date d
        ON f.purchase_date_key = d.date_key
    JOIN warehouse.dim_product p
        ON f.product_key = p.product_key
    JOIN warehouse.dim_customer c
        ON f.customer_key = c.customer_key
    JOIN warehouse.dim_seller s
        ON f.seller_key = s.seller_key;
    """

    df = pd.read_sql(query, engine)
    df["full_date"] = pd.to_datetime(df["full_date"])

    return df


@st.cache_data(show_spinner="Loading payment data...")
def load_payment_data():
    """
    Load cleaned payment data for payment analysis.
    """
    engine = get_database_engine()

    query = """
    SELECT
        order_id,
        payment_type,
        payment_sequential,
        payment_installments,
        payment_value,
        is_installment_payment,
        payment_value_per_installment
    FROM clean.payments;
    """

    return pd.read_sql(query, engine)


def format_number(value):
    """
    Format large numbers with commas and two decimals.
    """
    return f"{value:,.2f}"


def format_integer(value):
    """
    Format integers with commas.
    """
    return f"{int(value):,}"


def apply_sidebar_filters(df):
    """
    Apply interactive sidebar filters to the main dashboard dataset.
    """
    st.sidebar.header("Dashboard Filters")

    min_date = df["full_date"].min().date()
    max_date = df["full_date"].max().date()

    date_range = st.sidebar.date_input(
        "Purchase date range",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date,
    )

    if len(date_range) == 2:
        start_date, end_date = date_range
        df = df[
            (df["full_date"].dt.date >= start_date)
            & (df["full_date"].dt.date <= end_date)
        ]

    years = sorted(df["year"].dropna().unique())
    selected_years = st.sidebar.multiselect(
        "Year",
        options=years,
        default=years,
    )

    if selected_years:
        df = df[df["year"].isin(selected_years)]

    categories = sorted(df["product_category_name_english"].dropna().unique())
    selected_categories = st.sidebar.multiselect(
        "Product category",
        options=categories,
        default=categories,
    )

    if selected_categories:
        df = df[df["product_category_name_english"].isin(selected_categories)]

    customer_states = sorted(df["customer_state"].dropna().unique())
    selected_customer_states = st.sidebar.multiselect(
        "Customer state",
        options=customer_states,
        default=customer_states,
    )

    if selected_customer_states:
        df = df[df["customer_state"].isin(selected_customer_states)]

    seller_states = sorted(df["seller_state"].dropna().unique())
    selected_seller_states = st.sidebar.multiselect(
        "Seller state",
        options=seller_states,
        default=seller_states,
    )

    if selected_seller_states:
        df = df[df["seller_state"].isin(selected_seller_states)]

    return df


def show_kpis(df):
    """
    Display executive KPI cards.
    """
    total_revenue = df["total_item_value"].sum()
    total_orders = df["order_id"].nunique()
    total_items = len(df)
    avg_order_value = total_revenue / total_orders if total_orders else 0

    delivered_df = df[df["delivery_date_key"].notna()]
    avg_days_to_deliver = delivered_df["days_to_deliver"].mean()

    on_time_rate = (
        delivered_df["delivered_on_time"].mean() * 100
        if len(delivered_df) > 0
        else 0
    )

    col1, col2, col3, col4, col5 = st.columns(5)

    col1.metric("Total Revenue", format_number(total_revenue))
    col2.metric("Total Orders", format_integer(total_orders))
    col3.metric("Items Sold", format_integer(total_items))
    col4.metric("Avg Order Value", format_number(avg_order_value))
    col5.metric("On-Time Delivery", f"{on_time_rate:.2f}%")

    col6, col7, col8 = st.columns(3)
    col6.metric("Avg Days to Deliver", f"{avg_days_to_deliver:.2f}")
    col7.metric("Delivered Items", format_integer(len(delivered_df)))
    col8.metric("Undelivered Items", format_integer(df["delivery_date_key"].isna().sum()))


def show_overview(df):
    """
    Executive overview tab.
    """
    st.subheader("Executive Overview")
    show_kpis(df)

    monthly = (
        df.groupby(["year", "month_num", "month_name"], as_index=False)
        .agg(
            monthly_revenue=("total_item_value", "sum"),
            order_count=("order_id", "nunique"),
        )
        .sort_values(["year", "month_num"])
    )

    monthly["month_label"] = (
        monthly["month_name"].str[:3] + " " + monthly["year"].astype(str)
    )

    col1, col2 = st.columns(2)

    with col1:
        fig = px.line(
            monthly,
            x="month_label",
            y="monthly_revenue",
            markers=True,
            title="Monthly Revenue Trend",
        )
        fig.update_layout(xaxis_title="Month", yaxis_title="Revenue")
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        top_categories = (
            df.groupby("product_category_name_english", as_index=False)
            .agg(total_revenue=("total_item_value", "sum"))
            .sort_values("total_revenue", ascending=False)
            .head(10)
        )

        fig = px.bar(
            top_categories,
            x="total_revenue",
            y="product_category_name_english",
            orientation="h",
            title="Top 10 Product Categories by Revenue",
        )
        fig.update_layout(
            xaxis_title="Revenue",
            yaxis_title="Product Category",
            yaxis={"categoryorder": "total ascending"},
        )
        st.plotly_chart(fig, use_container_width=True)


def show_revenue(df):
    """
    Revenue analysis tab.
    """
    st.subheader("Revenue Trends")

    monthly = (
        df.groupby(["year", "month_num", "month_name"], as_index=False)
        .agg(
            monthly_revenue=("total_item_value", "sum"),
            order_count=("order_id", "nunique"),
            avg_item_value=("total_item_value", "mean"),
        )
        .sort_values(["year", "month_num"])
    )

    monthly["month_label"] = (
        monthly["month_name"].str[:3] + " " + monthly["year"].astype(str)
    )

    fig_revenue = px.line(
        monthly,
        x="month_label",
        y="monthly_revenue",
        markers=True,
        title="Monthly Revenue",
    )
    st.plotly_chart(fig_revenue, use_container_width=True)

    fig_orders = px.bar(
        monthly,
        x="month_label",
        y="order_count",
        title="Monthly Order Count",
    )
    st.plotly_chart(fig_orders, use_container_width=True)

    st.dataframe(monthly, use_container_width=True)


def show_products(df):
    """
    Product category performance tab.
    """
    st.subheader("Product Category Performance")

    category_summary = (
        df.groupby("product_category_name_english", as_index=False)
        .agg(
            total_revenue=("total_item_value", "sum"),
            order_count=("order_id", "nunique"),
            item_count=("order_item_id", "count"),
            avg_item_value=("total_item_value", "mean"),
        )
        .sort_values("total_revenue", ascending=False)
    )

    top_15 = category_summary.head(15)

    fig = px.bar(
        top_15,
        x="total_revenue",
        y="product_category_name_english",
        orientation="h",
        title="Top 15 Product Categories by Revenue",
    )
    fig.update_layout(
        xaxis_title="Revenue",
        yaxis_title="Product Category",
        yaxis={"categoryorder": "total ascending"},
    )
    st.plotly_chart(fig, use_container_width=True)

    st.dataframe(category_summary, use_container_width=True)


def show_geography(df):
    """
    Customer and seller geography tab.
    """
    st.subheader("Geography Analysis")

    col1, col2 = st.columns(2)

    customer_state_summary = (
        df.groupby("customer_state", as_index=False)
        .agg(
            total_revenue=("total_item_value", "sum"),
            order_count=("order_id", "nunique"),
        )
        .sort_values("total_revenue", ascending=False)
    )

    seller_state_summary = (
        df.groupby("seller_state", as_index=False)
        .agg(
            total_revenue=("total_item_value", "sum"),
            order_count=("order_id", "nunique"),
        )
        .sort_values("total_revenue", ascending=False)
    )

    with col1:
        fig = px.bar(
            customer_state_summary.head(15),
            x="customer_state",
            y="total_revenue",
            title="Revenue by Customer State",
        )
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        fig = px.bar(
            seller_state_summary.head(15),
            x="seller_state",
            y="total_revenue",
            title="Revenue by Seller State",
        )
        st.plotly_chart(fig, use_container_width=True)

    st.write("Customer State Summary")
    st.dataframe(customer_state_summary, use_container_width=True)

    st.write("Seller State Summary")
    st.dataframe(seller_state_summary, use_container_width=True)


def show_delivery(df):
    """
    Delivery performance tab.
    """
    st.subheader("Delivery Performance")

    delivered_df = df[df["delivery_date_key"].notna()].copy()

    show_kpis(df)

    category_delivery = (
        delivered_df.groupby("product_category_name_english", as_index=False)
        .agg(
            item_count=("order_item_id", "count"),
            avg_days_to_deliver=("days_to_deliver", "mean"),
            on_time_delivery_rate=("delivered_on_time", "mean"),
        )
    )

    category_delivery["on_time_delivery_rate"] = (
        category_delivery["on_time_delivery_rate"] * 100
    )

    category_delivery = category_delivery[
        category_delivery["item_count"] >= 100
    ].sort_values("avg_days_to_deliver", ascending=False)

    fig = px.bar(
        category_delivery.head(15),
        x="avg_days_to_deliver",
        y="product_category_name_english",
        orientation="h",
        title="Top 15 Slowest Product Categories by Delivery Time",
    )
    fig.update_layout(
        xaxis_title="Average Days to Deliver",
        yaxis_title="Product Category",
        yaxis={"categoryorder": "total ascending"},
    )
    st.plotly_chart(fig, use_container_width=True)

    monthly_delivery = (
        delivered_df.groupby(["year", "month_num", "month_name"], as_index=False)
        .agg(
            delivered_items=("order_item_id", "count"),
            on_time_delivery_rate=("delivered_on_time", "mean"),
        )
        .sort_values(["year", "month_num"])
    )

    monthly_delivery["on_time_delivery_rate"] = (
        monthly_delivery["on_time_delivery_rate"] * 100
    )

    monthly_delivery["month_label"] = (
        monthly_delivery["month_name"].str[:3]
        + " "
        + monthly_delivery["year"].astype(str)
    )

    fig = px.line(
        monthly_delivery,
        x="month_label",
        y="on_time_delivery_rate",
        markers=True,
        title="Monthly On-Time Delivery Rate",
    )
    fig.update_layout(xaxis_title="Month", yaxis_title="On-Time Delivery Rate (%)")
    st.plotly_chart(fig, use_container_width=True)

    st.dataframe(category_delivery, use_container_width=True)


def show_payments(payment_df):
    """
    Payment insights tab.
    """
    st.subheader("Payment Insights")

    payment_summary = (
        payment_df.groupby("payment_type", as_index=False)
        .agg(
            payment_records=("order_id", "count"),
            order_count=("order_id", "nunique"),
            total_payment_value=("payment_value", "sum"),
            avg_payment_value=("payment_value", "mean"),
            avg_installments=("payment_installments", "mean"),
            installment_payment_rate=("is_installment_payment", "mean"),
        )
        .sort_values("total_payment_value", ascending=False)
    )

    payment_summary["installment_payment_rate"] = (
        payment_summary["installment_payment_rate"] * 100
    )

    col1, col2 = st.columns(2)

    with col1:
        fig = px.bar(
            payment_summary,
            x="payment_type",
            y="total_payment_value",
            title="Total Payment Value by Payment Method",
        )
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        fig = px.bar(
            payment_summary,
            x="payment_type",
            y="installment_payment_rate",
            title="Installment Payment Rate by Payment Method",
        )
        st.plotly_chart(fig, use_container_width=True)

    st.dataframe(payment_summary, use_container_width=True)


def show_forecast_summary():
    """
    Forecasting summary tab.
    """
    st.subheader("Forecasting Summary")

    st.write(
        """
        The revenue forecasting analysis was completed in the Jupyter notebook using Prophet.
        The model captured the general upward revenue trend, but the forecast error was high,
        meaning it should be used as a directional planning tool rather than a precise daily forecast.
        """
    )

    col1, col2 = st.columns(2)
    col1.metric("Forecast MAE", "11,286.73")
    col2.metric("Forecast MAPE", "42.89%")

    forecast_chart_path = Path("reports/charts/revenue_forecast.png")

    if forecast_chart_path.exists():
        st.image(str(forecast_chart_path), caption="Revenue Forecast — Next 90 Days")
    else:
        st.warning(
            "Forecast chart was not found at reports/charts/revenue_forecast.png. "
            "Run the notebook first to generate it."
        )


def main():
    """
    Run the Streamlit dashboard.
    """
    st.title("Egyptian Retail & Financial Analytics Dashboard")
    st.write(
        """
        Interactive BI dashboard built with Streamlit using PostgreSQL warehouse tables.
        Use the sidebar filters to explore revenue, products, geography, delivery, and payment insights.
        """
    )

    fact_df = load_fact_data()
    payment_df = load_payment_data()

    filtered_df = apply_sidebar_filters(fact_df)

    if filtered_df.empty:
        st.warning("No data matches the selected filters. Please adjust the sidebar filters.")
        st.stop()

    tabs = st.tabs(
        [
            "Executive Overview",
            "Revenue Trends",
            "Products",
            "Geography",
            "Delivery",
            "Payments",
            "Forecast",
        ]
    )

    with tabs[0]:
        show_overview(filtered_df)

    with tabs[1]:
        show_revenue(filtered_df)

    with tabs[2]:
        show_products(filtered_df)

    with tabs[3]:
        show_geography(filtered_df)

    with tabs[4]:
        show_delivery(filtered_df)

    with tabs[5]:
        show_payments(payment_df)

    with tabs[6]:
        show_forecast_summary()


if __name__ == "__main__":
    main()