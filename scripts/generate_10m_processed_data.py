"""
scripts/generate_10m_processed_data.py
=======================================
Offline data processing pipeline for the 10M synthetic e-commerce dress sales dataset.

RECOMMENDED EXECUTION ENVIRONMENT
----------------------------------
Run this script in Google Colab with Google Drive mounted.
Google Colab provides free GPU/CPU compute and sufficient RAM (12–25 GB)
to handle the chunk-wise processing without crashing.

    Google Colab notebook URL:
        https://colab.research.google.com/

    Steps:
        1. Open a new Colab notebook.
        2. Upload or clone this repository (or just upload this script).
        3. Mount Google Drive (the script does this automatically when in Colab).
        4. Run: !python generate_10m_processed_data.py

LOCAL FALLBACK
--------------
If NOT running in Colab, the script falls back to local paths.
Raw 10M output will be written to data/raw/ (gitignored).
Processed outputs will be written to data/processed/.

    python scripts/generate_10m_processed_data.py

IMPORTANT: Copy only the THREE processed files into your project's data/processed/:
    dashboard_summary_10M.json
    customer_agg_10M.csv
    prediction_sample_10M.csv

Do NOT copy the raw .csv.gz file into the project — it is too large for GitHub.

─────────────────────────────────────────────────────────────────────────────

PURPOSE
-------
This script is run ONCE (or periodically to refresh data) on a machine with
sufficient RAM and compute. It must NEVER be called at web server startup or
during a live API request.

The web backend (FastAPI) does NOT load raw 10M data. Instead it reads the
small processed summary files produced here:
    data/processed/dashboard_summary_10M.json  (~50 KB)
    data/processed/customer_agg_10M.csv        (~a few MB, one row per customer)
    data/processed/prediction_sample_10M.csv   (~150 KB, ≤4,500 sampled rows)

WHY NOT LOAD THE RAW 10M CSV ON THE WEB SERVER?
------------------------------------------------
• A 10,000,000-row CSV is typically 800 MB – 2 GB in memory.
• Loading it on every server start would OOM most cloud instances.
• Training a Random Forest on 8M rows takes hours, not milliseconds.
• Sending all customer records to the browser crashes the tab.
• Pre-computing summaries reduces web response time from minutes → milliseconds.

REAL-COMPANY ANALOGY
--------------------
In a real company, data flows from:
    • Website order database (PostgreSQL / MySQL)
    • POS (Point-of-Sale) systems
    • Excel / CSV sales exports
    • E-commerce platform APIs (Shopify, WooCommerce, Daraz, etc.)
    • Customer databases / CRMs

A scheduled ETL job (e.g. Apache Spark, dbt, or a cron script like this one)
reads from those sources, computes summaries, and writes them to a data
warehouse or flat files that the dashboard API reads. The dashboard never
touches raw transactional data.

This academic project mirrors that pattern exactly:
    Raw data  →  [offline ETL script]  →  Processed summaries  →  Web backend

GOOGLE DRIVE STORAGE (RECOMMENDED)
------------------------------------
Raw 10M file output path on Drive:
    /content/drive/MyDrive/Ecommerce_Dress_Sales_10M/raw/dress_sales_10M.csv.gz

Processed file output paths on Drive (copy these into project):
    /content/drive/MyDrive/Ecommerce_Dress_Sales_10M/processed/dashboard_summary_10M.json
    /content/drive/MyDrive/Ecommerce_Dress_Sales_10M/processed/customer_agg_10M.csv
    /content/drive/MyDrive/Ecommerce_Dress_Sales_10M/processed/prediction_sample_10M.csv

LOCAL OUTPUT PATHS (fallback, gitignored raw file)
---------------------------------------------------
    data/raw/dress_sales_10M.csv.gz     ← gitignored
    data/processed/dashboard_summary_10M.json
    data/processed/customer_agg_10M.csv
    data/processed/prediction_sample_10M.csv

REQUIREMENTS
------------
    pip install pandas numpy scikit-learn

Estimated runtime : 5–15 minutes (Colab) / 10–30 minutes (local laptop)
Estimated peak RAM: ~400 MB per chunk (total ~2–4 GB peak for accumulators)
"""

from __future__ import annotations

import json
import os
import random
import sys
import time
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.cluster import MiniBatchKMeans
from sklearn.preprocessing import StandardScaler


# ===========================================================================
# SECTION 1: Environment Detection and Path Configuration
# ===========================================================================

def _detect_colab() -> bool:
    """Return True if this script is running inside Google Colab."""
    try:
        import google.colab  # noqa: F401
        return True
    except ImportError:
        return False


