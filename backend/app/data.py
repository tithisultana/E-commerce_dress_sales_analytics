from functools import lru_cache
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_PATH = PROJECT_ROOT / "data" / "dress_sales.csv"
REQUIRED_COLUMNS = {
    "Order_ID", "Customer_ID", "Gender", "Age", "Location", "Date",
    "Product_ID", "Product_Name", "Category", "Brand", "Material", "Size",
    "Color", "Price", "Quantity", "Discount", "Payment_Method", "Rating",
}
NUMERIC_COLUMNS = ["Age", "Price", "Quantity", "Discount", "Rating"]


class DatasetError(RuntimeError):
    """Raised when the source CSV is unavailable or fails validation."""


@lru_cache(maxsize=1)
def get_dataset() -> pd.DataFrame:
    if not DATA_PATH.is_file():
        raise DatasetError(f"Dataset not found: {DATA_PATH}")
    try:
        frame = pd.read_csv(DATA_PATH)
    except (OSError, pd.errors.ParserError, UnicodeDecodeError) as exc:
        raise DatasetError(f"Could not read dataset: {exc}") from exc

    missing_columns = sorted(REQUIRED_COLUMNS - set(frame.columns))
    if missing_columns:
        raise DatasetError(f"Dataset is missing required columns: {', '.join(missing_columns)}")
    if frame.empty:
        raise DatasetError("Dataset contains no transaction rows")

    frame = frame.copy()
    for column in NUMERIC_COLUMNS:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame["Date"] = pd.to_datetime(frame["Date"], errors="coerce")

    invalid_counts = frame[list(REQUIRED_COLUMNS)].isna().sum()
    for column in REQUIRED_COLUMNS:
        if frame[column].dtype == object:
            blank_count = frame[column].astype("string").str.strip().eq("").sum()
            if blank_count:
                invalid_counts[column] += blank_count
    invalid_counts = invalid_counts[invalid_counts > 0]
    if not invalid_counts.empty:
        details = ", ".join(f"{column}: {count}" for column, count in invalid_counts.items())
        raise DatasetError(f"Dataset contains missing or invalid required values ({details})")
    if (frame["Price"] < 0).any() or (frame["Quantity"] < 0).any():
        raise DatasetError("Price and Quantity must not contain negative values")
    if not frame["Discount"].between(0, 100).all():
        raise DatasetError("Discount must be between 0 and 100")
    if not frame["Rating"].between(0, 5).all():
        raise DatasetError("Rating must be between 0 and 5")

    frame = frame.drop_duplicates().copy()
    frame["Gross_Sales"] = frame["Price"] * frame["Quantity"]
    frame["Discount_Amount"] = frame["Gross_Sales"] * frame["Discount"] / 100
    frame["Net_Sales"] = frame["Gross_Sales"] - frame["Discount_Amount"]
    frame["Period"] = frame["Date"].dt.to_period("M").astype(str)
    return frame