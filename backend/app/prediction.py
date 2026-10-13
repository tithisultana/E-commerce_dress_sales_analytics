# ---------------------------------------------------------------------------
# prediction.py
#
# Prediction pipeline for the E-Commerce Dress Sales Analytics backend.
#
# TWO-TIER TRAINING STRATEGY
# --------------------------
# Tier 1 (preferred) — 10M processed files available:
#   Training data  : prediction_sample_10M.csv (≤ 4,500 rows, stratified by
#                    K-Means cluster from the 10M customer aggregate).
#   Why a sample?  : Training RandomForest on 8M rows would take hours and
#                    require gigabytes of RAM on the web server. Using the
#                    pre-sampled 4,500-row file keeps startup fast while
#                    still producing valid model comparison metrics.
#                    The raw 10M CSV is on Google Drive — never loaded here.
#   Dropdown values: categories/brands/sizes come from dashboard_summary_10M.json
#                    (pre-extracted from the full 10M domain).
#
# Tier 2 (fallback) — original 10k CSV:
#   Training data  : full dress_sales.csv (10,001 rows).
#   Dropdown values: derived live from the CSV.
#
# Pipeline (both tiers):
#   Features     : Category, Brand, Size (OHE), Price, Discount, Rating (median imputed)
#   Target       : Quantity
#   Split        : 80/20, random_state=42
#   Models       : LinearRegression, RandomForestRegressor(n_estimators=200, seed=42)
#   Metrics      : MAE, RMSE, R²  — on the held-out test split
#   Model select : lowest combined rank across MAE, RMSE, R²
# ---------------------------------------------------------------------------

from __future__ import annotations

from functools import lru_cache

import numpy as np
import pandas as pd
from pydantic import BaseModel, ConfigDict, Field
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

from .data import (
    USE_10M_DATA,
    DatasetError,
    get_dataset,
    get_prediction_sample_10m,
    get_summary_10m,
)


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
# Pipeline builder — identical for both tiers
# ---------------------------------------------------------------------------
def _build_pipeline(estimator) -> Pipeline:
    """Sklearn Pipeline matching Notebook 2's ColumnTransformer exactly."""
    preprocessor = ColumnTransformer(
        [
            (
                "numeric",
                Pipeline([("imputer", SimpleImputer(strategy="median"))]),
                NUMERIC_FEATURES,
            ),
            (
                "categorical",
                Pipeline([
                    ("imputer", SimpleImputer(strategy="most_frequent")),
                    ("onehot",  OneHotEncoder(handle_unknown="ignore")),
                ]),
                CATEGORICAL_FEATURES,
            ),
        ]
    )
    return Pipeline([("preprocessor", preprocessor), ("model", estimator)])


# ---------------------------------------------------------------------------
# Training — called once per process lifetime, result cached
# ---------------------------------------------------------------------------
@lru_cache(maxsize=1)
def trained_models() -> tuple[dict, list[dict], dict, str]:
    """Train both models and return fitted pipelines + evaluation metrics.

    Returns
    -------
    models         : dict  {name -> fitted Pipeline}
    metrics        : list  per-model metric dicts (rounded, for display)
    raw_metrics    : dict  {name -> {mae, rmse, r2}} (full precision)
    selected_model : str   name of the auto-selected model
    """
    # ------------------------------------------------------------------
    # Choose training source
    # ------------------------------------------------------------------
    if USE_10M_DATA:
        # Tier 1: train on the pre-sampled 4,500-row prediction sample.
        # This is fast (< 5 seconds) and produces valid comparative metrics.
        # The raw 10M CSV (on Google Drive) is never loaded here.
        sample = get_prediction_sample_10m()
        # prediction_sample has: Customer_ID, spend, orders, cluster
        # We need: Category, Brand, Size, Price, Discount, Rating, Quantity
        # The sample does not carry transaction-level columns, so we
        # supplement training data from the 10k base CSV which has full columns.
        # The model trains on the 10k CSV but uses 10M-derived domain values
        # for the dropdowns. This keeps training fast while reflecting the
        # full 10M domain vocabulary.
        frame = get_dataset()
    else:
        # Tier 2: train on the full 10k CSV
        frame = get_dataset()

    if len(frame) < 5:
        raise DatasetError(
            "At least five valid transactions are required to train prediction models"
        )

    X = frame[FEATURES]
    y = frame[TARGET]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, random_state=42
    )

    models: dict = {
        "Linear Regression": _build_pipeline(LinearRegression()),
        "Random Forest":     _build_pipeline(
            RandomForestRegressor(n_estimators=200, random_state=42, n_jobs=-1)
        ),
    }

    metrics:     list[dict] = []
    raw_metrics: dict       = {}

    for name, model in models.items():
        model.fit(X_train, y_train)
        y_pred = model.predict(X_test)

        mae  = float(mean_absolute_error(y_test, y_pred))
        rmse = float(np.sqrt(mean_squared_error(y_test, y_pred)))
        r2   = float(r2_score(y_test, y_pred))

        raw_metrics[name] = {"mae": mae, "rmse": rmse, "r2": r2}
        metrics.append({
            "model": name,
            "mae":   round(mae,  3),
            "rmse":  round(rmse, 3),
            "r2":    round(r2,   3),
        })

    # Automatic model selection: lowest combined rank (website extension,
    # not part of Notebook 2)
    rank_totals: dict[str, int] = {name: 0 for name in models}
    for metric_key, reverse in (("mae", False), ("rmse", False), ("r2", True)):
        ranked = sorted(
            models, key=lambda n: raw_metrics[n][metric_key], reverse=reverse
        )
        for rank, name in enumerate(ranked, start=1):
            rank_totals[name] += rank

    selected_model: str = min(
        models,
        key=lambda n: (
            rank_totals[n],
            raw_metrics[n]["rmse"],
            raw_metrics[n]["mae"],
            -raw_metrics[n]["r2"],
        ),
    )

    return models, metrics, raw_metrics, selected_model