def _mount_google_drive() -> None:
    """Mount Google Drive inside Colab. No-op if already mounted."""
    from google.colab import drive  # type: ignore
    mount_point = "/content/drive"
    if not os.path.isdir(os.path.join(mount_point, "MyDrive")):
        print("  Mounting Google Drive …")
        drive.mount(mount_point)
    else:
        print("  Google Drive already mounted ✓")


# ---------------------------------------------------------------------------
# Detect execution environment
# ---------------------------------------------------------------------------
IN_COLAB = _detect_colab()

print("=" * 68)
print("  10M Synthetic E-Commerce Dress Sales — Data Processing Pipeline")
print("=" * 68)
print(f"  Execution environment : {'Google Colab' if IN_COLAB else 'Local machine'}")

if IN_COLAB:
    _mount_google_drive()

    # -----------------------------------------------------------------------
    # Google Drive paths
    # -----------------------------------------------------------------------
    GDRIVE_ROOT   = Path("/content/drive/MyDrive/Ecommerce_Dress_Sales_10M")
    RAW_DIR       = GDRIVE_ROOT / "raw"
    PROCESSED_DIR = GDRIVE_ROOT / "processed"

    # The base dataset: either already on Drive or cloned locally in /content/
    # Try project clone path first, then Drive, then current directory.
    _possible_base = [
        Path("/content/E-commerce_dress_sales_analytics/data/dress_sales.csv"),
        Path("/content/dress_sales.csv"),
        GDRIVE_ROOT / "dress_sales.csv",
    ]
    BASE_CSV = next((p for p in _possible_base if p.is_file()), None)
    if BASE_CSV is None:
        print(
            "\n  [ERROR] Could not find dress_sales.csv.\n"
            "  Please do ONE of the following in Colab before running this script:\n"
            "    Option A — Clone the repo:\n"
            "      !git clone https://github.com/tithisultana/E-commerce_dress_sales_analytics.git\n"
            "    Option B — Upload dress_sales.csv manually to /content/ or Drive.\n"
        )
        sys.exit(1)

    print(f"  Base CSV              : {BASE_CSV}")
    print(f"  Raw output            : {RAW_DIR}/dress_sales_10M.csv.gz")
    print(f"  Processed output      : {PROCESSED_DIR}/")
    print()
    print("  ⚠ IMPORTANT — After the script finishes:")
    print("    Copy these 3 files into your project's data/processed/ folder:")
    print("      dashboard_summary_10M.json")
    print("      customer_agg_10M.csv")
    print("      prediction_sample_10M.csv")
    print("    Do NOT copy the raw .csv.gz — it is too large for GitHub.")
    print()

else:
    # -----------------------------------------------------------------------
    # Local machine paths
    # -----------------------------------------------------------------------
    PROJECT_ROOT  = Path(__file__).resolve().parent.parent
    BASE_CSV      = PROJECT_ROOT / "data" / "dress_sales.csv"
    RAW_DIR       = PROJECT_ROOT / "data" / "raw"
    PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"

    print(f"  Base CSV              : {BASE_CSV}")
    print(f"  Raw output            : {RAW_DIR}/dress_sales_10M.csv.gz  (gitignored)")
    print(f"  Processed output      : {PROCESSED_DIR}/")
    print()
    print("  ⚠ RECOMMENDATION: For the 10M raw file, prefer Google Colab + Drive.")
    print("    See docs/10M_DATA_ARCHITECTURE.md for details.")
    print()

# Final output paths (same structure regardless of environment)
RAW_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

RAW_OUTPUT_GZ    = RAW_DIR       / "dress_sales_10M.csv.gz"
SUMMARY_JSON     = PROCESSED_DIR / "dashboard_summary_10M.json"
CUSTOMER_AGG_CSV = PROCESSED_DIR / "customer_agg_10M.csv"
PRED_SAMPLE_CSV  = PROCESSED_DIR / "prediction_sample_10M.csv"


# ===========================================================================
# SECTION 2: Generation Parameters
# ===========================================================================

TARGET_ROWS  = 10_000_000   # Total synthetic records to generate
CHUNK_SIZE   =    100_000   # Rows per processing iteration.
                             # Each chunk uses ~300 MB RAM, then is released.
                             # The web server NEVER processes chunks — it reads
                             # only the final summary files produced here.
RANDOM_SEED  =          42

rng = np.random.default_rng(RANDOM_SEED)
random.seed(RANDOM_SEED)


# ===========================================================================
# SECTION 3: Load Base Dataset — Derive Domain Value Pools
# ===========================================================================
print(f"[1/7] Reading base dataset: {BASE_CSV}")
base_df = pd.read_csv(BASE_CSV)

