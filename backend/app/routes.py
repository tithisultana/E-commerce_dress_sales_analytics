from fastapi import APIRouter, HTTPException, Query

from . import analytics
from .data import get_dataset
from .prediction import PredictionInput, model_evaluation_data, predict_quantity


router = APIRouter(prefix="/api")


@router.get("/health")
def health() -> dict:
    return {"status": "running"}


@router.get("/overview")
def overview() -> dict:
    return analytics.overview_data()


@router.get("/sales")
def sales() -> dict:
    result = analytics.monthly_sales_data()
    result["payment_methods"] = analytics.payment_distribution_data()
    return result


@router.get("/sales/monthly")
def monthly_sales() -> dict:
    return analytics.monthly_sales_data()


@router.get("/sales/categories")
def category_sales() -> list[dict]:
    return analytics.category_sales_data()


@router.get("/sales/payment-methods")
def payment_distribution() -> list[dict]:
    return analytics.payment_distribution_data()


@router.get("/sales/locations")
def location_sales() -> list[dict]:
    return analytics.location_sales_data()


@router.get("/products")
def products(limit: int = Query(default=30, ge=1, le=100)) -> dict:
    return analytics.top_products_data(limit)


@router.get("/products/top")
def top_products(limit: int = Query(default=10, ge=1, le=100)) -> dict:
    return analytics.top_products_data(limit)


@router.get("/customers")
@router.get("/customers/analysis")
def customers() -> dict:
    return analytics.customer_analysis_data()


@router.get("/segments")
@router.get("/customers/segments")
def customer_segments() -> dict:
    return analytics.customer_segments_data()


@router.get("/prediction/models")
def prediction_models() -> dict:
    return model_evaluation_data()


@router.post("/predict")
def predict(request: PredictionInput) -> dict:
    try:
        return predict_quantity(request)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/about")
def about() -> dict:
    from .analytics import methodology_data

    return methodology_data()