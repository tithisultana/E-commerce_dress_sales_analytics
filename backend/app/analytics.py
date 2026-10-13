# ---------------------------------------------------------------------------
# analytics.py
#
# All analytics functions support a two-tier data strategy:
#
#   Tier 1 (preferred) — 10M processed summary files
#     dashboard_summary_10M.json  →  overview, monthly, categories, payments,
#                                    locations, products, methodology
#     customer_agg_10M.csv        →  customer analysis, segmentation
#     prediction_sample_10M.csv   →  segmentation scatter chart sample
#
#   Tier 2 (fallback) — original 10k CSV
#     dress_sales.csv  →  all functions, same logic as before
#
# The raw 10M transaction CSV lives on Google Drive and is NEVER loaded here.
# Processed files are read in milliseconds; the backend stays fast and
# memory-safe regardless of how large the underlying dataset is.
# ---------------------------------------------------------------------------

from __future__ import annotations

import pandas as pd
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

from .data import (
    DATA_PATH,
    REQUIRED_COLUMNS,
    USE_10M_DATA,
    get_customer_agg_10m,
    get_dataset,
    get_prediction_sample_10m,
    get_summary_10m,
)


def records(frame: pd.DataFrame) -> list[dict]:
    """Convert a DataFrame to a JSON-serialisable list of dicts."""
    normalized = frame.astype(object).where(pd.notna(frame), None)
    return normalized.to_dict(orient="records")


# ===========================================================================
# Overview / Dashboard KPIs
# ===========================================================================

def overview_data() -> dict:
    """Return KPIs, date range, monthly revenue, and category revenue.

    10M path: reads pre-computed values directly from dashboard_summary_10M.json.
    Fallback:  computes from the 10k CSV via groupby aggregations.
    """
    if USE_10M_DATA:
        # -----------------------------------------------------------------
        # Tier 1 — serve pre-computed 10M summary (milliseconds)
        # Raw 10M CSV is on Google Drive, not loaded here.
        # -----------------------------------------------------------------
        s = get_summary_10m()
        return {
            "kpis":             s["kpis"],
            "date_range":       s["date_range"],
            "monthly_revenue":  s["monthly"],
            "category_revenue": s["categories"],
        }

    # -----------------------------------------------------------------
    # Tier 2 — compute from original 10k CSV
    # -----------------------------------------------------------------
    frame = get_dataset()
    orders = int(frame["Order_ID"].nunique())
    categories = category_sales_data()
    return {
        "kpis": {
            "revenue": round(float(frame["Net_Sales"].sum()), 2),
            "orders": orders,
            "customers": int(frame["Customer_ID"].nunique()),
            "units": int(frame["Quantity"].sum()),
            "average_order_value": (
                round(float(frame["Net_Sales"].sum() / orders), 2) if orders else 0
            ),
            "average_rating": round(float(frame["Rating"].mean()), 2),
        },
        "date_range": {
            "start": frame["Date"].min().strftime("%Y-%m-%d"),
            "end":   frame["Date"].max().strftime("%Y-%m-%d"),
        },
        "monthly_revenue":  monthly_sales_data()["monthly"],
        "category_revenue": categories,
    }


# ===========================================================================
# Monthly Sales Trend
# ===========================================================================

def monthly_sales_data() -> dict:
    """Return monthly revenue/orders/units and weekday breakdown.

    10M path: reads pre-computed monthly and weekday arrays from JSON summary.
    Fallback:  groups the 10k CSV by Period and day name.
    """
    if USE_10M_DATA:
        s = get_summary_10m()
        return {
            "monthly": s["monthly"],
            "weekday": s["weekday"],
        }

    frame = get_dataset()
    monthly = frame.groupby("Period", as_index=False).agg(
        revenue=("Net_Sales", "sum"),
        orders=("Order_ID", "nunique"),
        units=("Quantity", "sum"),
    )
    weekdays = (
        frame.assign(weekday=frame["Date"].dt.day_name())
        .groupby("weekday", as_index=False)
        .agg(revenue=("Net_Sales", "sum"), orders=("Order_ID", "nunique"))
    )
    weekday_order = [
        "Monday", "Tuesday", "Wednesday", "Thursday",
        "Friday", "Saturday", "Sunday",
    ]
    weekdays["weekday"] = pd.Categorical(
        weekdays["weekday"], weekday_order, ordered=True
    )
    return {
        "monthly": records(monthly),
        "weekday": records(weekdays.sort_values("weekday")),
    }