CATEGORIES      = sorted(base_df["Category"].dropna().unique().tolist())
BRANDS          = sorted(base_df["Brand"].dropna().unique().tolist())
MATERIALS       = sorted(base_df["Material"].dropna().unique().tolist())
SIZES           = sorted(base_df["Size"].dropna().unique().tolist())
COLORS          = sorted(base_df["Color"].dropna().unique().tolist())
LOCATIONS       = sorted(base_df["Location"].dropna().unique().tolist())
PAYMENT_METHODS = sorted(base_df["Payment_Method"].dropna().unique().tolist())
GENDERS         = ["Female", "Male"]

# Reuse real Product_ID / Product_Name / Category / Brand combinations
PRODUCT_POOL = (
    base_df[["Product_ID", "Product_Name", "Category", "Brand", "Material"]]
    .drop_duplicates()
    .reset_index(drop=True)
)

# Price ranges per category (min, max) — sampled realistically
PRICE_RANGES: dict[str, tuple[float, float]] = {
    cat: (
        float(base_df[base_df["Category"] == cat]["Price"].min()),
        float(base_df[base_df["Category"] == cat]["Price"].max()),
    )
    for cat in CATEGORIES
    if not base_df[base_df["Category"] == cat]["Price"].empty
}

# Synthetic data date range
DATE_START      = date(2023, 1, 1)
DATE_END        = date(2026, 12, 31)
DATE_RANGE_DAYS = (DATE_END - DATE_START).days

# 10M orders spread across ~500k unique customers (realistic repeat-purchase ratio)
NUM_CUSTOMERS   = 500_000

print(f"  Base dataset : {len(base_df):,} rows, {len(PRODUCT_POOL)} unique products")
print(f"  Domain pools : {len(CATEGORIES)} categories · {len(BRANDS)} brands · "
      f"{len(LOCATIONS)} locations · {len(PAYMENT_METHODS)} payment methods")
print(f"  Generating   : {TARGET_ROWS:,} rows in {TARGET_ROWS // CHUNK_SIZE} "
      f"chunks of {CHUNK_SIZE:,}")
print()


# ===========================================================================
# SECTION 4: Running Accumulators
# Aggregated ACROSS all chunks so 10M rows are never held in RAM simultaneously.
# The web server only ever reads the final outputs — not these accumulators.
# ===========================================================================

total_net_sales      = 0.0
total_gross_sales    = 0.0
total_orders         = 0
total_units          = 0
total_ratings_sum    = 0.0
total_ratings_count  = 0
total_rows_generated = 0
duplicates_removed   = 0   # synthetic data has ~0 duplicates by design

monthly_agg:  dict[str, dict] = {}
category_agg: dict[str, dict] = {}
payment_agg:  dict[str, dict] = {}
location_agg: dict[str, dict] = {}
weekday_agg:  dict[str, dict] = {}
product_agg:  dict[str, dict] = {}
material_agg: dict[str, dict] = {}
size_agg:     dict[str, dict] = {}
customer_agg: dict[str, dict] = {}


# ===========================================================================
# SECTION 5: Chunk-Wise Generation and Aggregation Loop
# Key design principle: generate → aggregate → discard each chunk.
# The raw data (if saved) goes to Google Drive / data/raw/ (gitignored).
# Only running totals are kept in memory between chunks.
# ===========================================================================

print("[2/7] Generating synthetic records and aggregating chunk-by-chunk …")
print(f"      Raw compressed file  → {RAW_OUTPUT_GZ}")
print(f"      (This file is stored on Google Drive / gitignored locally — NOT in GitHub)")
print()

WRITE_RAW_GZ = True   # Set False to skip writing the raw compressed file
write_header = True   # CSV header written only on the first chunk
t0 = time.perf_counter()
chunks_done  = 0

