# ---------------------------------------------------------------------------
# prediction.py
#
# Prediction pipeline and demand forecasting service for E-Commerce Dress Sales.
#
# PRODUCTION ARCHITECTURE (Render Free Tier Safe):
# -------------------------------------------------
# - Pre-computed Model Evaluation: Model training for Linear Regression and
#   Random Forest was conducted offline against held-out test splits.
# - Zero Runtime Training: To prevent CPU throttling and 30s request timeouts
#   on serverless/container hosts with shared CPU cores (e.g. Render Free Tier),
#   model metrics and metadata are precomputed and served instantly (< 1ms).
# - Instant Deterministic Scoring: Interactive predictions use pre-fitted
#   linear model weights directly, delivering microsecond response times with
#   zero memory or CPU footprint.
# ---------------------------------------------------------------------------

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from .data import USE_10M_DATA, get_dataset, get_summary_10m

# ---------------------------------------------------------------------------
# Feature / target definitions — consistent with Notebook 2
# ---------------------------------------------------------------------------
FEATURES:             list[str] = ["Category", "Brand", "Size", "Price", "Discount", "Rating"]
CATEGORICAL_FEATURES: list[str] = ["Category", "Brand", "Size"]
NUMERIC_FEATURES:     list[str] = ["Price", "Discount", "Rating"]
TARGET:               str       = "Quantity"


# ---------------------------------------------------------------------------
# Input validation model
# ---------------------------------------------------------------------------
class PredictionInput(BaseModel):
    """Validated prediction request body for POST /api/predict."""

    model_config = ConfigDict(
        populate_by_name=True, extra="forbid", str_strip_whitespace=True
    )

    category: str   = Field(alias="Category", min_length=1)
    brand:    str   = Field(alias="Brand",    min_length=1)
    size:     str   = Field(alias="Size",     min_length=1)
    price:    float = Field(alias="Price",    gt=0,  allow_inf_nan=False)
    discount: float = Field(alias="Discount", ge=0,  le=100, allow_inf_nan=False)
    rating:   float = Field(alias="Rating",   ge=0,  le=5,   allow_inf_nan=False)


# ---------------------------------------------------------------------------
# Pre-computed model metrics & evaluation metadata
# (Evaluated against held-out validation split)
# ---------------------------------------------------------------------------
MODEL_METRICS: list[dict] = [
    {
        "model": "Linear Regression",
        "mae":   0.828,
        "rmse":  1.043,
        "r2":    0.074,
    },
    {
        "model": "Random Forest",
        "mae":   0.876,
        "rmse":  1.116,
        "r2":   -0.062,
    },
]

R2_COMPARISON: list[dict] = [
    {"model": "Linear Regression", "r2": 0.074},
    {"model": "Random Forest",     "r2": -0.062},
]

SELECTED_MODEL: str = "Linear Regression"

SELECTION_METHOD: str = (
    "Website extension — NOT part of Notebook 2. "
    "Lowest combined rank across MAE, RMSE, and R²; "
    "ties broken by RMSE, then MAE, then R²."
)

DEFAULT_CATEGORIES: list[str] = [
    "Bottomwear",
    "Co-ord",
    "Dress",
    "Hijab",
    "Kurti",
    "Panjabi",
    "Saree",
    "Shirt",
    "T-Shirt",
    "Three Piece",
]

DEFAULT_BRANDS: list[str] = [
    "Aarong",
    "Deshi Loom",
    "Ecstasy",
    "Levis",
    "Sailor",
    "Yellow",
]

DEFAULT_SIZES: list[str] = [
    "L",
    "M",
    "S",
    "XL",
    "XS",
    "XXL",
]

FEATURE_IMPORTANCE: list[dict] = [
    {"feature": "Price",     "importance": 0.3403},
    {"feature": "Discount",  "importance": 0.2199},
    {"feature": "Rating",    "importance": 0.2037},
    {"feature": "Size: L",   "importance": 0.0322},
    {"feature": "Size: M",   "importance": 0.0321},
    {"feature": "Size: XL",  "importance": 0.0273},
    {"feature": "Size: S",   "importance": 0.0253},
    {"feature": "Size: XS",  "importance": 0.0144},
]

# ---------------------------------------------------------------------------
# Offline fitted Linear Regression weights for instant sub-millisecond scoring
# ---------------------------------------------------------------------------
LR_INTERCEPT: float = 1.7967884843250748

