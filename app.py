%%writefile app.py
import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt


st.set_page_config(
    page_title="Supply Chain Dashboard",
    layout="wide",
)


dark_css = """
<style>
body {
    background-color: #0E1117;
    color: #FFFFFF;
}
.sidebar .sidebar-content {
    background-color: #161A23 !important;
}
h1, h2, h3, h4, h5, h6, p, label {
    color: #FFFFFF !important;
}
.stButton>button {
    background-color: #4A90E2;
    color: white;
    border-radius: 8px;
    padding: 6px 16px;
}
</style>
"""
st.markdown(dark_css, unsafe_allow_html=True)


@st.cache_data
def load_data():

    df = pd.read_csv("SCMS_Delivery_History_Dataset.csv")

    date_cols = [
        "PQ First Sent to Client Date",
        "PO Sent to Vendor Date",
        "Scheduled Delivery Date",
        "Delivered to Client Date",
        "Delivery Recorded Date",
    ]
    for col in date_cols:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")

    df = df.dropna(subset=["Scheduled Delivery Date", "Delivered to Client Date"]).copy()

    if "PO Sent to Vendor Date" in df.columns:
        df["lead_time_days"] = (
            df["Delivered to Client Date"] - df["PO Sent to Vendor Date"]
        ).dt.days
    else:
        df["lead_time_days"] = np.nan

    df["delay_days"] = (
        df["Delivered to Client Date"] - df["Scheduled Delivery Date"]
    ).dt.days

    df["lead_time_days"] = pd.to_numeric(df["lead_time_days"], errors="coerce")
    df["delay_days"] = pd.to_numeric(df["delay_days"], errors="coerce")

    df.loc[df["lead_time_days"] < 0, "lead_time_days"] = np.nan
    df.loc[df["lead_time_days"] > 365, "lead_time_days"] = np.nan

    df.loc[df["delay_days"] > 365, "delay_days"] = np.nan
    df.loc[df["delay_days"] < -90, "delay_days"] = np.nan

   
    numeric_cols = [
        "Freight Cost (USD)",
        "Line Item Insurance (USD)",
        "Weight (Kilograms)",
        "Line Item Quantity",
        "Line Item Value",
        "Pack Price",
        "Unit Price",
    ]

    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
            df[col] = df[col].fillna(df[col].median())

    if "Weight (Kilograms)" in df.columns:
        df = df[df["Weight (Kilograms)"] > 0].copy()
        weight_cap = df["Weight (Kilograms)"].quantile(0.95)
        df.loc[df["Weight (Kilograms)"] > weight_cap, "Weight (Kilograms)"] = weight_cap

    # is_late + year_month
    df["is_late"] = (df["delay_days"] > 0).astype(int)
    df["year_month"] = df["Delivered to Client Date"].dt.to_period("M").astype(str)

    return df


df = load_data()


def shorten_labels(labels, max_len=20):
    out = []
    for l in labels:
        l = str(l)
        if len(l) > max_len:
            out.append(l[:max_len] + "...")
        else:
            out.append(l)
    return out

st.title("Supply Chain Performance Dashboard")

total_shipments = len(df)
late_shipments = int(df["is_late"].sum())
late_ratio = round(df["is_late"].mean() * 100, 2)
avg_lead = round(df["lead_time_days"].mean(), 2)
avg_delay = round(df["delay_days"].mean(), 2)

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Total Shipments", f"{total_shipments}")
c2.metric("Late Shipments", f"{late_shipments}")
c3.metric("Late %", f"{late_ratio}%")
c4.metric("Avg Lead Time", f"{avg_lead} days")
c5.metric("Avg Delay", f"{avg_delay} days")

st.markdown("---")


st.sidebar.header("Filters")

country_filter = st.sidebar.multiselect(
    "Country",
    options=sorted(df["Country"].dropna().unique()),
    default=None
)

mode_filter = st.sidebar.multiselect(
    "Shipment Mode",
    options=sorted(df["Shipment Mode"].dropna().unique()),
    default=None
)

df_filtered = df.copy()
if country_filter:
    df_filtered = df_filtered[df_filtered["Country"].isin(country_filter)]
if mode_filter:
    df_filtered = df_filtered[df_filtered["Shipment Mode"].isin(mode_filter)]

st.sidebar.write(f"Filtered Shipments: {len(df_filtered)}")

tab1, tab2, tab3, tab4 = st.tabs(["Countries", "Shipment Modes", "Products", "Trends"])