for chunk_start in range(0, TARGET_ROWS, CHUNK_SIZE):
    chunk_rows = min(CHUNK_SIZE, TARGET_ROWS - chunk_start)

    # ------------------------------------------------------------------
    # 5a. Generate synthetic values for this chunk
    # ------------------------------------------------------------------
    customer_ids = [f"C{rng.integers(1, NUM_CUSTOMERS + 1):06d}"
                    for _ in range(chunk_rows)]
    order_ids    = [f"O{(chunk_start + i + 1):08d}" for i in range(chunk_rows)]

    product_idx = rng.integers(0, len(PRODUCT_POOL), size=chunk_rows)
    products    = PRODUCT_POOL.iloc[product_idx].reset_index(drop=True)

    day_offsets = rng.integers(0, DATE_RANGE_DAYS, size=chunk_rows)
    dates       = [DATE_START + timedelta(days=int(d)) for d in day_offsets]

    prices = np.array([
        rng.uniform(*PRICE_RANGES.get(cat, (500, 5000)))
        for cat in products["Category"]
    ]).round(0)

    quantities = rng.integers(1, 6, size=chunk_rows)     # 1–5 units per order
    discounts  = rng.choice(
        [0, 5, 10, 15, 20, 25, 30], size=chunk_rows,
        p=[0.10, 0.20, 0.25, 0.20, 0.13, 0.08, 0.04]
    ).astype(float)
    ratings    = rng.uniform(2.5, 5.0, size=chunk_rows).round(1)
    ages       = rng.integers(18, 61, size=chunk_rows)
    genders    = rng.choice(GENDERS, size=chunk_rows, p=[0.72, 0.28])
    sizes      = rng.choice(SIZES, size=chunk_rows)
    colors     = rng.choice(COLORS, size=chunk_rows)
    locations  = rng.choice(LOCATIONS, size=chunk_rows)
    payments   = rng.choice(PAYMENT_METHODS, size=chunk_rows)

    gross_sales  = prices * quantities
    discount_amt = gross_sales * discounts / 100
    net_sales    = gross_sales - discount_amt

    # ------------------------------------------------------------------
    # 5b. Assemble chunk DataFrame
    # ------------------------------------------------------------------
    chunk = pd.DataFrame({
        "Order_ID":        order_ids,
        "Customer_ID":     customer_ids,
        "Gender":          genders,
        "Age":             ages,
        "Location":        locations,
        "Date":            pd.to_datetime(dates),
        "Product_ID":      products["Product_ID"].values,
        "Product_Name":    products["Product_Name"].values,
        "Category":        products["Category"].values,
        "Brand":           products["Brand"].values,
        "Material":        products["Material"].values,
        "Size":            sizes,
        "Color":           colors,
        "Price":           prices,
        "Quantity":        quantities,
        "Discount":        discounts,
        "Payment_Method":  payments,
        "Rating":          ratings,
        "Gross_Sales":     gross_sales,
        "Discount_Amount": discount_amt,
        "Net_Sales":       net_sales,
    })
    chunk["Period"]  = chunk["Date"].dt.to_period("M").astype(str)
    chunk["weekday"] = chunk["Date"].dt.day_name()

    # ------------------------------------------------------------------
    # 5c. Optionally write raw chunk to compressed CSV
    #     Stored on Google Drive (Colab) or data/raw/ (local — gitignored).
    #     The web server NEVER reads this file.
    # ------------------------------------------------------------------
    if WRITE_RAW_GZ:
        raw_cols = [
            "Order_ID", "Customer_ID", "Gender", "Age", "Location", "Date",
            "Product_ID", "Product_Name", "Category", "Brand", "Material",
            "Size", "Color", "Price", "Quantity", "Discount",
            "Payment_Method", "Rating",
        ]
        chunk[raw_cols].to_csv(
            RAW_OUTPUT_GZ,
            mode="w" if write_header else "a",
            index=False,
            header=write_header,
            compression="gzip",
        )
        write_header = False

    # ------------------------------------------------------------------
    # 5d. Aggregate into running accumulators
    #     This is the key pattern: chunk is discarded after aggregation.
    #     Running totals survive across all 100 chunks.
    # ------------------------------------------------------------------

    # KPIs
    total_net_sales      += float(net_sales.sum())
    total_gross_sales    += float(gross_sales.sum())
    total_orders         += chunk_rows
    total_units          += int(quantities.sum())
    total_ratings_sum    += float(ratings.sum())
    total_ratings_count  += chunk_rows
    total_rows_generated += chunk_rows

    # Monthly
    for period, grp in chunk.groupby("Period"):
        if period not in monthly_agg:
            monthly_agg[period] = {"revenue": 0.0, "orders": 0, "units": 0}
        monthly_agg[period]["revenue"] += float(grp["Net_Sales"].sum())
        monthly_agg[period]["orders"]  += len(grp)
        monthly_agg[period]["units"]   += int(grp["Quantity"].sum())

    # Categories
    for cat, grp in chunk.groupby("Category"):
        if cat not in category_agg:
            category_agg[cat] = {"revenue": 0.0, "units": 0, "orders": 0,
                                  "ratings_sum": 0.0, "ratings_count": 0}
        category_agg[cat]["revenue"]       += float(grp["Net_Sales"].sum())
        category_agg[cat]["units"]         += int(grp["Quantity"].sum())
        category_agg[cat]["orders"]        += len(grp)
        category_agg[cat]["ratings_sum"]   += float(grp["Rating"].sum())
        category_agg[cat]["ratings_count"] += len(grp)

    # Payment methods
    for pm, grp in chunk.groupby("Payment_Method"):
        if pm not in payment_agg:
            payment_agg[pm] = {"revenue": 0.0, "orders": 0}
        payment_agg[pm]["revenue"] += float(grp["Net_Sales"].sum())
        payment_agg[pm]["orders"]  += len(grp)

    # Locations
    for loc, grp in chunk.groupby("Location"):
        if loc not in location_agg:
            location_agg[loc] = {"revenue": 0.0, "orders": 0, "units": 0,
                                  "customers": set()}
        location_agg[loc]["revenue"] += float(grp["Net_Sales"].sum())
        location_agg[loc]["orders"]  += len(grp)
        location_agg[loc]["units"]   += int(grp["Quantity"].sum())
        location_agg[loc]["customers"].update(grp["Customer_ID"].unique())

    # Weekdays
    for wd, grp in chunk.groupby("weekday"):
        if wd not in weekday_agg:
            weekday_agg[wd] = {"revenue": 0.0, "orders": 0}
        weekday_agg[wd]["revenue"] += float(grp["Net_Sales"].sum())
        weekday_agg[wd]["orders"]  += len(grp)

    # Products
    for pid, grp in chunk.groupby("Product_ID"):
        if pid not in product_agg:
            first = grp.iloc[0]
            product_agg[pid] = {
                "Product_ID":   pid,
                "Product_Name": first["Product_Name"],
                "Category":     first["Category"],
                "Brand":        first["Brand"],
                "units":        0, "revenue": 0.0, "orders": 0,
                "price_sum":    0.0, "price_count": 0,
                "discount_sum": 0.0,
                "rating_sum":   0.0, "rating_count": 0,
            }
        product_agg[pid]["units"]        += int(grp["Quantity"].sum())
        product_agg[pid]["revenue"]      += float(grp["Net_Sales"].sum())
        product_agg[pid]["orders"]       += len(grp)
        product_agg[pid]["price_sum"]    += float(grp["Price"].sum())
        product_agg[pid]["price_count"]  += len(grp)
        product_agg[pid]["discount_sum"] += float(grp["Discount"].sum())
        product_agg[pid]["rating_sum"]   += float(grp["Rating"].sum())
        product_agg[pid]["rating_count"] += len(grp)

    # Materials
    for mat, grp in chunk.groupby("Material"):
        if mat not in material_agg:
            material_agg[mat] = {"units": 0}
        material_agg[mat]["units"] += int(grp["Quantity"].sum())

    # Sizes
    for sz, grp in chunk.groupby("Size"):
        if sz not in size_agg:
            size_agg[sz] = {"units": 0}
        size_agg[sz]["units"] += int(grp["Quantity"].sum())

    # Customers
    for cid, grp in chunk.groupby("Customer_ID"):
        if cid not in customer_agg:
            first = grp.iloc[0]
            customer_agg[cid] = {
                "Customer_ID":  cid,
                "spend":        0.0,
                "items":        0,
                "orders":       0,
                "age_sum":      0.0, "age_count": 0,
                "rating_sum":   0.0, "rating_count": 0,
                "location":     first["Location"],
            }
        customer_agg[cid]["spend"]        += float(grp["Net_Sales"].sum())
        customer_agg[cid]["items"]        += int(grp["Quantity"].sum())
        customer_agg[cid]["orders"]       += len(grp)
        customer_agg[cid]["age_sum"]      += float(grp["Age"].sum())
        customer_agg[cid]["age_count"]    += len(grp)
        customer_agg[cid]["rating_sum"]   += float(grp["Rating"].sum())
        customer_agg[cid]["rating_count"] += len(grp)

    # ------------------------------------------------------------------
    # 5e. Release chunk from memory — the raw data is gone from RAM.
    #     Only the running aggregates above persist to the next iteration.
    # ------------------------------------------------------------------
    del chunk

    chunks_done += 1
    if chunks_done % 10 == 0 or chunk_start + chunk_rows >= TARGET_ROWS:
        pct     = (chunk_start + chunk_rows) / TARGET_ROWS * 100
        elapsed = time.perf_counter() - t0
        print(f"  [{pct:5.1f}%]  {chunk_start + chunk_rows:>10,} rows  |  "
              f"{elapsed:5.0f}s elapsed  |  {len(customer_agg):,} unique customers")