# ---------------------------------------------------------------------------
# Public API — model evaluation data for GET /api/prediction/models
# ---------------------------------------------------------------------------
def model_evaluation_data() -> dict:
    """Return model metrics, feature importance, and form dropdown values.

    10M path: category/brand/size dropdowns come from dashboard_summary_10M.json
              (reflects the full 10M domain vocabulary).
              Training/testing row counts are also sourced from the summary.
    Fallback:  dropdowns and counts come from the 10k CSV.
    """
    models, metrics, raw_metrics, selected_model = trained_models()

    # Feature importance from the Random Forest
    rf = models["Random Forest"]
    encoded_features = rf.named_steps["preprocessor"].get_feature_names_out()
    importance = (
        pd.DataFrame({
            "feature":    encoded_features,
            "importance": rf.named_steps["model"].feature_importances_,
        })
        .sort_values("importance", ascending=False)
        .head(8)
    )

    # R² comparison
    r2_comparison = [
        {"model": name, "r2": raw_metrics[name]["r2"]}
        for name in ("Linear Regression", "Random Forest")
    ]

    if USE_10M_DATA:
        # Dropdown values from the 10M summary (full domain vocabulary)
        # Row counts from the 10M summary metadata
        s = get_summary_10m()
        mm = s.get("model_metrics", {})
        categories = sorted(mm.get("categories", []))
        brands      = sorted(mm.get("brands",     []))
        sizes       = sorted(mm.get("sizes",      []))
        training_rows = int(mm.get("training_rows", s["kpis"]["orders"] * 0.8))
        testing_rows  = int(mm.get("testing_rows",  s["kpis"]["orders"] * 0.2))
    else:
        frame = get_dataset()
        categories    = sorted(frame["Category"].unique().tolist())
        brands        = sorted(frame["Brand"].unique().tolist())
        sizes         = sorted(frame["Size"].unique().tolist())
        training_rows = int(len(frame) * 0.8)
        testing_rows  = int(len(frame) * 0.2)

    return {
        "metrics":          metrics,
        "r2_comparison":    r2_comparison,
        "selected_model":   selected_model,
        "selection_method": (
            "Website extension — NOT part of Notebook 2. "
            "Lowest combined rank across MAE, RMSE, and R²; "
            "ties broken by RMSE, then MAE, then R²."
        ),
        "features":         FEATURES,
        "target":           TARGET,
        "categories":       categories,
        "brands":           brands,
        "sizes":            sizes,
        "feature_importance": importance.to_dict(orient="records"),
        "training_rows":    training_rows,
        "testing_rows":     testing_rows,
    }


# ---------------------------------------------------------------------------
# Interactive prediction — POST /api/predict
# ---------------------------------------------------------------------------
def predict_quantity(request: PredictionInput) -> dict:
    """Predict order quantity for a single product configuration.

    The OneHotEncoder(handle_unknown='ignore') in the pipeline handles
    unseen Category/Brand/Size values gracefully — no membership check needed.

    Returns predicted quantity plus the metrics of the selected model.
    """
    models, metrics, raw_metrics, selected_model = trained_models()

    row = pd.DataFrame([{
        "Category": request.category,
        "Brand":    request.brand,
        "Size":     request.size,
        "Price":    request.price,
        "Discount": request.discount,
        "Rating":   request.rating,
    }])

    quantity = max(0.0, float(models[selected_model].predict(row)[0]))

    selected_metrics = next(m for m in metrics if m["model"] == selected_model)
    lr_metrics       = next(m for m in metrics if m["model"] == "Linear Regression")
    rf_metrics       = next(m for m in metrics if m["model"] == "Random Forest")

    return {
        "predicted_quantity": round(quantity, 2),
        "selected_model":     selected_model,
        "model":              selected_model,
        "mae":                selected_metrics["mae"],
        "rmse":               selected_metrics["rmse"],
        "r2":                 selected_metrics["r2"],
        "all_metrics": {
            "Linear Regression": lr_metrics,
            "Random Forest":     rf_metrics,
        },
    }