# ===========================================================================
# Category Analysis
# ===========================================================================

def category_sales_data() -> list[dict]:
    """Revenue, units, and orders by category.

    10M path: returns pre-computed category list from JSON summary.
    Fallback:  groups the 10k CSV by Category.

    Note: the 10M summary includes average_rating per category;
    the fallback also includes it for API shape consistency.
    """
    if USE_10M_DATA:
        return get_summary_10m()["categories"]

    frame = get_dataset()
    categories = frame.groupby("Category", as_index=False).agg(
        revenue=("Net_Sales", "sum"),
        units=("Quantity", "sum"),
        orders=("Order_ID", "nunique"),
        average_rating=("Rating", "mean"),
    )
    categories["average_rating"] = categories["average_rating"].round(2)
    return records(categories.sort_values("revenue", ascending=False))


# ===========================================================================
# Top Products
# ===========================================================================

def top_products_data(limit: int = 10) -> dict:
    """Top products by units sold, plus material and size breakdowns.

    10M path: reads products_top30, materials, sizes from JSON summary.
    Fallback:  groups the 10k CSV.
    """
    if USE_10M_DATA:
        s = get_summary_10m()
        return {
            "products":  s["products_top30"][:limit],
            "materials": s["materials"],
            "sizes":     s["sizes"],
        }

    frame = get_dataset()
    products = (
        frame.groupby(
            ["Product_ID", "Product_Name", "Category", "Brand"], as_index=False
        )
        .agg(
            revenue=("Net_Sales", "sum"),
            units=("Quantity", "sum"),
            orders=("Order_ID", "nunique"),
            rating=("Rating", "mean"),
            price=("Price", "mean"),
            discount=("Discount", "mean"),
        )
        .sort_values("units", ascending=False)
    )
    materials = (
        frame.groupby("Material", as_index=False)
        .agg(units=("Quantity", "sum"))
        .sort_values("units", ascending=False)
    )
    sizes = frame.groupby("Size", as_index=False).agg(units=("Quantity", "sum"))
    return {
        "products":  records(products.head(limit)),
        "materials": records(materials),
        "sizes":     records(sizes),
    }


# ===========================================================================
# Payment Method Distribution
# ===========================================================================

def payment_distribution_data() -> list[dict]:
    """Revenue and order share by payment method.

    10M path: returns pre-computed payments list from JSON summary.
    Fallback:  groups the 10k CSV by Payment_Method.
    """
    if USE_10M_DATA:
        return get_summary_10m()["payments"]

    frame = get_dataset()
    payment = (
        frame.groupby("Payment_Method", as_index=False)
        .agg(revenue=("Net_Sales", "sum"), orders=("Order_ID", "nunique"))
        .sort_values("revenue", ascending=False)
    )
    total = payment["revenue"].sum()
    payment["share"] = (
        (payment["revenue"] / total * 100).round(2) if total else 0
    )
    return records(payment)


# ===========================================================================
# Location Sales
# ===========================================================================

def location_sales_data() -> list[dict]:
    """Revenue, orders, units, and customer count by location.

    10M path: returns pre-computed locations list from JSON summary.
    Fallback:  groups the 10k CSV by Location.
    """
    if USE_10M_DATA:
        return get_summary_10m()["locations"]

    frame = get_dataset()
    locations = (
        frame.groupby("Location", as_index=False)
        .agg(
            customers=("Customer_ID", "nunique"),
            revenue=("Net_Sales", "sum"),
            orders=("Order_ID", "nunique"),
            units=("Quantity", "sum"),
        )
    )
    return records(locations.sort_values("revenue", ascending=False))