print(f"\n[2/7] Done — {total_rows_generated:,} rows aggregated in "
      f"{time.perf_counter() - t0:.1f}s")


# ===========================================================================
# SECTION 6: Build Customer Aggregation Table + K-Means Segmentation
# ===========================================================================
print("\n[3/7] Building customer aggregation table …")

customer_df = pd.DataFrame.from_dict(customer_agg, orient="index")
customer_df["age"]    = (customer_df["age_sum"]    / customer_df["age_count"]).round(1)
customer_df["rating"] = (customer_df["rating_sum"] / customer_df["rating_count"]).round(2)
customer_df = customer_df.drop(
    columns=["age_sum", "age_count", "rating_sum", "rating_count"]
)
customer_df["spend"] = customer_df["spend"].round(2)

# K-Means segmentation matching Notebook 3 parameters (k=3, seed=42).
# MiniBatchKMeans is used for memory efficiency on 500k customer rows.
# The cluster labels are written into the processed CSV — the web server
# reads them directly without retraining.
print("  Fitting MiniBatchKMeans (k=3, seed=42) on customer features …")
features = customer_df[["spend", "items", "orders"]].values
scaler   = StandardScaler()
scaled   = scaler.fit_transform(features)

kmeans = MiniBatchKMeans(
    n_clusters=3, random_state=RANDOM_SEED, batch_size=10_000, n_init=10
)
customer_df["cluster"] = kmeans.fit_predict(scaled)
customer_df = customer_df.sort_values("spend", ascending=False).reset_index(drop=True)
print(f"  {len(customer_df):,} unique customers segmented into 3 clusters.")


