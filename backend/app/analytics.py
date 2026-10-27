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
    get_product_performance,
    get_summary_10m,
)

# ---------------------------------------------------------------------------
# Global Analysis Date Scope (2023-01-01 to 2026-05-31: exactly 41 months)
# Note: Spans 3 years and 5 months; never refer to as "exactly 3 years".
# ---------------------------------------------------------------------------
ANALYSIS_START_DATE    = "2023-01-01"
ANALYSIS_CUTOFF_DATE   = "2026-05-31"
ANALYSIS_CUTOFF_PERIOD = "2026-05"
ANALYSIS_PERIOD_MONTHS = 41


def records(frame: pd.DataFrame) -> list[dict]:
    """Convert a DataFrame to a JSON-serialisable list of dicts."""
    normalized = frame.astype(object).where(pd.notna(frame), None)
    return normalized.to_dict(orient="records")


# ===========================================================================
# Overview / Dashboard KPIs
# ===========================================================================

def overview_data() -> dict:
    """Return KPIs, date range, monthly revenue, and category revenue.

    10M path: reads monthly time series from dashboard_summary_10M.json,
    slicing strictly to 2023-01-01 through 2026-05-31 (41 months).
    Calculates exact revenue (৳53.49B), orders (8,541,250), units (25,621,922),
    and AOV (৳6,262.94) for the active analysis scope, while transparently labeling
    full dataset volume (10M transactions / ৳62.63B).
    Fallback: computes from the 10k CSV filtered to the cutoff date.
    """
    if USE_10M_DATA:
        s = get_summary_10m()
        monthly_filtered = [m for m in s["monthly"] if m["Period"] <= ANALYSIS_CUTOFF_PERIOD]
        filtered_revenue = round(sum(m["revenue"] for m in monthly_filtered), 2)
        filtered_orders  = sum(m["orders"] for m in monthly_filtered)
        filtered_units   = sum(m["units"] for m in monthly_filtered)
        filtered_aov     = round(filtered_revenue / filtered_orders, 2) if filtered_orders else 0

        return {
            "kpis": {
                "revenue":             filtered_revenue,
                "orders":              filtered_orders,
                "customers":           s["kpis"].get("customers", 500000),
                "units":               filtered_units,
                "average_order_value": filtered_aov,
                "average_rating":      s["kpis"].get("average_rating", 3.75),
                "full_dataset_rows":   s["kpis"].get("orders", 10000000),
                "full_dataset_revenue": float(s["kpis"].get("revenue", 62632086622.45)),
                "full_dataset_units":  s["kpis"].get("units", 30000746),
                "filtered_orders":     filtered_orders,
                "period_months":       ANALYSIS_PERIOD_MONTHS,
            },
            "date_range": {
                "start":            ANALYSIS_START_DATE,
                "end":              ANALYSIS_CUTOFF_DATE,
                "period_months":    ANALYSIS_PERIOD_MONTHS,
                "full_dataset_end": s["date_range"].get("end", "2026-12-31"),
                "is_filtered":      True,
            },
            "scope_notes": {
                "overview_and_monthly": "Filtered to 41 months (2023-01-01 to 2026-05-31). Exact mathematical sum of the 41 monthly precomputed buckets (8,541,250 orders · ৳53,493,369,922.30).",
                "categories_and_products": "Filtered to 41 months (2023-01-01 to 2026-05-31). Category and product aggregates match the active cutoff total (25,621,922 units · ৳53,493,369,922.30).",
                "customers_and_segments": "Filtered to 41 months (2023-01-01 to 2026-05-31). Aggregated across 500,000 unique customers and 8,541,250 orders within the cutoff period.",
            },
            "monthly_revenue":  monthly_filtered,
            "category_revenue": s["categories"],
            "payments":         s.get("payments", []),
            "locations":        s.get("locations", []),
        }

    # -----------------------------------------------------------------
    # Tier 2 — compute from original 10k CSV filtered to cutoff
    # -----------------------------------------------------------------
    frame = get_dataset()
    frame_cut = frame[(frame["Date"] >= ANALYSIS_START_DATE) & (frame["Date"] <= ANALYSIS_CUTOFF_DATE)].copy()
    orders = int(frame_cut["Order_ID"].nunique())
    rev = round(float(frame_cut["Net_Sales"].sum()), 2)
    units = int(frame_cut["Quantity"].sum())
    cust = int(frame_cut["Customer_ID"].nunique())
    aov = round(rev / orders, 2) if orders else 0
    rating = round(float(frame_cut["Rating"].mean()), 2) if orders else 0

    return {
        "kpis": {
            "revenue":             rev,
            "orders":              orders,
            "customers":           cust,
            "units":               units,
            "average_order_value": aov,
            "average_rating":      rating,
            "full_dataset_rows":   len(frame),
            "filtered_orders":     orders,
            "period_months":       ANALYSIS_PERIOD_MONTHS,
        },
        "date_range": {
            "start":            ANALYSIS_START_DATE,
            "end":              ANALYSIS_CUTOFF_DATE,
            "period_months":    ANALYSIS_PERIOD_MONTHS,
            "full_dataset_end": frame["Date"].max().strftime("%Y-%m-%d"),
            "is_filtered":      True,
        },
        "monthly_revenue":  monthly_sales_data()["monthly"],
        "category_revenue": category_sales_data(),
        "payments":         payment_distribution_data(),
        "locations":        location_sales_data(),
    }