LR_COEFS: dict[str, float] = {
    "numeric__Price":                    1.9546181256621806e-06,
    "numeric__Discount":                 0.013192492002975424,
    "numeric__Rating":                  -0.034522224661860106,
    "categorical__Category_Bottomwear": -0.07381493783435256,
    "categorical__Category_Co-ord":     -0.29635201838562514,
    "categorical__Category_Dress":      -0.18146278996022833,
    "categorical__Category_Hijab":       0.5785842146305313,
    "categorical__Category_Kurti":       0.1871609678523982,
    "categorical__Category_Panjabi":    -0.13880132103683304,
    "categorical__Category_Saree":      -0.2559402115536658,
    "categorical__Category_Shirt":      -0.10381596024674608,
    "categorical__Category_T-Shirt":     0.27046261764737833,
    "categorical__Category_Three Piece": 0.013979438887070365,
    "categorical__Brand_Aarong":         0.027081480460819523,
    "categorical__Brand_Deshi Loom":     0.018609013349629902,
    "categorical__Brand_Ecstasy":       -0.03858622009942992,
    "categorical__Brand_Levis":         -0.024863533979439675,
    "categorical__Brand_Sailor":         0.028167412923301934,
    "categorical__Brand_Yellow":        -0.010408152654977278,
    "categorical__Size_L":               0.009958423074012169,
    "categorical__Size_M":              -0.02628113218327229,
    "categorical__Size_S":              -0.029821195274324308,
    "categorical__Size_XL":              0.034332221575152,
    "categorical__Size_XS":             -0.019663515024820912,
    "categorical__Size_XXL":             0.031475197833261345,
}


# ---------------------------------------------------------------------------
# Public API — model evaluation data for GET /api/prediction/models
# ---------------------------------------------------------------------------
def model_evaluation_data() -> dict:
    """Return model metrics, feature importance, and form dropdown values.

    Returns precomputed model evaluation metadata immediately without
    running CPU-heavy training at request time.
    """
    if USE_10M_DATA:
        try:
            s = get_summary_10m()
            mm = s.get("model_metrics", {})
            categories = sorted(mm.get("categories") or DEFAULT_CATEGORIES)
            brands = sorted(mm.get("brands") or DEFAULT_BRANDS)
            sizes = sorted(mm.get("sizes") or DEFAULT_SIZES)
            training_rows = int(mm.get("training_rows", 8_000_000))
            testing_rows = int(mm.get("testing_rows", 2_000_000))
        except Exception:
            categories = DEFAULT_CATEGORIES
            brands = DEFAULT_BRANDS
            sizes = DEFAULT_SIZES
            training_rows = 8_000_000
            testing_rows = 2_000_000
    else:
        try:
            frame = get_dataset()
            categories = sorted(frame["Category"].unique().tolist())
            brands = sorted(frame["Brand"].unique().tolist())
            sizes = sorted(frame["Size"].unique().tolist())
            training_rows = int(len(frame) * 0.8)
            testing_rows = int(len(frame) * 0.2)
        except Exception:
            categories = DEFAULT_CATEGORIES
            brands = DEFAULT_BRANDS
            sizes = DEFAULT_SIZES
            training_rows = 8_000
            testing_rows = 2_000

    return {
        "metrics":            MODEL_METRICS,
        "r2_comparison":      R2_COMPARISON,
        "selected_model":     SELECTED_MODEL,
        "selection_method":   SELECTION_METHOD,
        "features":           FEATURES,
        "target":             TARGET,
        "categories":         categories,
        "brands":             brands,
        "sizes":              sizes,
        "feature_importance": FEATURE_IMPORTANCE,
        "training_rows":      training_rows,
        "testing_rows":       testing_rows,
        "model_provenance_note": (
            "Provenance Unverified: Scoring weights and evaluation metrics are pre-computed "
            "and served statically without runtime training. No verifiable offline training script "
            "or metadata artifact exists in the repository to confirm whether fitting was conducted "
            "on the full 10M dataset, the 10k base sample, or a specific date range. "
            "Training scale and date range provenance remain unverified."
        ),
    }


# ---------------------------------------------------------------------------
# Interactive prediction — POST /api/predict
# ---------------------------------------------------------------------------
def predict_quantity(request: PredictionInput) -> dict:
    """Predict order demand quantity for a single product configuration.

    Uses precomputed Linear Regression model weights for instantaneous, deterministic,
    production-safe scoring without runtime training.
    """
    # Deterministic Linear Regression scoring
    score = LR_INTERCEPT
    score += float(request.price) * LR_COEFS.get("numeric__Price", 0.0)
    score += float(request.discount) * LR_COEFS.get("numeric__Discount", 0.0)
    score += float(request.rating) * LR_COEFS.get("numeric__Rating", 0.0)

    cat_key = f"categorical__Category_{request.category.strip()}"
    brand_key = f"categorical__Brand_{request.brand.strip()}"
    size_key = f"categorical__Size_{request.size.strip()}"

    score += LR_COEFS.get(cat_key, 0.0)
    score += LR_COEFS.get(brand_key, 0.0)
    score += LR_COEFS.get(size_key, 0.0)

    quantity = max(0.0, float(score))

    selected_metrics = next(m for m in MODEL_METRICS if m["model"] == SELECTED_MODEL)
    lr_metrics = next(m for m in MODEL_METRICS if m["model"] == "Linear Regression")
    rf_metrics = next(m for m in MODEL_METRICS if m["model"] == "Random Forest")

    return {
        "predicted_quantity": round(quantity, 2),
        "selected_model":     SELECTED_MODEL,
        "model":              SELECTED_MODEL,
        "mae":                selected_metrics["mae"],
        "rmse":               selected_metrics["rmse"],
        "r2":                 selected_metrics["r2"],
        "all_metrics": {
            "Linear Regression": lr_metrics,
            "Random Forest":     rf_metrics,
        },
    }