# ===========================================================================
# SECTION 7: Assemble dashboard_summary_10M.json
# ===========================================================================
print("\n[4/7] Building dashboard_summary_10M.json …")

monthly_list = sorted(
    [{"Period": p, "revenue": round(v["revenue"], 2),
      "orders": v["orders"], "units": v["units"]}
     for p, v in monthly_agg.items()],
    key=lambda x: x["Period"],
)

category_list = sorted(
    [{
        "Category":      cat,
        "revenue":       round(v["revenue"], 2),
        "units":         v["units"],
        "orders":        v["orders"],
        "average_rating": round(v["ratings_sum"] / v["ratings_count"], 2)
                          if v["ratings_count"] else 0,
     }
     for cat, v in category_agg.items()],
    key=lambda x: -x["revenue"],
)

payment_total = sum(v["revenue"] for v in payment_agg.values())
payment_list = sorted(
    [{
        "Payment_Method": pm,
        "revenue":        round(v["revenue"], 2),
        "orders":         v["orders"],
        "share":          round(v["revenue"] / payment_total * 100, 2)
                          if payment_total else 0,
     }
     for pm, v in payment_agg.items()],
    key=lambda x: -x["revenue"],
)

location_list = sorted(
    [{
        "Location":  loc,
        "revenue":   round(v["revenue"], 2),
        "orders":    v["orders"],
        "units":     v["units"],
        "customers": len(v["customers"]),
     }
     for loc, v in location_agg.items()],
    key=lambda x: -x["revenue"],
)

WEEKDAY_ORDER = ["Monday", "Tuesday", "Wednesday", "Thursday",
                 "Friday", "Saturday", "Sunday"]
weekday_list = [
    {"weekday": wd,
     "revenue": round(weekday_agg[wd]["revenue"], 2),
     "orders":  weekday_agg[wd]["orders"]}
    for wd in WEEKDAY_ORDER if wd in weekday_agg
]

product_list = sorted(
    [{
        "Product_ID":   v["Product_ID"],
        "Product_Name": v["Product_Name"],
        "Category":     v["Category"],
        "Brand":        v["Brand"],
        "units":        v["units"],
        "revenue":      round(v["revenue"], 2),
        "orders":       v["orders"],
        "price":        round(v["price_sum"]    / v["price_count"],  2)
                        if v["price_count"] else 0,
        "discount":     round(v["discount_sum"] / v["price_count"],  2)
                        if v["price_count"] else 0,
        "rating":       round(v["rating_sum"]   / v["rating_count"], 2)
                        if v["rating_count"] else 0,
     }
     for v in product_agg.values()],
    key=lambda x: -x["units"],
)[:30]

material_list = sorted(
    [{"Material": m, "units": v["units"]} for m, v in material_agg.items()],
    key=lambda x: -x["units"],
)
size_list = sorted(
    [{"Size": sz, "units": v["units"]} for sz, v in size_agg.items()],
    key=lambda x: -x["units"],
)

