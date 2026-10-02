import pandas as pd
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

from .data import DATA_PATH, REQUIRED_COLUMNS, get_dataset


def records(frame: pd.DataFrame) -> list[dict]:
    normalized = frame.astype(object).where(pd.notna(frame), None)
    return normalized.to_dict(orient="records")


def overview_data() -> dict:
    frame = get_dataset()
    orders = int(frame["Order_ID"].nunique())
    categories = category_sales_data()
    return {
        "kpis": {
            "revenue": round(float(frame["Net_Sales"].sum()), 2),
            "orders": orders,
            "customers": int(frame["Customer_ID"].nunique()),
            "units": int(frame["Quantity"].sum()),
            "average_order_value": round(float(frame["Net_Sales"].sum() / orders), 2) if orders else 0,
            "average_rating": round(float(frame["Rating"].mean()), 2),
        },
        "date_range": {
            "start": frame["Date"].min().strftime("%Y-%m-%d"),
            "end": frame["Date"].max().strftime("%Y-%m-%d"),
        },
        "monthly_revenue": monthly_sales_data()["monthly"],
        "category_revenue": categories,
    }


def monthly_sales_data() -> dict:
    frame = get_dataset()
    monthly = frame.groupby("Period", as_index=False).agg(
        revenue=("Net_Sales", "sum"), orders=("Order_ID", "nunique"), units=("Quantity", "sum")
    )
    weekdays = frame.assign(weekday=frame["Date"].dt.day_name()).groupby("weekday", as_index=False).agg(
        revenue=("Net_Sales", "sum"), orders=("Order_ID", "nunique")
    )
    weekday_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    weekdays["weekday"] = pd.Categorical(weekdays["weekday"], weekday_order, ordered=True)
    return {"monthly": records(monthly), "weekday": records(weekdays.sort_values("weekday"))}


def category_sales_data() -> list[dict]:
    frame = get_dataset()
    categories = frame.groupby("Category", as_index=False).agg(
        revenue=("Net_Sales", "sum"), units=("Quantity", "sum"), orders=("Order_ID", "nunique")
    )
    return records(categories.sort_values("revenue", ascending=False))


def top_products_data(limit: int = 10) -> dict:
    frame = get_dataset()
    products = frame.groupby(["Product_ID", "Product_Name", "Category", "Brand"], as_index=False).agg(
        revenue=("Net_Sales", "sum"), units=("Quantity", "sum"), orders=("Order_ID", "nunique"),
        rating=("Rating", "mean"), price=("Price", "mean"), discount=("Discount", "mean")
    ).sort_values("revenue", ascending=False)
    materials = frame.groupby("Material", as_index=False).agg(units=("Quantity", "sum")).sort_values("units", ascending=False)
    sizes = frame.groupby("Size", as_index=False).agg(units=("Quantity", "sum"))
    return {"products": records(products.head(limit)), "materials": records(materials), "sizes": records(sizes)}


def payment_distribution_data() -> list[dict]:
    frame = get_dataset()
    payment = frame.groupby("Payment_Method", as_index=False).agg(
        revenue=("Net_Sales", "sum"), orders=("Order_ID", "nunique")
    ).sort_values("revenue", ascending=False)
    total = payment["revenue"].sum()
    payment["share"] = (payment["revenue"] / total * 100).round(2) if total else 0
    return records(payment)


def location_sales_data() -> list[dict]:
    frame = get_dataset()
    locations = frame.groupby("Location", as_index=False).agg(
        customers=("Customer_ID", "nunique"), revenue=("Net_Sales", "sum"),
        orders=("Order_ID", "nunique"), units=("Quantity", "sum")
    )
    return records(locations.sort_values("revenue", ascending=False))


def customer_analysis_data() -> dict:
    frame = get_dataset()
    customers = frame.groupby("Customer_ID", as_index=False).agg(
        spend=("Net_Sales", "sum"), items=("Quantity", "sum"), orders=("Order_ID", "nunique"),
        age=("Age", "mean"), rating=("Rating", "mean"), location=("Location", "first")
    ).sort_values("spend", ascending=False)
    age_bins = pd.cut(frame["Age"], bins=[0, 20, 30, 40, 50, 100], labels=["<20", "20-29", "30-39", "40-49", "50+"])
    age_groups = frame.assign(age_group=age_bins).groupby("age_group", observed=False, as_index=False).agg(
        orders=("Order_ID", "nunique"), revenue=("Net_Sales", "sum")
    )
    return {
        "top_customers": records(customers.head(12)),
        "customers": records(customers),
        "locations": location_sales_data(),
        "age_groups": records(age_groups),
        "repeat_customers": int((customers["orders"] > 1).sum()),
        "customer_count": int(len(customers)),
        "average_customer_value": round(float(customers["spend"].mean()), 2),
        "average_orders_per_customer": round(float(customers["orders"].mean()), 2),
    }


def customer_segments_data() -> dict:
    frame = get_dataset()
    customers = frame.groupby("Customer_ID", as_index=False).agg(
        spend=("Gross_Sales", "sum"), items=("Quantity", "sum"), orders=("Order_ID", "nunique")
    )
    feature_columns = ["spend", "orders", "items"]
    scaled = StandardScaler().fit_transform(customers[feature_columns])
    customers["cluster"] = KMeans(n_clusters=3, random_state=42, n_init=10).fit_predict(scaled)
    summary = customers.groupby("cluster", as_index=False).agg(
        customers=("Customer_ID", "count"), spend=("spend", "mean"), items=("items", "mean"), orders=("orders", "mean")
    ).sort_values("spend")
    labels = dict(zip(summary["cluster"], ["Emerging", "Regular", "High value"]))
    customers["segment"] = customers["cluster"].map(labels)
    summary["segment"] = summary["cluster"].map(labels)
    summary[["spend", "items", "orders"]] = summary[["spend", "items", "orders"]].round(2)
    sample = customers.sample(min(500, len(customers)), random_state=42)
    return {"summary": records(summary), "customers": records(sample)}


def methodology_data() -> dict:
    frame = get_dataset()
    source = pd.read_csv(DATA_PATH)
    return {
        "rows": int(len(frame)), "columns": int(len(REQUIRED_COLUMNS)),
        "date_start": frame["Date"].min().strftime("%Y-%m-%d"),
        "date_end": frame["Date"].max().strftime("%Y-%m-%d"),
        "missing_values": int(frame[list(REQUIRED_COLUMNS)].isna().sum().sum()),
        "duplicate_rows_removed": int(source.duplicated().sum()),
        "revenue_definition": "Price x Quantity x (1 - Discount / 100)",
        "segmentation": "K-Means (k=3) on standardized customer gross spend, items, and order count.",
        "prediction": "Quantity prediction; 80/20 random split (seed 42), one-hot encoded categories, Linear Regression baseline and Random Forest (200 trees).",
    }