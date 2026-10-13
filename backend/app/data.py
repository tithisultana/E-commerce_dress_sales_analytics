# ---------------------------------------------------------------------------
# data.py
#
# Data loading layer for the E-Commerce Dress Sales Analytics backend.
#
# TWO-TIER DATA STRATEGY
# ----------------------
# Tier 1 — 10M processed summary files (preferred):
#   Generated offline in Google Colab from 10M synthetic transactions.
#   Raw 10M data stays on Google Drive — it is NEVER loaded here.
#   Files are small (< 20 MB total) and load in milliseconds.
#
#   data/processed/dashboard_summary_10M.json  — KPIs, trends, aggregates
#   data/processed/customer_agg_10M.csv        — one row per customer
#   data/processed/prediction_sample_10M.csv   — scatter chart sample
#
# Tier 2 — original 10k CSV (fallback):
#   Used when processed files are absent (e.g. fresh clone before Colab run).
#   data/dress_sales.csv  — 10,001-row base dataset
#
# The backend detects which tier is available and uses it automatically.
# ---------------------------------------------------------------------------

import json
from functools import lru_cache
from pathlib import Path

import pandas as pd


# ---------------------------------------------------------------------------
# Path constants
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Tier 2 — original small CSV (fallback)
DATA_PATH = PROJECT_ROOT / "data" / "dress_sales.csv"

# Tier 1 — 10M processed summary files
PROCESSED_DIR         = PROJECT_ROOT / "data" / "processed"
SUMMARY_10M_PATH      = PROCESSED_DIR / "dashboard_summary_10M.json"
CUSTOMER_AGG_10M_PATH = PROCESSED_DIR / "customer_agg_10M.csv"
PRED_SAMPLE_10M_PATH  = PROCESSED_DIR / "prediction_sample_10M.csv"

# Columns required in the original CSV
REQUIRED_COLUMNS = {
    "Order_ID", "Customer_ID", "Gender", "Age", "Location", "Date",
    "Product_ID", "Product_Name", "Category", "Brand", "Material", "Size",
    "Color", "Price", "Quantity", "Discount", "Payment_Method", "Rating",
}
NUMERIC_COLUMNS = ["Age", "Price", "Quantity", "Discount", "Rating"]


# ---------------------------------------------------------------------------
# Availability flags — checked once at import time
# ---------------------------------------------------------------------------
def _10m_available() -> bool:
    """Return True when ALL three 10M processed files exist."""
    return (
        SUMMARY_10M_PATH.is_file()
        and CUSTOMER_AGG_10M_PATH.is_file()
        and PRED_SAMPLE_10M_PATH.is_file()
    )


USE_10M_DATA: bool = _10m_available()


# ---------------------------------------------------------------------------
# Error type
# ---------------------------------------------------------------------------
class DatasetError(RuntimeError):
    """Raised when a required data source is unavailable or fails validation."""


# ===========================================================================
# TIER 1 LOADERS — 10M processed summary files
# Raw 10M CSV lives on Google Drive and is NEVER loaded by the backend.
# ===========================================================================