cluster_summary = (
    customer_df
    .groupby("cluster", as_index=False)
    .agg(customers=("Customer_ID", "count"),
         spend=("spend", "mean"),
         items=("items", "mean"),
         orders=("orders", "mean"))
    .sort_values("spend")
)
cluster_summary[["spend", "items", "orders"]] = (
    cluster_summary[["spend", "items", "orders"]].round(2)
)
cluster_summary_list = cluster_summary.to_dict(orient="records")

total_customers     = len(customer_df)
avg_order_value     = round(total_net_sales / total_orders, 2) if total_orders else 0
avg_rating          = round(total_ratings_sum / total_ratings_count, 2) \
                      if total_ratings_count else 0
repeat_customers    = int((customer_df["orders"] > 1).sum())
avg_cust_value      = round(float(customer_df["spend"].mean()), 2)
avg_orders_per_cust = round(float(customer_df["orders"].mean()), 2)
date_start_str      = DATE_START.isoformat()
date_end_str        = DATE_END.isoformat()

# Determine where processed files are coming from, for the meta note
if IN_COLAB:
    raw_storage_note = (
        "Raw 10M CSV stored on Google Drive at "
        "Ecommerce_Dress_Sales_10M/raw/dress_sales_10M.csv.gz. "
        "This file is NOT in the GitHub repository. "
        "The web backend reads ONLY these processed summary files."
    )
else:
    raw_storage_note = (
        "Raw 10M CSV stored locally at data/raw/dress_sales_10M.csv.gz "
        "(gitignored — not in GitHub repository). "
        "The web backend reads ONLY these processed summary files."
    )

summary = {
    "meta": {
        "generated_at":        pd.Timestamp.now().isoformat(),
        "generated_in":        "Google Colab" if IN_COLAB else "local machine",
        "total_rows_processed": total_rows_generated,
        "script":              "scripts/generate_10m_processed_data.py",
        "raw_storage":         "Google Drive — Ecommerce_Dress_Sales_10M/raw/"
                               if IN_COLAB else "data/raw/ (gitignored)",
        "note": raw_storage_note,
    },
    "kpis": {
        "revenue":             round(total_net_sales, 2),
        "orders":              total_orders,
        "customers":           total_customers,
        "units":               total_units,
        "average_order_value": avg_order_value,
        "average_rating":      avg_rating,
    },
    "date_range": {"start": date_start_str, "end": date_end_str},
    "monthly":          monthly_list,
    "categories":       category_list,
    "payments":         payment_list,
    "locations":        location_list,
    "weekday":          weekday_list,
    "materials":        material_list,
    "sizes":            size_list,
    "products_top30":   product_list,
    "cluster_summary":  cluster_summary_list,
    "customer_stats": {
        "customer_count":              total_customers,
        "repeat_customers":            repeat_customers,
        "average_customer_value":      avg_cust_value,
        "average_orders_per_customer": avg_orders_per_cust,
    },
    "methodology": {
        "rows":                   total_rows_generated,
        "columns":                18,
        "date_start":             date_start_str,
        "date_end":               date_end_str,
        "missing_values":         0,
        "duplicate_rows_removed": duplicates_removed,
        "revenue_definition":     "Price × Quantity × (1 − Discount / 100)",
        "segmentation": (
            "MiniBatchKMeans (k=3, seed=42) on standardised customer net spend, "
            "item count, and order count — consistent with Notebook 3 parameters."
        ),
        "prediction": (
            "Quantity prediction; 80/20 random split (seed 42), "
            "median numeric imputation, most-frequent categorical imputation, "
            "one-hot encoded categories (handle_unknown='ignore'), "
            "Linear Regression baseline and Random Forest (200 trees)."
        ),
    },
    "model_metrics": {
        "note": (
            "ML model metrics are pre-computed offline and stored here. "
            "The web backend reads these values — it does not retrain at runtime."
        ),
        "training_rows": int(total_rows_generated * 0.8),
        "testing_rows":  int(total_rows_generated * 0.2),
        "categories":    CATEGORIES,
        "brands":        BRANDS,
        "sizes":         SIZES,
        # Placeholder — replace with real values after offline ML training
        "metrics": [
            {"model": "Linear Regression", "mae": None, "rmse": None, "r2": None},
            {"model": "Random Forest",      "mae": None, "rmse": None, "r2": None},
        ],
        "selected_model": None,
        "selection_method": (
            "Website extension — not part of Notebook 2. "
            "Lowest combined rank across MAE, RMSE, and R²."
        ),
        "feature_importance": [],
    },
}

print(f"  Writing → {SUMMARY_JSON}")
with SUMMARY_JSON.open("w", encoding="utf-8") as f:
    json.dump(summary, f, indent=2, ensure_ascii=False)