# ===========================================================================
# Customer Analysis
# ===========================================================================

def customer_analysis_data() -> dict:
    """Customer spending summary, top customers, age groups, and locations.

    10M path:
        Reads customer_agg_10M.csv (one row per customer, 500k rows).
        Age groups are computed from the agg CSV — fast single-column scan.
        The frontend table is paginated; all 500k rows are returned but the
        API response is ~25 MB maximum (the CSV itself is ~20 MB).
        Top customers: head(12) by spend (already sorted desc in the file).

    Fallback:
        Groups the 10k CSV by Customer_ID.
    """
    if USE_10M_DATA:
        customers = get_customer_agg_10m()
        # customers is already sorted by spend desc (from the ETL script)

        # Age groups from the pre-aggregated customer table
        age_bins = pd.cut(
            customers["age"],
            bins=[0, 20, 30, 40, 50, 100],
            labels=["<20", "20-29", "30-39", "40-49", "50+"],
        )
        age_groups = (
            customers.assign(age_group=age_bins)
            .groupby("age_group", observed=False, as_index=False)
            .agg(orders=("orders", "sum"), revenue=("spend", "sum"))
        )

        s = get_summary_10m()["customer_stats"]
        return {
            "top_customers":             records(customers.head(12)),
            "customers":                 records(customers),
            "locations":                 location_sales_data(),
            "age_groups":                records(age_groups),
            "repeat_customers":          int(s["repeat_customers"]),
            "customer_count":            int(s["customer_count"]),
            "average_customer_value":    float(s["average_customer_value"]),
            "average_orders_per_customer": float(s["average_orders_per_customer"]),
        }

    # Fallback — 10k CSV
    frame = get_dataset()
    customers = (
        frame.groupby("Customer_ID", as_index=False)
        .agg(
            spend=("Net_Sales", "sum"),
            items=("Quantity", "sum"),
            orders=("Order_ID", "nunique"),
            age=("Age", "mean"),
            rating=("Rating", "mean"),
            location=("Location", "first"),
        )
        .sort_values("spend", ascending=False)
    )
    age_bins = pd.cut(
        frame["Age"],
        bins=[0, 20, 30, 40, 50, 100],
        labels=["<20", "20-29", "30-39", "40-49", "50+"],
    )
    age_groups = (
        frame.assign(age_group=age_bins)
        .groupby("age_group", observed=False, as_index=False)
        .agg(orders=("Order_ID", "nunique"), revenue=("Net_Sales", "sum"))
    )
    return {
        "top_customers": records(customers.head(12)),
        "customers":     records(customers),
        "locations":     location_sales_data(),
        "age_groups":    records(age_groups),
        "repeat_customers":          int((customers["orders"] > 1).sum()),
        "customer_count":            int(len(customers)),
        "average_customer_value":    round(float(customers["spend"].mean()), 2),
        "average_orders_per_customer": round(float(customers["orders"].mean()), 2),
    }


# ===========================================================================
# Customer Segmentation (K-Means)
# ===========================================================================