@lru_cache(maxsize=1)
def get_summary_10m() -> dict:
    """Load and cache dashboard_summary_10M.json.

    This file contains all pre-computed KPIs, monthly trends, category
    breakdowns, payment methods, locations, top products, cluster summaries,
    and methodology metadata — derived from 10M synthetic transactions.

    The raw 10M CSV that produced this file is stored on Google Drive and
    is NOT present in this repository. Only this lightweight summary is used
    by the web backend.
    """
    if not SUMMARY_10M_PATH.is_file():
        raise DatasetError(f"10M summary not found: {SUMMARY_10M_PATH}")
    try:
        return json.loads(SUMMARY_10M_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DatasetError(f"Could not read 10M summary: {exc}") from exc


@lru_cache(maxsize=1)
def get_customer_agg_10m() -> pd.DataFrame:
    """Load and cache customer_agg_10M.csv.

    One row per unique customer (500,000 customers aggregated from 10M rows).
    Columns: Customer_ID, spend, items, orders, age, rating, location, cluster.

    This file is the result of offline aggregation — the backend never
    re-aggregates from raw transaction data.
    """
    if not CUSTOMER_AGG_10M_PATH.is_file():
        raise DatasetError(f"10M customer aggregate not found: {CUSTOMER_AGG_10M_PATH}")
    try:
        df = pd.read_csv(CUSTOMER_AGG_10M_PATH)
        df["cluster"] = df["cluster"].astype(int)
        return df
    except (OSError, pd.errors.ParserError) as exc:
        raise DatasetError(f"Could not read customer aggregate: {exc}") from exc


@lru_cache(maxsize=1)
def get_prediction_sample_10m() -> pd.DataFrame:
    """Load and cache prediction_sample_10M.csv.

    A stratified sample of ≤ 4,500 customers (1,500 per K-Means cluster).
    Columns: Customer_ID, spend, orders, cluster.
    Used for the Customer Segmentation scatter chart and as the training
    dataset for prediction models when 10M files are active.

    Scatter chart rendering: only 4,500 points — browser never receives
    or renders the full 500k customer table.
    """
    if not PRED_SAMPLE_10M_PATH.is_file():
        raise DatasetError(f"10M prediction sample not found: {PRED_SAMPLE_10M_PATH}")
    try:
        df = pd.read_csv(PRED_SAMPLE_10M_PATH)
        df["cluster"] = df["cluster"].astype(int)
        return df
    except (OSError, pd.errors.ParserError) as exc:
        raise DatasetError(f"Could not read prediction sample: {exc}") from exc


# ===========================================================================
# TIER 2 LOADER — original 10k CSV (fallback)
# ===========================================================================

@lru_cache(maxsize=1)
def get_dataset() -> pd.DataFrame:
    """Load, validate, and cache the original 10k-row dress_sales.csv.

    Used as a fallback when 10M processed files are not yet available
    (e.g. on a fresh clone before running scripts/generate_10m_processed_data.py
    in Google Colab).

    This function is also used by prediction.py when building the interactive
    prediction form dropdowns from the CSV domain values.
    """
    if not DATA_PATH.is_file():
        raise DatasetError(f"Dataset not found: {DATA_PATH}")
    try:
        frame = pd.read_csv(DATA_PATH)
    except (OSError, pd.errors.ParserError, UnicodeDecodeError) as exc:
        raise DatasetError(f"Could not read dataset: {exc}") from exc

    missing_columns = sorted(REQUIRED_COLUMNS - set(frame.columns))
    if missing_columns:
        raise DatasetError(
            f"Dataset is missing required columns: {', '.join(missing_columns)}"
        )
    if frame.empty:
        raise DatasetError("Dataset contains no transaction rows")

    frame = frame.drop_duplicates().copy()
    frame["Date"] = pd.to_datetime(frame["Date"], errors="coerce")

    for column in NUMERIC_COLUMNS:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
        median = frame[column].median()
        if pd.notna(median):
            frame[column] = frame[column].fillna(median)

    for column in frame.select_dtypes(include=["object", "string"]).columns:
        if column not in REQUIRED_COLUMNS:
            continue
        frame[column] = frame[column].astype("string").str.strip()
        frame[column] = frame[column].replace("", pd.NA)
        mode = frame[column].mode(dropna=True)
        if not mode.empty:
            frame[column] = frame[column].fillna(mode.iloc[0])

    invalid_counts = frame[list(REQUIRED_COLUMNS)].isna().sum()
    for column in REQUIRED_COLUMNS:
        if frame[column].dtype == object:
            blank_count = (
                frame[column].astype("string").str.strip().eq("").sum()
            )
            if blank_count:
                invalid_counts[column] += blank_count
    invalid_counts = invalid_counts[invalid_counts > 0]
    if not invalid_counts.empty:
        details = ", ".join(
            f"{col}: {cnt}" for col, cnt in invalid_counts.items()
        )
        raise DatasetError(
            f"Dataset contains missing or invalid required values ({details})"
        )

    if (frame["Price"] < 0).any() or (frame["Quantity"] < 0).any():
        raise DatasetError("Price and Quantity must not contain negative values")
    if not frame["Discount"].between(0, 100).all():
        raise DatasetError("Discount must be between 0 and 100")
    if not frame["Rating"].between(0, 5).all():
        raise DatasetError("Rating must be between 0 and 5")

    frame["Gross_Sales"] = frame["Price"] * frame["Quantity"]
    frame["Discount_Amount"] = frame["Gross_Sales"] * (frame["Discount"] / 100)
    frame["Net_Sales"] = frame["Gross_Sales"] - frame["Discount_Amount"]
    frame["Year"] = frame["Date"].dt.year
    frame["Month"] = frame["Date"].dt.month
    frame["Month_Name"] = frame["Date"].dt.month_name()
    frame["Day_of_Week"] = frame["Date"].dt.day_name()
    frame["Period"] = frame["Date"].dt.to_period("M").astype(str)
    return frame