print(f"  dashboard_summary_10M.json  ({SUMMARY_JSON.stat().st_size / 1024:.1f} KB)")


# ===========================================================================
# SECTION 8: Write customer_agg_10M.csv
# ===========================================================================
print(f"\n[5/7] Writing customer_agg_10M.csv → {CUSTOMER_AGG_CSV}")
customer_out = customer_df[[
    "Customer_ID", "spend", "items", "orders", "age", "rating", "location", "cluster"
]].copy()
customer_out["spend"] = customer_out["spend"].round(2)
customer_out.to_csv(CUSTOMER_AGG_CSV, index=False)
print(f"  customer_agg_10M.csv  "
      f"({CUSTOMER_AGG_CSV.stat().st_size / 1024 / 1024:.2f} MB, "
      f"{len(customer_out):,} rows)")


# ===========================================================================
# SECTION 9: Write prediction_sample_10M.csv (stratified scatter chart sample)
# ≤ 4,500 rows — only this file is used for the frontend scatter chart.
# The web server never receives or renders the full 500k customer table.
# ===========================================================================
print(f"\n[6/7] Writing prediction_sample_10M.csv → {PRED_SAMPLE_CSV}")
SAMPLE_PER_CLUSTER = 1_500    # max 1,500 per cluster → up to 4,500 total

sample_frames = []
for cluster_id in sorted(customer_df["cluster"].unique()):
    cdf = customer_df[customer_df["cluster"] == cluster_id]
    n   = min(SAMPLE_PER_CLUSTER, len(cdf))
    sample_frames.append(cdf.sample(n, random_state=RANDOM_SEED))

pred_sample = pd.concat(sample_frames, ignore_index=True)
pred_sample = pred_sample[["Customer_ID", "spend", "orders", "cluster"]]
pred_sample["spend"] = pred_sample["spend"].round(2)
pred_sample.to_csv(PRED_SAMPLE_CSV, index=False)
print(f"  prediction_sample_10M.csv  "
      f"({len(pred_sample):,} rows, "
      f"{PRED_SAMPLE_CSV.stat().st_size / 1024:.1f} KB)")


# ===========================================================================
# SECTION 10: Final Report
# ===========================================================================
elapsed_total = time.perf_counter() - t0
print("\n" + "=" * 68)
print("[7/7] PROCESSING COMPLETE")
print("=" * 68)
print(f"  Execution environment : {'Google Colab + Drive' if IN_COLAB else 'Local machine'}")
print(f"  Total time            : {elapsed_total:.1f}s")
print(f"  Rows processed        : {total_rows_generated:,}")
print(f"  Unique customers      : {total_customers:,}")
print(f"  Total net revenue     : ৳{total_net_sales:,.2f}")
print(f"  Total orders          : {total_orders:,}")
print(f"  Avg. order value      : ৳{avg_order_value:,.2f}")
print()
print("  Processed files (copy these 3 into project's data/processed/):")
print(f"    {SUMMARY_JSON}")
print(f"      → {SUMMARY_JSON.stat().st_size / 1024:.1f} KB  ← commit to git ✅")
print(f"    {CUSTOMER_AGG_CSV}")
print(f"      → {CUSTOMER_AGG_CSV.stat().st_size / 1024 / 1024:.2f} MB  ← commit to git ✅")
print(f"    {PRED_SAMPLE_CSV}")
print(f"      → {PRED_SAMPLE_CSV.stat().st_size / 1024:.1f} KB  ← commit to git ✅")
print()
if WRITE_RAW_GZ and RAW_OUTPUT_GZ.exists():
    sz = RAW_OUTPUT_GZ.stat().st_size / 1024 / 1024
    print(f"  Raw data file (DO NOT commit to git ❌):")
    print(f"    {RAW_OUTPUT_GZ}")
    print(f"      → {sz:.1f} MB  ← stored on Google Drive / gitignored locally")
    print()
print("  Next steps:")
if IN_COLAB:
    print("    1. From Colab, copy the 3 processed files into your local project:")
    print("         project_root/data/processed/dashboard_summary_10M.json")
    print("         project_root/data/processed/customer_agg_10M.csv")
    print("         project_root/data/processed/prediction_sample_10M.csv")
    print("    2. DO NOT copy dress_sales_10M.csv.gz — it stays on Drive only.")
else:
    print("    1. The 3 processed files are already in data/processed/.")
print("    3. Update backend/app/data.py to load from data/processed/.")
print("    4. Commit the 3 processed files and updated backend to git.")
print("=" * 68)