def customer_segments_data() -> dict:
    """K-Means customer segmentation — summary + scatter chart sample.

    10M path:
        Cluster labels are pre-computed in the ETL script and stored in
        customer_agg_10M.csv. The cluster summary is re-derived from the
        agg CSV (fast — 500k rows, not 10M transactions).
        The scatter chart sample comes from prediction_sample_10M.csv
        (≤ 4,500 rows — the browser never receives the full 500k table).
        Features: Total_Spending (spend), Total_Items (items),
                  Total_Orders (orders) — consistent with Notebook 3.

    Fallback:
        Runs KMeans(k=3, seed=42) on the 10k CSV customer table.
        Features: spend (gross), items, orders — consistent with Notebook 3.
    """
    if USE_10M_DATA:
        customers = get_customer_agg_10m()
        scatter   = get_prediction_sample_10m()

        # Cluster summary from the pre-segmented customer table
        # (cluster column was assigned by MiniBatchKMeans in the ETL script)
        summary = (
            customers.groupby("cluster", as_index=False)
            .agg(
                customers=("Customer_ID", "count"),
                spend=("spend", "mean"),
                items=("items", "mean"),
                orders=("orders", "mean"),
            )
            .sort_values("spend")
        )
        summary[["spend", "items", "orders"]] = (
            summary[["spend", "items", "orders"]].round(2)
        )
        # Align column name used by frontend ("segment" == "cluster")
        summary["segment"] = summary["cluster"]

        return {
            "summary":   records(summary),
            "customers": records(scatter),  # ≤ 4,500 points for scatter chart
        }

    # Fallback — KMeans on 10k CSV
    frame  = get_dataset()
    # Notebook 3: Sales = Price × Quantity (gross, no discount deducted)
    cs = frame.assign(Sales=frame["Price"] * frame["Quantity"])
    customers = (
        cs.groupby("Customer_ID", as_index=False)
        .agg(
            spend=("Sales", "sum"),
            items=("Quantity", "sum"),
            orders=("Order_ID", "nunique"),
        )
    )
    feature_cols = ["spend", "items", "orders"]
    scaled = StandardScaler().fit_transform(customers[feature_cols])
    customers["cluster"] = KMeans(
        n_clusters=3, random_state=42, n_init=10
    ).fit_predict(scaled)
    summary = (
        customers.groupby("cluster", as_index=False)
        .agg(
            customers=("Customer_ID", "count"),
            spend=("spend", "mean"),
            items=("items", "mean"),
            orders=("orders", "mean"),
        )
        .sort_values("cluster")
    )
    customers["segment"] = customers["cluster"]
    summary["segment"]   = summary["cluster"]
    summary[["spend", "items", "orders"]] = (
        summary[["spend", "items", "orders"]].round(2)
    )
    sample = customers.sample(min(500, len(customers)), random_state=42)
    return {"summary": records(summary), "customers": records(sample)}


# ===========================================================================
# Methodology / About
# ===========================================================================

def methodology_data() -> dict:
    """Dataset and methodology metadata for the Methodology page.

    10M path: returns values from the methodology and meta sections of the
              JSON summary (rows=10M, date range, revenue definition, etc.).
    Fallback:  computes row count, dates, and duplicate count from the CSV.
    """
    if USE_10M_DATA:
        s  = get_summary_10m()
        m  = s["methodology"]
        return {
            "rows":                   int(m["rows"]),
            "columns":                int(m.get("columns", len(REQUIRED_COLUMNS))),
            "date_start":             m["date_start"],
            "date_end":               m["date_end"],
            "missing_values":         int(m.get("missing_values", 0)),
            "duplicate_rows_removed": int(m.get("duplicate_rows_removed", 0)),
            "revenue_definition":     m["revenue_definition"],
            "segmentation":           m["segmentation"],
            "prediction":             m["prediction"],
        }

    frame  = get_dataset()
    source = pd.read_csv(DATA_PATH)
    return {
        "rows":                   int(len(frame)),
        "columns":                int(len(REQUIRED_COLUMNS)),
        "date_start":             frame["Date"].min().strftime("%Y-%m-%d"),
        "date_end":               frame["Date"].max().strftime("%Y-%m-%d"),
        "missing_values":         int(frame[list(REQUIRED_COLUMNS)].isna().sum().sum()),
        "duplicate_rows_removed": int(source.duplicated().sum()),
        "revenue_definition":     "Net Sales = Price x Quantity x (1 - Discount / 100)",
        "segmentation": (
            "Customer spending in EDA uses Net Sales after discount, "
            "while K-Means segmentation uses gross sales (Price x Quantity), "
            "following the respective notebooks."
        ),
        "prediction": (
            "Quantity prediction; 80/20 random split (seed 42), "
            "median/mode imputation, one-hot encoded categories, "
            "Linear Regression baseline and Random Forest (200 trees)."
        ),
    }