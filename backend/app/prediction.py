from functools import lru_cache
import numpy as np
import pandas as pd
from pydantic import BaseModel, ConfigDict, Field
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

from .data import DatasetError, get_dataset


FEATURES = ["Category", "Brand", "Size", "Price", "Discount", "Rating"]
CATEGORICAL_FEATURES = ["Category", "Brand", "Size"]
NUMERIC_FEATURES = ["Price", "Discount", "Rating"]


class PredictionInput(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid", str_strip_whitespace=True)

    category: str = Field(alias="Category", min_length=1)
    brand: str = Field(alias="Brand", min_length=1)
    size: str = Field(alias="Size", min_length=1)
    price: float = Field(alias="Price", gt=0, allow_inf_nan=False)
    discount: float = Field(alias="Discount", ge=0, le=100, allow_inf_nan=False)
    rating: float = Field(alias="Rating", ge=0, le=5, allow_inf_nan=False)


def _pipeline(estimator) -> Pipeline:
    preprocessing = ColumnTransformer(
        [
            ("numeric", "passthrough", NUMERIC_FEATURES),
            ("categorical", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL_FEATURES),
        ]
    )
    return Pipeline([("preprocessor", preprocessing), ("model", estimator)])


@lru_cache(maxsize=1)
def trained_models() -> tuple[dict, list[dict], str]:
    frame = get_dataset()
    if len(frame) < 5:
        raise DatasetError("At least five valid transactions are required to train prediction models")
    features = frame[FEATURES]
    target = frame["Quantity"]
    x_train, x_test, y_train, y_test = train_test_split(
        features, target, test_size=0.2, random_state=42
    )
    models = {
        "Linear Regression": _pipeline(LinearRegression()),
        "Random Forest": _pipeline(
            RandomForestRegressor(n_estimators=200, random_state=42, n_jobs=-1)
        ),
    }
    metrics = []
    raw_metrics = {}
    for name, model in models.items():
        model.fit(x_train, y_train)
        predicted = model.predict(x_test)
        raw_metrics[name] = {
            "mae": float(mean_absolute_error(y_test, predicted)),
            "rmse": float(np.sqrt(mean_squared_error(y_test, predicted))),
            "r2": float(r2_score(y_test, predicted)),
        }
        metrics.append({
            "model": name,
            "mae": round(raw_metrics[name]["mae"], 3),
            "rmse": round(raw_metrics[name]["rmse"], 3),
            "r2": round(raw_metrics[name]["r2"], 3),
        })

    rank_totals = {name: 0 for name in models}
    for metric, reverse in (("mae", False), ("rmse", False), ("r2", True)):
        ranked_models = sorted(models, key=lambda name: raw_metrics[name][metric], reverse=reverse)
        for rank, name in enumerate(ranked_models, start=1):
            rank_totals[name] += rank

    selected_model = min(
        models,
        key=lambda name: (
            rank_totals[name],
            raw_metrics[name]["rmse"],
            raw_metrics[name]["mae"],
            -raw_metrics[name]["r2"],
        ),
    )
    return models, metrics, selected_model


def model_evaluation_data() -> dict:
    frame = get_dataset()
    models, metrics, selected_model = trained_models()
    forest = models["Random Forest"].named_steps["model"]
    encoded_features = models["Random Forest"].named_steps["preprocessor"].get_feature_names_out()
    importance = pd.DataFrame({
        "feature": encoded_features,
        "importance": forest.feature_importances_,
    }).sort_values("importance", ascending=False).head(8)
    return {
        "metrics": metrics,
        "selected_model": selected_model,
        "selection_method": "Lowest combined rank across MAE, RMSE, and R²; ties are broken by RMSE, then MAE, then R².",
        "features": FEATURES,
        "target": "Quantity",
        "categories": sorted(frame["Category"].unique().tolist()),
        "brands": sorted(frame["Brand"].unique().tolist()),
        "sizes": sorted(frame["Size"].unique().tolist()),
        "feature_importance": importance.to_dict(orient="records"),
        "training_rows": int(len(frame) * 0.8),
        "testing_rows": int(len(frame) * 0.2),
    }


def predict_quantity(request: PredictionInput) -> dict:
    frame = get_dataset()
    for field, column in (("category", "Category"), ("brand", "Brand"), ("size", "Size")):
        value = getattr(request, field)
        if value not in frame[column].values:
            raise ValueError(f"Choose a {field} present in the dataset")
    models, metrics, selected_model = trained_models()
    row = pd.DataFrame([{
        "Category": request.category, "Brand": request.brand, "Size": request.size,
        "Price": request.price, "Discount": request.discount, "Rating": request.rating,
    }])
    quantity = max(0.0, float(models[selected_model].predict(row)[0]))
    selected_metrics = next(metric for metric in metrics if metric["model"] == selected_model)
    return {
        "predicted_quantity": round(quantity, 2),
        "selected_model": selected_model,
        "model": selected_model,
        "mae": selected_metrics["mae"],
        "rmse": selected_metrics["rmse"],
        "r2": selected_metrics["r2"],
    }