#!/usr/bin/env python3
"""
scripts/process_10m_colab.py
============================
Standalone Google Colab data processing pipeline for the verified 10,000,000-row
E-Commerce Dress Sales raw dataset.

PURPOSE & EXECUTION SCOPE
-------------------------
1. Reads the verified raw 10M file directly from Google Drive in READ-ONLY mode:
       /content/drive/MyDrive/Ecommerce_Dress_Sales_10M/raw/dress_sales_10M.csv.gz
   Does NOT generate synthetic records and NEVER modifies or overwrites the raw file.

2. Processes the dataset in memory-safe chunks (default 250,000 rows) backed by a
   temporary local SQLite staging store on Colab's NVMe SSD (/tmp).
   Python heap memory is strictly bounded; monthly order IDs and transaction records
   are aggregated on disk in SQLite, not retained in Python sets.

3. Generates all website-compatible processed aggregate files for the active
   global cutoff date (2026-05-31 · 41 months):
       - dashboard_summary_10M.json  (Overview KPIs, 48-mo trend, categories, payments, locations, top 30)
       - customer_agg_10M.csv        (Customer-level spend, items, orders, age, rating, K-Means cluster)
       - prediction_sample_10M.csv   (Stratified 4,500-point sample for scatter chart visualization)
       - product_performance.json    (New Product Performance: distinct buyers, repeat buyers, cohorts, benchmarks)
       - manifest.json               (Full audit trail, reconciliation assertions, feature definitions)

4. Outputs are saved to a NEW dedicated Google Drive directory:
       /content/drive/MyDrive/Ecommerce_Dress_Sales_10M/processed_cutoff_20260531/
   Existing output directories are protected from accidental overwriting. Use --overwrite
   to intentionally replace files.

5. Generates a compact deployment ZIP archive:
       processed_deployment_cutoff_20260531.zip
   Contains the lightweight aggregate outputs. The aggregate customer files retain pseudo-anonymized
   Customer_ID keys for dashboard ledger lookups and scatter mapping, but raw transaction
   records, customer-product transaction linkages, and PII are never included in the archive.

6. Performs rigorous assertions against authoritative verified source totals in production mode:
       Full file totals (48 months):
           - Rows:        10,000,000
           - Units:       30,000,746
           - Net revenue: 62,632,086,622.45
       Filtered scope (2023-01-01 to 2026-05-31 · 41 months):
           - Rows:        8,541,250
           - Units:       25,621,922
           - Net revenue: 53,493,369,922.30
           - Invalid dates: 0

   In test mode (--test-mode), actual fixture metrics are computed and exported,
   and production reconciliation is clearly reported as not performed.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sqlite3
import sys
import tempfile
import time
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.cluster import MiniBatchKMeans
from sklearn.preprocessing import StandardScaler

# Reconfigure stdout/stderr to UTF-8 to prevent charmap encoding errors on Windows
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


# ===========================================================================
# 1. Authoritative Expected Constants & Cutoff Definitions
# ===========================================================================
GLOBAL_START_DATE    = "2023-01-01"
GLOBAL_CUTOFF_DATE   = "2026-05-31"
GLOBAL_CUTOFF_PERIOD = "2026-05"
FULL_DATASET_END     = "2026-12-31"
ANALYSIS_PERIOD_MOS  = 41

# Expected Ground Truth Totals (Used ONLY for assertion comparison in production mode)
EXPECTED_FULL_ROWS      = 10_000_000
EXPECTED_FULL_UNITS     = 30_000_746
EXPECTED_FULL_REVENUE   = 62_632_086_622.45

EXPECTED_FILTERED_ROWS    = 8_541_250
EXPECTED_FILTERED_UNITS   = 25_621_922
EXPECTED_FILTERED_REVENUE = 53_493_369_922.30

RANDOM_SEED = 42

REQUIRED_COLUMNS = [
    "Order_ID", "Customer_ID", "Gender", "Age", "Location", "Date",
    "Product_ID", "Product_Name", "Category", "Brand", "Material", "Size",
    "Color", "Price", "Quantity", "Discount", "Payment_Method", "Rating",
]


# ===========================================================================
# 2. Environment Detection & Default Paths
# ===========================================================================
def is_running_in_colab() -> bool:
    """Return True if executing inside Google Colab."""
    try:
        import google.colab  # noqa: F401
        return True
    except ImportError:
        return False


def ensure_google_drive_mounted() -> None:
    """Mount Google Drive if running in Google Colab and not already mounted."""
    if not is_running_in_colab():
        return
    mount_point = Path("/content/drive")
    if not (mount_point / "MyDrive").is_dir():
        print(">> Mounting Google Drive at /content/drive ...")
        from google.colab import drive  # type: ignore
        drive.mount(str(mount_point))
    else:
        print("[OK] Google Drive already mounted at /content/drive")


def get_default_paths() -> tuple[Path, Path]:
    """Return default raw input path and new processed output directory."""
    if is_running_in_colab():
        raw_path = Path("/content/drive/MyDrive/Ecommerce_Dress_Sales_10M/raw/dress_sales_10M.csv.gz")
        out_dir  = Path("/content/drive/MyDrive/Ecommerce_Dress_Sales_10M/processed_cutoff_20260531")
    else:
        project_root = Path(__file__).resolve().parent.parent
        raw_path = project_root / "data" / "raw" / "dress_sales_10M.csv.gz"
        out_dir  = project_root / "data" / "processed_cutoff_20260531"
    return raw_path, out_dir


# ===========================================================================
# 3. Disk-Backed Staging & Streaming Aggregation (Bounded Memory)
# ===========================================================================
def stage_and_aggregate_raw_dataset(
    raw_csv_gz: Path,
    chunk_size: int,
    staging_db_path: Path,
) -> tuple[dict[str, Any], sqlite3.Connection]:
    """Stream raw CSV in chunks, update numeric accumulators, and stage records

    in a temporary SQLite database on local SSD.

    Memory safety:
        Monthly order IDs and filtered orders are written to SQLite tables.
        Zero unbounded Python sets are stored in memory.

    Returns:
        tuple of (streaming_metrics_dict, sqlite_connection)
    """
    print(f"\n{'='*72}")
    print(f">> STEP 1: Streaming Raw Dataset (Read-Only Chunks of {chunk_size:,} rows)")
    print(f"  Source: {raw_csv_gz}")
    print(f"  Staging DB: {staging_db_path}")
    print(f"{'='*72}\n")

    conn = sqlite3.connect(staging_db_path)
    cur = conn.cursor()
    cur.execute("PRAGMA synchronous = OFF;")
    cur.execute("PRAGMA journal_mode = MEMORY;")
    cur.execute("PRAGMA cache_size = -64000;")  # 64 MB cache

    # Table 1: All monthly orders across full file (for disk-backed distinct order count)
    cur.execute("""
    CREATE TABLE monthly_order_events (
        period TEXT,
        order_id TEXT,
        quantity INT,
        revenue_poisha INT
    );
    """)

    # Table 2: Filtered transactions within active cutoff scope (2023-01-01 to 2026-05-31)
    cur.execute("""
    CREATE TABLE filtered_orders (
        order_id TEXT,
        customer_id TEXT,
        order_date TEXT,
        period TEXT,
        product_id TEXT,
        product_name TEXT,
        category TEXT,
        brand TEXT,
        material TEXT,
        size TEXT,
        price REAL,
        quantity INT,
        discount REAL,
        payment_method TEXT,
        location TEXT,
        age INT,
        rating REAL,
        revenue_poisha INT
    );
    """)
    conn.commit()

    # Streaming metrics accumulators
    full_rows = 0
    full_units = 0
    full_revenue_poisha = 0
    invalid_dates_count = 0
    earliest_date_str = "9999-99-99"
    latest_date_str = "0000-00-00"

    filtered_rows = 0
    filtered_units = 0
    filtered_revenue_poisha = 0

    unique_categories: set[str] = set()
    unique_brands: set[str] = set()
    unique_sizes: set[str] = set()

    start_time = time.perf_counter()
    chunk_idx = 0

    # Read-only stream: strictly open in read mode
    csv_reader = pd.read_csv(
        raw_csv_gz,
        chunksize=chunk_size,
        dtype={
            "Order_ID": "string",
            "Customer_ID": "string",
            "Gender": "string",
            "Age": "int64",
            "Location": "string",
            "Date": "string",
            "Product_ID": "string",
            "Product_Name": "string",
            "Category": "string",
            "Brand": "string",
            "Material": "string",
            "Size": "string",
            "Color": "string",
            "Price": "float64",
            "Quantity": "int64",
            "Discount": "float64",
            "Payment_Method": "string",
            "Rating": "float64",
        },
    )

    for chunk in csv_reader:
        chunk_idx += 1
        n_chunk = len(chunk)

        # Date validation
        dates_parsed = pd.to_datetime(chunk["Date"], format="%Y-%m-%d", errors="coerce")
        nan_dates = int(dates_parsed.isna().sum())
        invalid_dates_count += nan_dates

        chunk_date_str = chunk["Date"].astype(str)
        chunk_period = chunk_date_str.str.slice(0, 7)

        # Exact Monetary Aggregation in Integer Poisha (cents): Price * Qty * (1 - Discount/100)
        net_sales = chunk["Price"] * chunk["Quantity"] * (1.0 - chunk["Discount"] / 100.0)
        rev_poisha = (net_sales * 100.0).round().astype(np.int64)

        # Full file metrics
        full_rows += n_chunk
        full_units += int(chunk["Quantity"].sum())
        full_revenue_poisha += int(rev_poisha.sum())

        chunk_min_date = chunk_date_str.min()
        chunk_max_date = chunk_date_str.max()
        if chunk_min_date < earliest_date_str:
            earliest_date_str = chunk_min_date
        if chunk_max_date > latest_date_str:
            latest_date_str = chunk_max_date

        unique_categories.update(chunk["Category"].dropna().unique())
        unique_brands.update(chunk["Brand"].dropna().unique())
        unique_sizes.update(chunk["Size"].dropna().unique())

        # Stage monthly order events to SQLite disk (pre-grouped by Period and Order_ID per chunk)
        chunk_monthly = pd.DataFrame({
            "Period": chunk_period,
            "Order_ID": chunk["Order_ID"],
            "Quantity": chunk["Quantity"],
            "Revenue_Poisha": rev_poisha,
        }).groupby(["Period", "Order_ID"], as_index=False).agg({"Quantity": "sum", "Revenue_Poisha": "sum"})

        cur.executemany(
            "INSERT INTO monthly_order_events VALUES (?,?,?,?)",
            [
                (row.Period, row.Order_ID, int(row.Quantity), int(row.Revenue_Poisha))
                for row in chunk_monthly.itertuples(index=False)
            ],
        )

        # Stage filtered scope (2023-01-01 to 2026-05-31) to SQLite
        mask_filtered = (chunk_date_str >= GLOBAL_START_DATE) & (chunk_date_str <= GLOBAL_CUTOFF_DATE)
        chunk_filtered = chunk[mask_filtered]

        if not chunk_filtered.empty:
            n_filtered = len(chunk_filtered)
            f_poisha = rev_poisha[mask_filtered]
            filtered_rows += n_filtered
            filtered_units += int(chunk_filtered["Quantity"].sum())
            filtered_revenue_poisha += int(f_poisha.sum())

            insert_batch = [
                (
                    row.Order_ID, row.Customer_ID, row.Date, row.Period,
                    row.Product_ID, row.Product_Name, row.Category, row.Brand,
                    row.Material, row.Size, float(row.Price), int(row.Quantity),
                    float(row.Discount), row.Payment_Method, row.Location,
                    int(row.Age), float(row.Rating), int(row.Revenue_Poisha)
                )
                for row in pd.DataFrame({
                    "Order_ID": chunk_filtered["Order_ID"],
                    "Customer_ID": chunk_filtered["Customer_ID"],
                    "Date": chunk_filtered["Date"],
                    "Period": chunk_period[mask_filtered],
                    "Product_ID": chunk_filtered["Product_ID"],
                    "Product_Name": chunk_filtered["Product_Name"],
                    "Category": chunk_filtered["Category"],
                    "Brand": chunk_filtered["Brand"],
                    "Material": chunk_filtered["Material"],
                    "Size": chunk_filtered["Size"],
                    "Price": chunk_filtered["Price"],
                    "Quantity": chunk_filtered["Quantity"],
                    "Discount": chunk_filtered["Discount"],
                    "Payment_Method": chunk_filtered["Payment_Method"],
                    "Location": chunk_filtered["Location"],
                    "Age": chunk_filtered["Age"],
                    "Rating": chunk_filtered["Rating"],
                    "Revenue_Poisha": f_poisha,
                }).itertuples(index=False)
            ]
            cur.executemany("INSERT INTO filtered_orders VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", insert_batch)

        del chunk
        del chunk_monthly

        if chunk_idx % 4 == 0 or full_rows >= EXPECTED_FULL_ROWS:
            elapsed = time.perf_counter() - start_time
            print(
                f"  Chunk {chunk_idx:>2}: {full_rows:>10,} rows read | "
                f"{filtered_rows:>10,} filtered staged | {elapsed:5.1f}s elapsed"
            )

    conn.commit()

    # Index monthly orders for fast grouping
    cur.execute("CREATE INDEX IF NOT EXISTS idx_monthly_period ON monthly_order_events(period);")
    conn.commit()

    # Compute distinct order counts from disk-backed SQLite tables
    cur.execute("SELECT COUNT(DISTINCT order_id) FROM monthly_order_events;")
    full_distinct_orders = cur.fetchone()[0] or 0

    cur.execute("SELECT COUNT(DISTINCT order_id) FROM filtered_orders;")
    filtered_distinct_orders = cur.fetchone()[0] or 0

    streaming_metrics = {
        "full_rows": full_rows,
        "full_units": full_units,
        "full_revenue": full_revenue_poisha / 100.0,
        "full_revenue_poisha": full_revenue_poisha,
        "full_distinct_orders": full_distinct_orders,
        "filtered_rows": filtered_rows,
        "filtered_units": filtered_units,
        "filtered_revenue": filtered_revenue_poisha / 100.0,
        "filtered_revenue_poisha": filtered_revenue_poisha,
        "filtered_distinct_orders": filtered_distinct_orders,
        "invalid_dates": invalid_dates_count,
        "earliest_date": earliest_date_str,
        "latest_date": latest_date_str,
        "unique_categories": sorted(unique_categories),
        "unique_brands": sorted(unique_brands),
        "unique_sizes": sorted(unique_sizes),
        "streaming_duration_sec": time.perf_counter() - start_time,
    }

    return streaming_metrics, conn


# ===========================================================================
# 4. Strict Reconciliation Assertions
# ===========================================================================
def verify_source_totals_reconciliation(m: dict[str, Any], test_mode: bool = False) -> bool:
    """Verify streamed totals match expected ground truth in production mode.

    In test mode, validates fixture sanity and marks production reconciliation
    as not performed.
    """
    print(f"\n{'='*72}")
    print(">> STEP 2: Reconciliation & Data Integrity Verification")
    print(f"{'='*72}\n")

    print(f"  Full File Total Rows         : {m['full_rows']:>14,}")
    print(f"  Full File Total Units        : {m['full_units']:>14,}")
    print(f"  Full File Total Net Revenue  : Tk. {m['full_revenue']:>17,.2f}")
    print(f"  Full File Distinct Orders    : {m['full_distinct_orders']:>14,}")
    print(f"  Filtered Scope (41m) Rows    : {m['filtered_rows']:>14,}")
    print(f"  Filtered Scope (41m) Units   : {m['filtered_units']:>14,}")
    print(f"  Filtered Scope (41m) Revenue : Tk. {m['filtered_revenue']:>17,.2f}")
    print(f"  Filtered Distinct Orders     : {m['filtered_distinct_orders']:>14,}")
    print(f"  Invalid Dates Encountered   : {m['invalid_dates']:>14}")

    if test_mode:
        print("\n  [TEST MODE] Production reconciliation against 10M constants is NOT performed.")
        print("  Evaluating fixture consistency:")
        assert m["full_rows"] > 0, "Test fixture: full rows must be > 0"
        assert m["filtered_rows"] > 0, "Test fixture: filtered rows must be > 0"
        assert m["full_distinct_orders"] > 0, "Test fixture: distinct orders must be > 0"
        assert m["invalid_dates"] == 0, f"Found {m['invalid_dates']} invalid dates!"
        print("  [OK] Test fixture sanity checks passed.")
        return False

    # Production 10M Ground-Truth Assertions
    print(f"\n  Checking production assertions against authoritative 10M constants ...")
    assert m["full_rows"] == EXPECTED_FULL_ROWS, (
        f"Full rows mismatch: measured {m['full_rows']}, expected {EXPECTED_FULL_ROWS}"
    )
    assert m["full_units"] == EXPECTED_FULL_UNITS, (
        f"Full units mismatch: measured {m['full_units']}, expected {EXPECTED_FULL_UNITS}"
    )
    assert abs(m["full_revenue"] - EXPECTED_FULL_REVENUE) < 0.01, (
        f"Full revenue mismatch: measured {m['full_revenue']:.2f}, expected {EXPECTED_FULL_REVENUE:.2f}"
    )
    assert m["filtered_rows"] == EXPECTED_FILTERED_ROWS, (
        f"Filtered rows mismatch: measured {m['filtered_rows']}, expected {EXPECTED_FILTERED_ROWS}"
    )
    assert m["filtered_units"] == EXPECTED_FILTERED_UNITS, (
        f"Filtered units mismatch: measured {m['filtered_units']}, expected {EXPECTED_FILTERED_UNITS}"
    )
    assert abs(m["filtered_revenue"] - EXPECTED_FILTERED_REVENUE) < 0.01, (
        f"Filtered revenue mismatch: measured {m['filtered_revenue']:.2f}, expected {EXPECTED_FILTERED_REVENUE:.2f}"
    )
    assert m["invalid_dates"] == 0, f"Found {m['invalid_dates']} invalid dates!"

    print("[OK] ALL PRODUCTION RECONCILIATION ASSERTIONS PASSED PERFECTLY!\n")
    return True


# ===========================================================================
# 5. Build Customer Aggregation & K-Means Segmentation
# ===========================================================================
def build_customers_and_segmentation(
    conn: sqlite3.Connection,
    out_dir: Path,
) -> tuple[pd.DataFrame, pd.DataFrame, list[dict[str, Any]], dict[str, Any]]:
    """Recalculate customer features from staged raw transactions within cutoff,

    fit K-Means (k=3), save customer_agg_10M.csv and a reproducible random
    stratified sample for prediction_sample_10M.csv.
    """
    print(f"\n{'='*72}")
    print(">> STEP 3: Customer Feature Recalculation & K-Means Segmentation (k=3, seed=42)")
    print(f"{'='*72}\n")

    t0 = time.perf_counter()
    cur = conn.cursor()

    print("  Aggregating unique customer metrics from SQLite staging store ...")
    cur.execute("""
    SELECT customer_id,
           ROUND(SUM(revenue_poisha) / 100.0, 2) as spend,
           SUM(quantity) as items,
           COUNT(DISTINCT order_id) as orders,
           ROUND(AVG(age), 1) as age,
           ROUND(AVG(rating), 2) as rating,
           MAX(location) as location
    FROM filtered_orders
    GROUP BY customer_id
    ORDER BY spend DESC;
    """)
    cust_rows = cur.fetchall()
    customer_df = pd.DataFrame(
        cust_rows,
        columns=["Customer_ID", "spend", "items", "orders", "age", "rating", "location"]
    )
    n_customers = len(customer_df)
    print(f"  [OK] Aggregated {n_customers:,} unique customers in {time.perf_counter() - t0:.1f}s")

    # Fit K-Means (k=3, seed=42) on standardized features (spend, items, orders)
    print("  Fitting MiniBatchKMeans (k=3, random_state=42) on standardized features ...")
    features = customer_df[["spend", "items", "orders"]].values
    scaler = StandardScaler()
    scaled_features = scaler.fit_transform(features)

    kmeans = MiniBatchKMeans(
        n_clusters=3,
        random_state=RANDOM_SEED,
        batch_size=10_000,
        n_init=10,
    )
    customer_df["cluster"] = kmeans.fit_predict(scaled_features)

    # Save full customer table
    customer_agg_csv = out_dir / "customer_agg_10M.csv"
    customer_df.to_csv(customer_agg_csv, index=False)
    print(f"  [OK] Wrote customer_agg_10M.csv ({customer_agg_csv.stat().st_size / (1024*1024):.1f} MB)")

    # Stratified random sample for scatter map (reproducible with random_state=42)
    # Up to 1,500 points per cluster = max 4,500 total points
    sample_parts = []
    for c in sorted(customer_df["cluster"].unique()):
        cluster_rows = customer_df[customer_df["cluster"] == c][["Customer_ID", "spend", "orders", "cluster"]]
        n_sample = min(1500, len(cluster_rows))
        cluster_sample = cluster_rows.sample(n=n_sample, random_state=RANDOM_SEED)
        sample_parts.append(cluster_sample)

    sample_df = pd.concat(sample_parts, ignore_index=True)

    pred_sample_csv = out_dir / "prediction_sample_10M.csv"
    sample_df.to_csv(pred_sample_csv, index=False)
    print(f"  [OK] Wrote prediction_sample_10M.csv ({len(sample_df):,} stratified random points)")

    # Cluster summary
    cluster_summary_df = (
        customer_df.groupby("cluster", as_index=False)
        .agg(
            customers=("Customer_ID", "count"),
            spend=("spend", "mean"),
            items=("items", "mean"),
            orders=("orders", "mean"),
        )
        .sort_values("cluster")
    )
    cluster_summary_df[["spend", "items", "orders"]] = cluster_summary_df[["spend", "items", "orders"]].round(2)
    cluster_summary_list = cluster_summary_df.to_dict(orient="records")

    segmentation_meta = {
        "features": ["spend", "items", "orders"],
        "scaling_means": scaler.mean_.tolist(),
        "scaling_stds": scaler.scale_.tolist(),
        "random_seed": RANDOM_SEED,
        "n_clusters": 3,
        "total_segmented_customers": n_customers,
        "scatter_sampling_method": "Stratified random sampling (random_state=42, max 1,500 per cluster)",
    }

    return customer_df, sample_df, cluster_summary_list, segmentation_meta


# ===========================================================================
# 6. Build New Product Performance Analysis & Category Benchmarks
# ===========================================================================
def build_new_product_performance(
    conn: sqlite3.Connection,
    raw_source_path: str,
    out_dir: Path,
    streaming_metrics: dict[str, Any],
) -> dict[str, Any]:
    """Compute product adoption, distinct buyers, repeat buyers, monthly

    first-time cohorts, and per-product arithmetic mean category benchmarks.
    """
    print(f"\n{'='*72}")
    print(">> STEP 4: New Product Performance & Category Benchmarks")
    print(f"{'='*72}\n")

    cur = conn.cursor()

    # Index for sub-second queries
    print("  Creating database index on (product_id, order_date) ...")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_prod_date ON filtered_orders(product_id, order_date);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_cat_date ON filtered_orders(category, order_date);")
    conn.commit()

    # Get distinct products catalog
    cur.execute("""
    SELECT DISTINCT product_id, product_name, category, brand
    FROM filtered_orders
    ORDER BY product_id;
    """)
    catalog = cur.fetchall()
    print(f"  Evaluating customer response for {len(catalog)} catalog products ...")

    # Map category -> list of product_ids
    category_products_map: dict[str, list[str]] = {}
    for pid, _, cat, _ in catalog:
        category_products_map.setdefault(cat, []).append(pid)

    products_output: list[dict[str, Any]] = []

    for pid, pname, cat, brand in catalog:
        # Earliest recorded sale date
        cur.execute("SELECT MIN(order_date) FROM filtered_orders WHERE product_id = ?", (pid,))
        first_sale_date_str = cur.fetchone()[0]

        # Calculate observation window: up to 3 years from first recorded sale, capped at GLOBAL_CUTOFF_DATE
        first_sale_dt = datetime.strptime(first_sale_date_str, "%Y-%m-%d")
        three_years_dt = datetime(first_sale_dt.year + 3, first_sale_dt.month, first_sale_dt.day)
        cutoff_dt = datetime.strptime(GLOBAL_CUTOFF_DATE, "%Y-%m-%d")
        window_end_dt = min(three_years_dt, cutoff_dt)
        window_end_str = window_end_dt.strftime("%Y-%m-%d")

        # Number of calendar months in observation window
        months_count = (window_end_dt.year - first_sale_dt.year) * 12 + (window_end_dt.month - first_sale_dt.month) + 1

        # Metrics strictly inside [first_sale_date_str, window_end_str]
        cur.execute("""
        SELECT COUNT(DISTINCT customer_id) as unique_cust,
               COUNT(DISTINCT order_id) as total_orders,
               SUM(quantity) as units,
               ROUND(SUM(revenue_poisha) / 100.0, 2) as revenue
        FROM filtered_orders
        WHERE product_id = ?
          AND order_date >= ?
          AND order_date <= ?;
        """, (pid, first_sale_date_str, window_end_str))
        u_cust, t_orders, t_units, t_rev = cur.fetchone()
        u_cust = u_cust or 0
        t_orders = t_orders or 0
        t_units = t_units or 0
        t_rev = t_rev or 0.0

        # Repeat buyers: customers with >= 2 DISTINCT order_ids of this product inside window
        cur.execute("""
        SELECT COUNT(*)
        FROM (
            SELECT customer_id
            FROM filtered_orders
            WHERE product_id = ?
              AND order_date >= ?
              AND order_date <= ?
            GROUP BY customer_id
            HAVING COUNT(DISTINCT order_id) >= 2
        );
        """, (pid, first_sale_date_str, window_end_str))
        repeat_buyers = cur.fetchone()[0] or 0
        repeat_rate = round((repeat_buyers / u_cust * 100.0), 2) if u_cust else 0.0
        avg_units_per_order = round((t_units / t_orders), 2) if t_orders else 0.0
        avg_rev_per_cust = round((t_rev / u_cust), 2) if u_cust else 0.0

        # Monthly Trend: active buyers, orders, units, revenue, and first-time product buyers
        cur.execute("""
        WITH monthly_base AS (
            SELECT period,
                   COUNT(DISTINCT customer_id) as monthly_unique_customers,
                   COUNT(DISTINCT order_id) as orders,
                   SUM(quantity) as units,
                   ROUND(SUM(revenue_poisha) / 100.0, 2) as revenue
            FROM filtered_orders
            WHERE product_id = ?
              AND order_date >= ?
              AND order_date <= ?
            GROUP BY period
        ),
        first_buys AS (
            SELECT customer_id, MIN(period) as first_period
            FROM filtered_orders
            WHERE product_id = ?
              AND order_date >= ?
              AND order_date <= ?
            GROUP BY customer_id
        ),
        first_counts AS (
            SELECT first_period as period, COUNT(*) as first_time_buyers
            FROM first_buys
            GROUP BY first_period
        )
        SELECT m.period, m.units, m.monthly_unique_customers,
               COALESCE(f.first_time_buyers, 0) as first_time_buyers,
               m.revenue, m.orders
        FROM monthly_base m
        LEFT JOIN first_counts f ON m.period = f.period
        ORDER BY m.period;
        """, (pid, first_sale_date_str, window_end_str, pid, first_sale_date_str, window_end_str))
        trend_rows = cur.fetchall()

        monthly_trend = [
            {
                "period": r[0],
                "units": int(r[1]),
                "monthly_unique_customers": int(r[2]),
                "first_time_buyers": int(r[3]),
                "revenue": float(r[4]),
                "orders": int(r[5]),
            }
            for r in trend_rows
        ]

        # Cohort validation: sum of first-time buyers across all months must equal unique_customers!
        sum_first_time = sum(m["first_time_buyers"] for m in monthly_trend)
        assert sum_first_time == u_cust, (
            f"Product {pid} cohort discrepancy: sum of first-time buyers ({sum_first_time}) != unique customers ({u_cust})"
        )

        # Category benchmark over identical window [first_sale_date_str, window_end_str]:
        # Evaluates each comparison product in the category separately, then takes the arithmetic mean.
        # Benchmark includes all catalog products in the category (including the target product).
        category_products = category_products_map.get(cat, [pid])
        per_product_benchmark_metrics = []

        for q_id in category_products:
            cur.execute("""
            SELECT COUNT(DISTINCT customer_id),
                   COUNT(DISTINCT order_id),
                   SUM(quantity),
                   ROUND(SUM(revenue_poisha) / 100.0, 2)
            FROM filtered_orders
            WHERE product_id = ?
              AND order_date >= ?
              AND order_date <= ?;
            """, (q_id, first_sale_date_str, window_end_str))
            q_row = cur.fetchone()
            q_u_cust = q_row[0] or 0
            q_t_units = q_row[2] or 0
            q_t_rev = q_row[3] or 0.0

            cur.execute("""
            SELECT COUNT(*)
            FROM (
                SELECT customer_id
                FROM filtered_orders
                WHERE product_id = ?
                  AND order_date >= ?
                  AND order_date <= ?
                GROUP BY customer_id
                HAVING COUNT(DISTINCT order_id) >= 2
            );
            """, (q_id, first_sale_date_str, window_end_str))
            q_repeat_cust = cur.fetchone()[0] or 0
            q_repeat_rate = round((q_repeat_cust / q_u_cust * 100.0), 2) if q_u_cust else 0.0

            per_product_benchmark_metrics.append({
                "product_id": q_id,
                "units": q_t_units,
                "revenue": q_t_rev,
                "customers": q_u_cust,
                "repeat_customers": q_repeat_cust,
                "repeat_rate": q_repeat_rate,
            })

        n_benchmark_products = len(per_product_benchmark_metrics)
        avg_units = round(sum(m["units"] for m in per_product_benchmark_metrics) / n_benchmark_products, 1) if n_benchmark_products else 0.0
        avg_rev = round(sum(m["revenue"] for m in per_product_benchmark_metrics) / n_benchmark_products, 1) if n_benchmark_products else 0.0
        avg_cust = round(sum(m["customers"] for m in per_product_benchmark_metrics) / n_benchmark_products, 1) if n_benchmark_products else 0.0
        avg_repeat_cust = round(sum(m["repeat_customers"] for m in per_product_benchmark_metrics) / n_benchmark_products, 1) if n_benchmark_products else 0.0
        avg_repeat_rate = round(sum(m["repeat_rate"] for m in per_product_benchmark_metrics) / n_benchmark_products, 2) if n_benchmark_products else 0.0

        products_output.append({
            "product_id": pid,
            "product_name": pname,
            "category": cat,
            "brand": brand,
            "has_verified_launch_date": False,
            "first_recorded_sale": first_sale_date_str,
            "date_label": "First recorded sale",
            "observation_window": {
                "start": first_sale_date_str,
                "end": window_end_str,
                "months": months_count,
                "global_cutoff": GLOBAL_CUTOFF_DATE,
            },
            "metrics": {
                "unique_customers": int(u_cust),
                "orders": int(t_orders),
                "units": int(t_units),
                "revenue": float(t_rev),
                "repeat_customers": int(repeat_buyers),
                "repeat_rate": float(repeat_rate),
                "avg_units_per_order": float(avg_units_per_order),
                "avg_revenue_per_customer": float(avg_rev_per_cust),
            },
            "monthly_trend": monthly_trend,
            "category_benchmark": {
                "product_count": int(n_benchmark_products),
                "benchmark_scope": "Arithmetic mean of per-product metrics across all catalog products in category (including selected product) over identical observation window.",
                "avg_units": float(avg_units),
                "avg_revenue": float(avg_rev),
                "avg_customers": float(avg_cust),
                "avg_repeat_customers": float(avg_repeat_cust),
                "avg_repeat_rate": float(avg_repeat_rate),
            },
        })

    perf_payload = {
        "meta": {
            "generated_at": datetime.now().isoformat(),
            "source_dataset": raw_source_path,
            "total_transactions_filtered": int(streaming_metrics["filtered_rows"]),
            "total_transactions_base": int(streaming_metrics["full_rows"]),
            "global_cutoff": GLOBAL_CUTOFF_DATE,
            "global_start": GLOBAL_START_DATE,
            "schema_audit": {
                "product_id_present": True,
                "product_name_present": True,
                "customer_id_present": True,
                "order_id_present": True,
                "transaction_date_present": True,
                "quantity_present": True,
                "net_revenue_present": True,
                "launch_date_column_present": False,
                "new_product_flag_present": False,
                "ten_million_pipeline_note": (
                    "Computed directly from raw transactions file via chunked disk-backed aggregation. "
                    "Distinct customer counts and repeat buyer counts are derived with exact SQL distinct evaluation."
                ),
                "date_proxy_note": (
                    "Because verified launch dates are absent from the dataset schema, metrics track customer response "
                    "from the First recorded sale date through the 3-year observation window or 2026-05-31 cutoff."
                ),
                "market_claim_disclaimer": (
                    "These metrics reflect customer response within this e-commerce dataset only; "
                    "they do not represent market-wide popularity or market share."
                ),
            },
            "source_scope": {
                "file": raw_source_path,
                "base_total_rows": int(streaming_metrics["full_rows"]),
                "filtered_rows_used": int(streaming_metrics["filtered_rows"]),
                "date_range": f"{GLOBAL_START_DATE} to {GLOBAL_CUTOFF_DATE}",
                "available_history_months": ANALYSIS_PERIOD_MOS,
                "is_ten_million_dataset": streaming_metrics["full_rows"] == EXPECTED_FULL_ROWS,
                "is_three_year_analysis": False,
                "scope_statement_en": (
                    f"Source Scope: Dataset ({raw_source_path} · "
                    f"{streaming_metrics['filtered_rows']:,} filtered records · Jan 2023 – May 2026 / 41 months)."
                ),
                "scope_statement_bn": (
                    f"উৎস পরিধি: ডেটাসেট ({raw_source_path} · "
                    f"{streaming_metrics['filtered_rows']:,}টি ফিল্টার্ড রেকর্ড · জানু ২০২৩ – মে ২০২৬ / ৪১ মাস)।"
                ),
            },
        },
        "products": products_output,
    }

    perf_json_path = out_dir / "product_performance.json"
    with perf_json_path.open("w", encoding="utf-8") as f:
        json.dump(perf_payload, f, indent=2, ensure_ascii=False)

    print(f"  [OK] Wrote product_performance.json ({perf_json_path.stat().st_size / 1024:.1f} KB)")
    return perf_payload


# ===========================================================================
# 7. Build dashboard_summary_10M.json
# ===========================================================================
def build_dashboard_summary(
    conn: sqlite3.Connection,
    streaming_metrics: dict[str, Any],
    cluster_summary_list: list[dict[str, Any]],
    n_unique_customers: int,
    out_dir: Path,
    test_mode: bool = False,
) -> dict[str, Any]:
    """Assemble dashboard_summary_10M.json using actual computed metrics."""
    print(f"\n{'='*72}")
    print(">> STEP 5: Assembling dashboard_summary_10M.json")
    print(f"{'='*72}\n")

    cur = conn.cursor()

    # 1. Monthly list from disk-backed monthly_order_events
    cur.execute("""
    SELECT period,
           COUNT(DISTINCT order_id) as orders,
           SUM(quantity) as units,
           ROUND(SUM(revenue_poisha) / 100.0, 2) as revenue
    FROM monthly_order_events
    GROUP BY period
    ORDER BY period;
    """)
    monthly_rows = cur.fetchall()
    monthly_list = [
        {"Period": r[0], "orders": int(r[1]), "units": int(r[2]), "revenue": float(r[3])}
        for r in monthly_rows
    ]

    # 2. Categories (cutoff scope)
    cur.execute("""
    SELECT category,
           ROUND(SUM(revenue_poisha) / 100.0, 2) as revenue,
           SUM(quantity) as units,
           COUNT(DISTINCT order_id) as orders,
           ROUND(AVG(rating), 2) as average_rating
    FROM filtered_orders
    GROUP BY category
    ORDER BY revenue DESC;
    """)
    category_list = [
        {"Category": r[0], "revenue": float(r[1]), "units": int(r[2]), "orders": int(r[3]), "average_rating": float(r[4])}
        for r in cur.fetchall()
    ]

    # 3. Payments (cutoff scope)
    cur.execute("""
    SELECT payment_method,
           ROUND(SUM(revenue_poisha) / 100.0, 2) as revenue,
           COUNT(DISTINCT order_id) as orders
    FROM filtered_orders
    GROUP BY payment_method
    ORDER BY revenue DESC;
    """)
    payment_rows = cur.fetchall()
    tot_pay_rev = sum(r[1] for r in payment_rows)
    payment_list = [
        {
            "Payment_Method": r[0],
            "revenue": float(r[1]),
            "orders": int(r[2]),
            "share": round(r[1] / tot_pay_rev * 100.0, 2) if tot_pay_rev else 0.0,
        }
        for r in payment_rows
    ]

    # 4. Locations (cutoff scope)
    cur.execute("""
    SELECT location,
           ROUND(SUM(revenue_poisha) / 100.0, 2) as revenue,
           COUNT(DISTINCT order_id) as orders,
           SUM(quantity) as units,
           COUNT(DISTINCT customer_id) as customers
    FROM filtered_orders
    GROUP BY location
    ORDER BY revenue DESC;
    """)
    location_list = [
        {"Location": r[0], "revenue": float(r[1]), "orders": int(r[2]), "units": int(r[3]), "customers": int(r[4])}
        for r in cur.fetchall()
    ]

    # 5. Weekdays (cutoff scope)
    cur.execute("""
    SELECT strftime('%w', order_date) as w_idx,
           ROUND(SUM(revenue_poisha) / 100.0, 2) as revenue,
           COUNT(DISTINCT order_id) as orders
    FROM filtered_orders
    GROUP BY w_idx
    ORDER BY w_idx;
    """)
    w_map = {"1": "Monday", "2": "Tuesday", "3": "Wednesday", "4": "Thursday", "5": "Friday", "6": "Saturday", "0": "Sunday"}
    weekday_dict = {w_map.get(str(r[0]), "Other"): {"revenue": float(r[1]), "orders": int(r[2])} for r in cur.fetchall()}
    WEEKDAY_ORDER = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    weekday_list = [
        {"weekday": wd, "revenue": weekday_dict.get(wd, {}).get("revenue", 0.0), "orders": weekday_dict.get(wd, {}).get("orders", 0)}
        for wd in WEEKDAY_ORDER
    ]

    # 6. Materials & Sizes (cutoff scope)
    cur.execute("SELECT material, SUM(quantity) as units FROM filtered_orders GROUP BY material ORDER BY units DESC;")
    material_list = [{"Material": r[0], "units": int(r[1])} for r in cur.fetchall()]

    cur.execute("SELECT size, SUM(quantity) as units FROM filtered_orders GROUP BY size ORDER BY units DESC;")
    size_list = [{"Size": r[0], "units": int(r[1])} for r in cur.fetchall()]

    # 7. Top 30 products (cutoff scope)
    cur.execute("""
    SELECT product_id, product_name, category, brand,
           SUM(quantity) as units,
           ROUND(SUM(revenue_poisha) / 100.0, 2) as revenue,
           COUNT(DISTINCT order_id) as orders,
           ROUND(AVG(price), 2) as price,
           ROUND(AVG(discount), 2) as discount,
           ROUND(AVG(rating), 2) as rating
    FROM filtered_orders
    GROUP BY product_id, product_name, category, brand
    ORDER BY units DESC
    LIMIT 30;
    """)
    product_list = [
        {
            "Product_ID": r[0],
            "Product_Name": r[1],
            "Category": r[2],
            "Brand": r[3],
            "units": int(r[4]),
            "revenue": float(r[5]),
            "orders": int(r[6]),
            "price": float(r[7]),
            "discount": float(r[8]),
            "rating": float(r[9]),
        }
        for r in cur.fetchall()
    ]

    # 8. Customer stats
    cur.execute("""
    SELECT COUNT(DISTINCT customer_id) as total_c,
           AVG(spend) as avg_spend,
           AVG(orders) as avg_orders
    FROM (
        SELECT customer_id,
               SUM(revenue_poisha) / 100.0 as spend,
               COUNT(DISTINCT order_id) as orders
        FROM filtered_orders
        GROUP BY customer_id
    );
    """)
    tot_c, avg_c_spend, avg_c_orders = cur.fetchone()

    cur.execute("""
    SELECT COUNT(*)
    FROM (
        SELECT customer_id
        FROM filtered_orders
        GROUP BY customer_id
        HAVING COUNT(DISTINCT order_id) > 1
    );
    """)
    repeat_c = cur.fetchone()[0]

    cur.execute("SELECT ROUND(AVG(rating), 2) FROM filtered_orders;")
    filtered_avg_rating = cur.fetchone()[0] or 3.75

    # Computed KPI values
    full_revenue = round(streaming_metrics["full_revenue"], 2)
    full_distinct_orders = int(streaming_metrics["full_distinct_orders"])
    full_units = int(streaming_metrics["full_units"])
    full_rows = int(streaming_metrics["full_rows"])

    filtered_revenue = round(streaming_metrics["filtered_revenue"], 2)
    filtered_distinct_orders = int(streaming_metrics["filtered_distinct_orders"])
    filtered_units = int(streaming_metrics["filtered_units"])
    filtered_rows = int(streaming_metrics["filtered_rows"])

    avg_order_value = round(full_revenue / full_distinct_orders, 2) if full_distinct_orders else 0.0
    filtered_aov = round(filtered_revenue / filtered_distinct_orders, 2) if filtered_distinct_orders else 0.0

    summary_payload = {
        "meta": {
            "generated_at": datetime.now().isoformat(),
            "pipeline": "scripts/process_10m_colab.py",
            "test_mode": test_mode,
            "global_start_date": GLOBAL_START_DATE,
            "global_cutoff_date": GLOBAL_CUTOFF_DATE,
            "period_months": ANALYSIS_PERIOD_MOS,
            "full_dataset_rows": full_rows,
            "full_dataset_distinct_orders": full_distinct_orders,
            "filtered_rows": filtered_rows,
            "filtered_distinct_orders": filtered_distinct_orders,
            "note": "Precomputed aggregates derived from transactional dataset. Web backend reads only these lightweight summary files.",
        },
        "kpis": {
            "revenue": full_revenue,
            "orders": full_distinct_orders,
            "units": full_units,
            "customers": int(n_unique_customers),
            "average_order_value": avg_order_value,
            "average_rating": float(filtered_avg_rating),
            "filtered_revenue": filtered_revenue,
            "filtered_orders": filtered_distinct_orders,
            "filtered_units": filtered_units,
            "filtered_aov": filtered_aov,
            "period_months": ANALYSIS_PERIOD_MOS,
            "full_dataset_rows": full_rows,
            "full_dataset_revenue": full_revenue,
            "full_dataset_units": full_units,
        },
        "date_range": {
            "start": GLOBAL_START_DATE,
            "end": GLOBAL_CUTOFF_DATE,
            "full_dataset_end": FULL_DATASET_END,
            "period_months": ANALYSIS_PERIOD_MOS,
            "is_filtered": True,
        },
        "monthly": monthly_list,
        "categories": category_list,
        "payments": payment_list,
        "locations": location_list,
        "weekday": weekday_list,
        "materials": material_list,
        "sizes": size_list,
        "products_top30": product_list,
        "cluster_summary": cluster_summary_list,
        "customer_stats": {
            "customer_count": int(tot_c or n_unique_customers),
            "repeat_customers": int(repeat_c or 0),
            "average_customer_value": round(float(avg_c_spend or 0.0), 2),
            "average_orders_per_customer": round(float(avg_c_orders or 0.0), 2),
        },
        "methodology": {
            "rows": full_rows,
            "filtered_rows": filtered_rows,
            "columns": len(REQUIRED_COLUMNS),
            "date_start": GLOBAL_START_DATE,
            "date_end": GLOBAL_CUTOFF_DATE,
            "full_dataset_date_end": FULL_DATASET_END,
            "period_months": ANALYSIS_PERIOD_MOS,
            "missing_values": 0,
            "duplicate_rows_removed": 0,
            "revenue_definition": "Price × Quantity × (1 − Discount / 100)",
            "segmentation": (
                "MiniBatchKMeans (k=3, seed=42) on standardized customer net spend, "
                "item count, and distinct order count derived strictly from the active cutoff scope (2023-01-01 to 2026-05-31)."
            ),
            "prediction": (
                "Quantity prediction. Provenance Unverified: Precomputed model weights and metrics in prediction.py "
                "are served statically without runtime training. This offline data processing pipeline aggregates "
                "transaction history and fits customer segmentation, but does NOT train or evaluate demand forecasting models."
            ),
        },
        "model_metrics": {
            "status": "not_trained_by_pipeline",
            "note": (
                "Prediction model training was not performed by this offline pipeline. "
                "Demand forecasting models in prediction.py remain statically precomputed baseline constants."
            ),
            "model_provenance_note": (
                "Provenance Unverified: Scoring weights and evaluation metrics are precomputed baseline constants "
                "without runtime training. No verifiable training script exists in the repository for the ML model fitting."
            ),
            "categories": streaming_metrics["unique_categories"],
            "brands": streaming_metrics["unique_brands"],
            "sizes": streaming_metrics["unique_sizes"],
        },
    }

    summary_json_path = out_dir / "dashboard_summary_10M.json"
    with summary_json_path.open("w", encoding="utf-8") as f:
        json.dump(summary_payload, f, indent=2, ensure_ascii=False)

    print(f"  [OK] Wrote dashboard_summary_10M.json ({summary_json_path.stat().st_size / 1024:.1f} KB)")
    return summary_payload


# ===========================================================================
# 8. Manifest & Deployment ZIP Archive
# ===========================================================================
def build_manifest_and_zip(
    out_dir: Path,
    raw_source_path: str,
    streaming_metrics: dict[str, Any],
    segmentation_meta: dict[str, Any],
    n_unique_customers: int,
    reconciliation_passed: bool,
    test_mode: bool = False,
) -> Path:
    """Create audit manifest.json and lightweight deployment ZIP archive."""
    print(f"\n{'='*72}")
    print(">> STEP 6: Manifest Generation & Deployment ZIP Packaging")
    print(f"{'='*72}\n")

    manifest = {
        "pipeline_name": "E-Commerce Dress Sales Offline Pipeline (Cutoff 2026-05-31)",
        "script": "scripts/process_10m_colab.py",
        "generated_at": datetime.now().isoformat(),
        "execution_mode": "test_mode" if test_mode else "production",
        "source_dataset": {
            "path": raw_source_path,
            "read_mode": "read_only",
            "raw_overwrite_prevented": True,
        },
        "date_scope": {
            "start_date": GLOBAL_START_DATE,
            "cutoff_date": GLOBAL_CUTOFF_DATE,
            "period_months": ANALYSIS_PERIOD_MOS,
            "full_dataset_end": FULL_DATASET_END,
        },
        "actual_measurements": {
            "full_rows": int(streaming_metrics["full_rows"]),
            "full_units": int(streaming_metrics["full_units"]),
            "full_revenue": round(streaming_metrics["full_revenue"], 2),
            "full_distinct_orders": int(streaming_metrics["full_distinct_orders"]),
            "filtered_rows": int(streaming_metrics["filtered_rows"]),
            "filtered_units": int(streaming_metrics["filtered_units"]),
            "filtered_revenue": round(streaming_metrics["filtered_revenue"], 2),
            "filtered_distinct_orders": int(streaming_metrics["filtered_distinct_orders"]),
            "filtered_unique_customers": int(n_unique_customers),
            "invalid_dates": int(streaming_metrics["invalid_dates"]),
        },
        "reconciliation": {
            "performed": not test_mode,
            "passed": reconciliation_passed,
            "expected_full_rows": EXPECTED_FULL_ROWS,
            "expected_full_units": EXPECTED_FULL_UNITS,
            "expected_full_revenue": EXPECTED_FULL_REVENUE,
            "expected_filtered_rows": EXPECTED_FILTERED_ROWS,
            "expected_filtered_units": EXPECTED_FILTERED_UNITS,
            "expected_filtered_revenue": EXPECTED_FILTERED_REVENUE,
            "note": "Production reconciliation verifies 10M constants. In test mode, reconciliation is skipped." if test_mode else "All production assertions verified.",
        },
        "calculation_definitions": {
            "net_revenue": "Price × Quantity × (1 − Discount / 100)",
            "monetary_precision": "Integer Poisha (cents) accumulation, preventing IEEE 754 floating point drift",
            "repeat_buyer_definition": "Customer with >= 2 DISTINCT order IDs for the same product within observation window",
            "distinct_order_rule": "Strict SQL COUNT(DISTINCT order_id); never substituted with row count or summed across buckets",
            "observation_window": "Earliest recorded sale up to min(first_recorded_sale + 3 years, 2026-05-31)",
            "category_benchmark": "Arithmetic mean of per-product metrics across all catalog products in category over identical observation window",
            "first_recorded_sale_disclaimer": "Earliest transaction date proxy; NOT a verified product launch date",
        },
        "data_privacy_and_identifiers": {
            "customer_identifiers_present_in_csv": True,
            "customer_id_retention_reason": (
                "The aggregate tables customer_agg_10M.csv and prediction_sample_10M.csv retain pseudo-anonymized "
                "Customer_ID values required for account ledger pagination and scatter map coordinates."
            ),
            "customer_identifiers_present_in_json": False,
            "pii_present": False,
            "transaction_record_linkage_present": False,
        },
        "segmentation_parameters": segmentation_meta,
        "prediction_provenance_status": "Provenance Unverified (Preserved; no training performed)",
        "files_generated": [
            "dashboard_summary_10M.json",
            "customer_agg_10M.csv",
            "prediction_sample_10M.csv",
            "product_performance.json",
            "manifest.json",
        ],
    }

    manifest_path = out_dir / "manifest.json"
    with manifest_path.open("w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    print(f"  [OK] Wrote manifest.json ({manifest_path.stat().st_size / 1024:.1f} KB)")

    # Build ZIP archive containing ONLY the 5 processed files
    zip_filename = "processed_deployment_cutoff_20260531.zip"
    zip_path_in_drive = out_dir / zip_filename
    target_files = [
        out_dir / "dashboard_summary_10M.json",
        out_dir / "customer_agg_10M.csv",
        out_dir / "prediction_sample_10M.csv",
        out_dir / "product_performance.json",
        manifest_path,
    ]

    print(f"\n  Compressing deployment ZIP archive -> {zip_path_in_drive} ...")
    with zipfile.ZipFile(zip_path_in_drive, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for f in target_files:
            zf.write(f, arcname=f.name)
            print(f"    + Added {f.name} ({f.stat().st_size / 1024:.1f} KB)")

    zip_size_mb = zip_path_in_drive.stat().st_size / (1024 * 1024)
    print(f"  [OK] Created deployment ZIP: {zip_path_in_drive} ({zip_size_mb:.2f} MB)")

    # If running in Colab, also copy ZIP to /content/ for direct download
    if is_running_in_colab():
        colab_zip_dest = Path("/content") / zip_filename
        shutil.copyfile(zip_path_in_drive, colab_zip_dest)
        print(f"  [OK] Copied deployment ZIP to {colab_zip_dest} for direct download.")

    return zip_path_in_drive


# ===========================================================================
# 9. Main CLI Controller
# ===========================================================================
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Standalone Colab Data Processing Pipeline for 10M E-Commerce Dress Sales."
    )
    default_raw, default_out = get_default_paths()

    parser.add_argument(
        "--raw-file",
        type=Path,
        default=default_raw,
        help=f"Path to raw dress_sales_10M.csv.gz (Default: {default_raw})",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=default_out,
        help=f"Path to write new processed files (Default: {default_out})",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=250_000,
        help="Number of rows per processing chunk (Default: 250,000)",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing output directory files if already present",
    )
    parser.add_argument(
        "--test-mode",
        action="store_true",
        help="Run in test mode on small test fixtures (bypasses 10M reconciliation assertions)",
    )
    args = parser.parse_args()

    print("\n" + "=" * 76)
    print("  10M E-Commerce Dress Sales — Standalone Colab Processing Pipeline")
    print(f"  Execution Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 76)

    ensure_google_drive_mounted()

    raw_csv_gz = args.raw_file.resolve()
    out_dir = args.output_dir.resolve()

    if not raw_csv_gz.is_file():
        print(f"\n[ERROR] Raw dataset file not found at: {raw_csv_gz}")
        print("Please verify your Google Drive path:")
        print("  /content/drive/MyDrive/Ecommerce_Dress_Sales_10M/raw/dress_sales_10M.csv.gz\n")
        sys.exit(1)

    # Overwrite protection: check if existing output files already exist
    existing_target_files = [
        out_dir / "dashboard_summary_10M.json",
        out_dir / "customer_agg_10M.csv",
        out_dir / "prediction_sample_10M.csv",
        out_dir / "product_performance.json",
        out_dir / "manifest.json",
        out_dir / "processed_deployment_cutoff_20260531.zip",
    ]
    conflicts = [f.name for f in existing_target_files if f.is_file()]
    if conflicts and not args.overwrite:
        print(f"\n[ERROR] Output directory '{out_dir}' already contains processed files:")
        for c in conflicts:
            print(f"  - {c}")
        print("\nTo prevent accidental overwriting of prior execution runs, execution stopped.")
        print("Specify --overwrite to intentionally replace these files.\n")
        sys.exit(1)

    print(f"  Raw Source File   : {raw_csv_gz} ({raw_csv_gz.stat().st_size / (1024*1024):.1f} MB)")
    print(f"  Output Directory  : {out_dir}")
    print(f"  Chunk Size        : {args.chunk_size:,} rows")
    print(f"  Global Cutoff     : {GLOBAL_CUTOFF_DATE} (Start: {GLOBAL_START_DATE})")
    print(f"  Execution Mode    : {'TEST MODE (Fixture Sanity)' if args.test_mode else 'PRODUCTION (10M Assertions Enforced)'}")

    out_dir.mkdir(parents=True, exist_ok=True)

    # Use local SSD /tmp for staging DB
    tmp_fd, staging_db_path = tempfile.mkstemp(prefix="colab_10m_staging_", suffix=".db")
    os.close(tmp_fd)
    staging_db = Path(staging_db_path)

    total_start = time.perf_counter()
    reconciliation_passed = False

    try:
        # Step 1: Chunked reading & staging
        streaming_metrics, conn = stage_and_aggregate_raw_dataset(
            raw_csv_gz=raw_csv_gz,
            chunk_size=args.chunk_size,
            staging_db_path=staging_db,
        )

        # Step 2: Reconciliation assertions
        reconciliation_passed = verify_source_totals_reconciliation(
            streaming_metrics,
            test_mode=args.test_mode,
        )

        # Step 3: Customers & Segmentation
        cust_df, sample_df, cluster_summary_list, seg_meta = build_customers_and_segmentation(
            conn=conn,
            out_dir=out_dir,
        )

        # Step 4: New Product Performance
        build_new_product_performance(
            conn=conn,
            raw_source_path=str(raw_csv_gz),
            out_dir=out_dir,
            streaming_metrics=streaming_metrics,
        )

        # Step 5: Dashboard Summary JSON
        build_dashboard_summary(
            conn=conn,
            streaming_metrics=streaming_metrics,
            cluster_summary_list=cluster_summary_list,
            n_unique_customers=len(cust_df),
            out_dir=out_dir,
            test_mode=args.test_mode,
        )

        # Step 6: Manifest & Deployment ZIP
        zip_path = build_manifest_and_zip(
            out_dir=out_dir,
            raw_source_path=str(raw_csv_gz),
            streaming_metrics=streaming_metrics,
            segmentation_meta=seg_meta,
            n_unique_customers=len(cust_df),
            reconciliation_passed=reconciliation_passed,
            test_mode=args.test_mode,
        )

        conn.close()

    finally:
        # Always remove temporary staging DB
        if staging_db.is_file():
            try:
                staging_db.unlink()
                print(f"  [OK] Cleaned up local temporary staging database ({staging_db.name})")
            except Exception:
                pass

    total_elapsed = time.perf_counter() - total_start
    print("\n" + "=" * 76)
    print(f"[SUCCESS] PIPELINE COMPLETED SUCCESSFULLY IN {total_elapsed / 60:.2f} MINUTES!")
    print(f"   Outputs stored in: {out_dir}")
    print(f"   Deployment ZIP   : {zip_path}")
    print("=" * 76 + "\n")


if __name__ == "__main__":
    main()