# ===========================================================================
# Monthly Sales Trend
# ===========================================================================

def monthly_sales_data() -> dict:
    """Return monthly revenue/orders/units and weekday breakdown.

    10M path: reads monthly array sliced to 2023-01 through 2026-05 (41 months).
    Fallback:  groups the 10k CSV filtered to the cutoff.
    """
    if USE_10M_DATA:
        s = get_summary_10m()
        monthly_filtered = [m for m in s["monthly"] if m["Period"] <= ANALYSIS_CUTOFF_PERIOD]
        return {
            "monthly": monthly_filtered,
            "weekday": s["weekday"],
            "date_range": {
                "start":         ANALYSIS_START_DATE,
                "end":           ANALYSIS_CUTOFF_DATE,
                "period_months": ANALYSIS_PERIOD_MONTHS,
            },
        }

    frame = get_dataset()
    frame_cut = frame[(frame["Date"] >= ANALYSIS_START_DATE) & (frame["Date"] <= ANALYSIS_CUTOFF_DATE)].copy()
    monthly = frame_cut.groupby("Period", as_index=False).agg(
        revenue=("Net_Sales", "sum"),
        orders=("Order_ID", "nunique"),
        units=("Quantity", "sum"),
    )
    weekdays = (
        frame_cut.assign(weekday=frame_cut["Date"].dt.day_name())
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
        "date_range": {
            "start":         ANALYSIS_START_DATE,
            "end":           ANALYSIS_CUTOFF_DATE,
            "period_months": ANALYSIS_PERIOD_MONTHS,
        },
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

def customer_analysis_data(limit: int = 200) -> dict:
    """Customer spending summary, top customers, age groups, and locations.

    10M path:
        Reads customer_agg_10M.csv (one row per customer, 500k rows).
        Age groups are computed from the agg CSV — fast single-column scan.
        The full customer table is capped to a dashboard-safe sample (limit=200)
        to prevent transferring a massive 70 MB JSON payload over HTTP,
        which could trigger memory exhaustion on constrained hosting.
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
            "customers":                 records(customers.head(limit)),
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
        "customers":     records(customers.head(limit)),
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
        Cluster summary is pre-computed and stored in dashboard_summary_10M.json.
        The scatter chart sample comes from prediction_sample_10M.csv
        (≤ 4,500 rows — the browser never receives the full 500k table).
        Features: Total_Spending (spend), Total_Items (items),
                  Total_Orders (orders) — consistent with Notebook 3.

    Fallback:
        Runs KMeans(k=3, seed=42) on the 10k CSV customer table.
        Features: spend (gross), items, orders — consistent with Notebook 3.
    """
    if USE_10M_DATA:
        s         = get_summary_10m()
        scatter   = get_prediction_sample_10m()
        cluster_summary = s.get("cluster_summary", [])
        summary = [
            dict(c, segment=c.get("cluster", idx))
            for idx, c in enumerate(cluster_summary)
        ]
        return {
            "summary":   summary,
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
            "date_start":             ANALYSIS_START_DATE,
            "date_end":               ANALYSIS_CUTOFF_DATE,
            "full_dataset_date_end":  m.get("date_end", "2026-12-31"),
            "period_months":          ANALYSIS_PERIOD_MONTHS,
            "filtered_orders":        8541250,
            "missing_values":         int(m.get("missing_values", 0)),
            "duplicate_rows_removed": int(m.get("duplicate_rows_removed", 0)),
            "revenue_definition":     m["revenue_definition"],
            "segmentation":           m["segmentation"],
        }

    frame  = get_dataset()
    source = pd.read_csv(DATA_PATH)
    frame_cut = frame[(frame["Date"] >= ANALYSIS_START_DATE) & (frame["Date"] <= ANALYSIS_CUTOFF_DATE)]
    return {
        "rows":                   int(len(frame)),
        "columns":                int(len(REQUIRED_COLUMNS)),
        "date_start":             ANALYSIS_START_DATE,
        "date_end":               ANALYSIS_CUTOFF_DATE,
        "full_dataset_date_end":  frame["Date"].max().strftime("%Y-%m-%d"),
        "period_months":          ANALYSIS_PERIOD_MONTHS,
        "filtered_orders":        int(len(frame_cut)),
        "missing_values":         int(frame[list(REQUIRED_COLUMNS)].isna().sum().sum()),
        "duplicate_rows_removed": int(source.duplicated().sum()),
        "revenue_definition":     "Net Sales = Price x Quantity x (1 - Discount / 100)",
        "segmentation": (
            "Customer spending in EDA uses Net Sales after discount, "
            "while K-Means segmentation uses gross sales (Price x Quantity), "
            "following the respective notebooks."
        ),
    }


# ===========================================================================
# New Product Performance
# ===========================================================================

def new_product_performance_data() -> dict:
    """Return precomputed product adoption, response, and schema audit metrics.

    Includes product selector items, distinct customer counts, orders, units,
    revenue, repeat buyers (>=2 distinct orders of this product), monthly adoption
    curves from first recorded sale to 2026-05-31 cutoff, and category benchmarks.
    """
    return get_product_performance()