with tab1:
    st.subheader("Country-Level Performance")

    country_stats = (
        df_filtered.groupby("Country")
        .agg(
            total_shipments=("is_late", "count"),
            late_shipments=("is_late", "sum"),
            avg_lead=("lead_time_days", "mean"),
            avg_delay=("delay_days", "mean"),
            total_quantity=("Line Item Quantity", "sum"),
            total_value=("Line Item Value", "sum"),
        )
        .reset_index()
    )

    if not country_stats.empty:
        country_stats["late_ratio"] = (
            country_stats["late_shipments"] / country_stats["total_shipments"] * 100
        ).round(2)

        st.dataframe(
            country_stats.sort_values("total_shipments", ascending=False),
            use_container_width=True,
        )

        # Top 10 countries by quantity
        top_countries = (
            country_stats.sort_values("total_quantity", ascending=False)
            .head(10)
            .set_index("Country")["total_quantity"]
        )

        labels = shorten_labels(top_countries.index, max_len=15)

        fig, ax = plt.subplots(figsize=(10, 5))
        ax.bar(labels, top_countries.values)
        ax.set_title("Top 10 Countries by Quantity")
        ax.set_xlabel("Country")
        ax.set_ylabel("Total Quantity")
        plt.xticks(rotation=45, ha="right")
        st.pyplot(fig)
    else:
        st.write("No data after applying filters.")

with tab2:
    st.subheader("Shipment Mode Performance")

    shipment_stats = (
        df_filtered.groupby("Shipment Mode")
        .agg(
            total_shipments=("is_late", "count"),
            late_shipments=("is_late", "sum"),
            avg_lead=("lead_time_days", "mean"),
            avg_delay=("delay_days", "mean"),
        )
        .reset_index()
    )

    if not shipment_stats.empty:
        shipment_stats["late_ratio"] = (
            shipment_stats["late_shipments"] / shipment_stats["total_shipments"] * 100
        ).round(2)

        st.dataframe(shipment_stats, use_container_width=True)

        fig, ax = plt.subplots(figsize=(8, 5))
        ax.bar(shipment_stats["Shipment Mode"], shipment_stats["late_ratio"])
        ax.set_title("Late Ratio by Shipment Mode")
        ax.set_xlabel("Shipment Mode")
        ax.set_ylabel("Late Ratio (%)")
        plt.xticks(rotation=30, ha="right")
        st.pyplot(fig)
    else:
        st.write("No data after applying filters.")

with tab3:
    st.subheader("Top Products by Quantity")

    product_stats = (
        df_filtered.groupby("Item Description")["Line Item Quantity"]
        .sum()
        .sort_values(ascending=False)
        .head(15)
    )

    if not product_stats.empty:
        labels = shorten_labels(product_stats.index, max_len=30)
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.barh(labels, product_stats.values)
        ax.set_xlabel("Total Quantity")
        ax.set_ylabel("Product")
        ax.invert_yaxis()
        st.pyplot(fig)
    else:
        st.write("No data after applying filters.")

with tab4:
    st.subheader("Shipment Trends (Yearly and Monthly)")

    trend_df = df_filtered.copy()
    trend_df["year"] = trend_df["Delivered to Client Date"].dt.year
    trend_df["month"] = trend_df["Delivered to Client Date"].dt.month

    
    yearly_stats = (
        trend_df.groupby("year")
        .agg(
            total_shipments=("is_late", "count"),
            total_quantity=("Line Item Quantity", "sum"),
            avg_lead=("lead_time_days", "mean"),
        )
        .reset_index()
    )

    if not yearly_stats.empty:
        st.write("Yearly Total Quantity")

        import plotly.express as px  

        fig_year = px.line(
            yearly_stats,
            x="year",
            y="total_quantity",
            markers=True,
            title="Total Quantity per Year",
        )
        fig_year.update_layout(
            xaxis_title="Year",
            yaxis_title="Total Quantity",
            template="plotly_dark",
            height=400,
        )
        st.plotly_chart(fig_year, use_container_width=True)
    else:
        st.write("No data after applying filters.")
        st.stop()

    st.markdown("---")

   

    st.write("Monthly Breakdown with Filters")

    years_available = sorted(trend_df["year"].dropna().unique())
    selected_year = st.selectbox("Select Year", options=years_available)

    month_labels = {
        1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr",
        5: "May", 6: "Jun", 7: "Jul", 8: "Aug",
        9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec",
    }

    month_options = list(month_labels.keys())
    selected_months = st.multiselect(
        "Filter Months (optional)",
        options=month_options,
        format_func=lambda m: month_labels[m],
    )

    month_df = trend_df[trend_df["year"] == selected_year].copy()

    if selected_months:
        month_df = month_df[month_df["month"].isin(selected_months)]

    monthly_stats = (
        month_df.groupby("month")
        .agg(
            total_shipments=("is_late", "count"),
            total_quantity=("Line Item Quantity", "sum"),
            avg_lead=("lead_time_days", "mean"),
        )
        .reset_index()
        .sort_values("month")
    )

    if not monthly_stats.empty:
        monthly_stats["month_label"] = monthly_stats["month"].map(month_labels)

        fig_month = px.line(
            monthly_stats,
            x="month_label",
            y="total_quantity",
            markers=True,
            title=f"Total Quantity per Month in {int(selected_year)}",
        )
        fig_month.update_layout(
            xaxis_title="Month",
            yaxis_title="Total Quantity",
            template="plotly_dark",
            height=400,
        )
        st.plotly_chart(fig_month, use_container_width=True)
    else:
        st.write("No monthly data for this selection.")

