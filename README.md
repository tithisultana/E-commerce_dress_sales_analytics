# E-Commerce Dress Sales Analysis
## Business Analytics Dashboard

An enterprise-grade business analytics dashboard prototype for e-commerce dress sales intelligence. The platform delivers executive-level operational visibility, historical sales trajectories, catalog performance, buyer segmentation, and predictive demand forecasting.

> **Note on Dataset:** The dataset utilized across this project comprises 10,000,000 transaction records prepared and generated for academic demonstration and machine learning analysis. Core analytical decisions and machine learning algorithms were initially formulated on a base empirical dataset and subsequently scaled through a chunk-wise batch processing pipeline.

---

## 1. Project Overview

**E-Commerce Dress Sales Analysis** provides a complete business intelligence workflow designed to answer critical commercial questions for fashion retail operations:

- **Executive KPI Monitoring:** Track Net Revenue, completed order volume, customer counts, units fulfilled, Average Order Value (AOV), and customer review ratings.
- **Sales & Revenue Dynamics:** Longitudinal revenue trends across 48 months, seasonal surges, weekday ordering patterns, and payment gateway distributions.
- **Product & Catalog Performance:** Bestselling silhouettes, revenue contribution by category (Saree, Dress, Kurti, Salwar Kameez, etc.), brand dominance, and promotional discount depth.
- **Customer Account Intelligence:** Buyer lifetime value, repeat purchase rates, regional customer densities, and searchable customer ledger.
- **Behavioral Customer Segmentation:** Unsupervised K-Means clustering ($k=3$) grouping buyers into distinct spending and frequency tiers.
- **Predictive Demand Forecasting:** Supervised regression modeling (Linear Regression baseline and Random Forest Regressor) estimating product demand from category, brand, size, price, discount, and rating attributes.

---

## 2. Dataset & Scale

| Metric | Specification |
|---|---|
| **Total Transactions** | 10,000,000 orders |
| **Unique Customers** | 500,000 registered accounts |
| **Longitudinal Period** | 2023-01-01 to 2026-12-31 (4 years) |
| **Total Net Sales** | ৳62,632,086,622.45 |
| **Total Units Fulfilled** | 30,000,746 items |
| **Average Order Value** | ৳6,263.21 |
| **Raw Data Storage** | Stored externally in **Google Drive raw data storage** |
| **Web Serving Strategy** | Served strictly from pre-computed summary outputs (no raw file parsing) |

### Why the Website Does NOT Load the Raw 10M File Directly:
- **Eliminates RAM Exhaustion:** A 10M transaction CSV requires 1–2 GB of disk storage and inflates to 4–8 GB of memory when parsed into Pandas DataFrames. Loading this in a web server causes immediate Out-Of-Memory (OOM) crashes on standard instances.
- **Sub-Second Latency:** Parsing 10M records takes 30–120 seconds on server boot, and computing live aggregations on demand induces heavy latency. Serving pre-aggregated summaries allows API endpoints to respond in **under 50 milliseconds**.
- **Industry-Standard Decoupling:** In enterprise data warehouses (Snowflake, BigQuery, Databricks), transactional raw logs are stored in cloud data lakes, processed via scheduled batch ETL pipelines, and served to dashboards as aggregated data marts.

---

## 3. Data Processing Architecture

The project decouples offline big data processing from online real-time dashboard presentation:

```
┌────────────────────────────────────────────────────────┐
│                    Raw Data Layer                      │
│     data/dress_sales.csv (10,001 empirical rows)       │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│             Google Drive Raw Data Storage              │
│       Cloud storage archive: dress_sales_10M.csv.gz     │
│        (Keeps GitHub repository clean & lightweight)   │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│                 Chunk-wise Processing                  │
│       scripts/generate_10m_processed_data.py           │
│   (100k rows/chunk offline in Google Colab; peak <400MB)│
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│               Processed Analytics Outputs              │
│           data/processed/ (Committed to Git)           │
│   • dashboard_summary_10M.json                         │
│   • customer_agg_10M.csv                               │
│   • prediction_sample_10M.csv                          │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│                     FastAPI Backend                    │
│   (Loads lightweight summary files in milliseconds)    │
└───────────────────────────┬────────────────────────────┘
                            │ JSON API (<50ms response)
                            ▼
┌────────────────────────────────────────────────────────┐
│                     React Dashboard                    │
│   (Interactive charts, KPI cards, tables & forecasts)  │
└────────────────────────────────────────────────────────┘
```

---

## 4. Processed Output Files

The application serves from three optimized analytical artifacts in `data/processed/`:

1. **`dashboard_summary_10M.json` (~22 KB)**
   - **Role:** Powers high-level overview metrics, time series trends, and category breakdowns.
   - **Contents:** Executive KPIs (`revenue`, `orders`, `customers`, `units`, `aov`, `rating`), 48-month time series, category sales and unit volumes, payment gateway revenue shares, regional fulfillment densities, top 30 products, cluster centroid statistics, and methodology definitions.
2. **`customer_agg_10M.csv` (~21 MB, 500,000 rows)**
   - **Role:** Powers the Customer Analytics ledger and customer profile lookup table.
   - **Contents:** One row per buyer containing `Customer_ID`, `spend`, `items`, `orders`, `age`, `rating`, `location`, and `cluster` label (pre-computed via MiniBatchKMeans, $k=3$).
3. **`prediction_sample_10M.csv` (~100 KB, 4,500 rows)**
   - **Role:** Powers the interactive Customer Behavioral Scatter Plot.
   - **Contents:** Stratified sample of 1,500 customer accounts per cluster (4,500 rows total) carrying `Customer_ID`, `spend`, `orders`, and `cluster`. This prevents browser rendering freezes while maintaining visual cohort distributions.

---

## 5. Notebooks

The research and development lifecycle is documented across four Jupyter notebooks in `notebooks/`:

| Notebook | Purpose & Core Logic |
|---|---|
| **`01_E-Commerce_Dress_Sales_EDA.ipynb`** | **Exploratory Data Analysis:** Data cleaning, missing value handling, temporal seasonality extraction, Net Sales calculation (`Price × Quantity × (1 − Discount/100)`), category distributions, and baseline KPI formulation. |
| **`02_E-Commerce_Dress_Sales_Prediction.ipynb`** | **Predictive Demand Modeling:** Supervised regression pipeline using `SimpleImputer` (median for numeric, mode for categorical) and `OneHotEncoder(handle_unknown='ignore')`. 80/20 train/test holdout evaluation comparing Linear Regression against Random Forest Regressor (200 trees) on MAE, RMSE, and $R^2$. |
| **`03_E-Commerce_Customer_Segmentation.ipynb`** | **Customer Behavioral Segmentation:** Aggregating transactional history into customer-level RFM features (`Total_Spending`, `Total_Items`, `Total_Orders`), standardizing features via `StandardScaler`, and fitting K-Means ($k=3$) to identify distinct buyer segments. |
| **`04_10M_Data_Processing_Pipeline.ipynb`** | **Large-Scale Processing Pipeline:** Documents how the logic from Notebooks 01–03 is operationalized at 10M scale. Illustrates Google Drive cloud mounting, chunk-wise generation, running accumulators, output verification, and integration with the live web application. |

---

## 6. Backend Architecture

The backend is built with **FastAPI** (`backend/main.py` and `backend/app/`):

- **Data Access Layer (`backend/app/data.py`):** Automatically detects if the 10M processed summary files are available (`USE_10M_DATA = True`). Caches JSON and CSV summaries in memory using `@lru_cache`, while retaining full fallback support to the base CSV (`data/dress_sales.csv`).
- **Analytics Engine (`backend/app/analytics.py`):** Serves structured endpoints for KPIs, monthly trends, categorical performance, payment methods, geographic densities, customer account summaries, and methodology metadata directly from processed artifacts without live recalculation.
- **Machine Learning Layer (`backend/app/prediction.py`):** Trains and caches the scikit-learn preprocessing pipeline, Linear Regression baseline, and Random Forest Regressor (200 estimators). Evaluates holdout test metrics, identifies the optimal model, extracts Random Forest feature importances, and serves single-item real-time demand predictions via `POST /api/predict`.
- **API Router (`backend/app/routes.py`):** Exposes clean RESTful endpoints adhering to OpenAPI specifications (interactive documentation at `/docs`).

---

## 7. Frontend Dashboard

Built with **React**, **Vite**, **Recharts**, and **Lucide Icons** (`frontend/src/`):

- **Design System:** Deep navy / charcoal sidebar (`#0b1329`), soft off-white canvas (`#f8fafc`), emerald/teal accents (`#0d9488`), warm copper metric highlights (`#ea580c`), and clean elevated white cards with subtle shadows.
- **Dashboard Pages:**
  1. **Dashboard / Overview:** Executive KPI summary cards, monthly net revenue trajectory area chart, category revenue share, payment gateway donut mix, and regional delivery volumes.
  2. **Sales Analytics:** Interactive period filters (all time, 12 months, 6 months) and metric toggle (Revenue vs. Orders), category performance matrix, payment revenue, and territory density.
  3. **Product Analytics:** Top 10 bestselling products by units, revenue leaders, promotional discount depth analysis, and searchable product catalogue table with category filtering.
  4. **Customer Analytics:** Account base metrics, lifetime value, purchase frequency, district distribution, top account spenders, and paginated customer account ledger.
  5. **Customer Segmentation:** Segment cohort distribution donut, centroid statistics cards, and 4,500-point behavioral scatter plot mapping gross spend against order count.
  6. **Sales Prediction:** Interactive demand forecasting form, model benchmark comparison table, holdout test metrics (MAE, RMSE, $R^2$), and algorithm notes.
  7. **Methodology:** Complete 8-step data architecture workflow, storage layer explanation, dataset specifications table, evaluation metric definitions, and formula references.

---

## 8. How to Run

### Prerequisites
- Python 3.10+
- Node.js 18+ and npm

### 1. Run the Backend API

```bash
# Optional: create and activate a virtual environment
python -m venv .venv
# On Windows: .venv\Scripts\activate
# On Linux/macOS: source .venv/bin/activate

# Install Python requirements
pip install -r backend/requirements.txt

# Start the FastAPI server
uvicorn backend.main:app --host 0.0.0.0 --port 8000
```
API endpoints and Swagger documentation will be available at:
- API Base: `http://localhost:8000/api`
- Interactive Swagger Docs: `http://localhost:8000/docs`

### 2. Run the Frontend Dashboard

In a separate terminal:

```bash
cd frontend

# Install frontend dependencies
npm install

# Start the Vite development server
npm run dev -- --host 0.0.0.0
```
Open `http://localhost:5173` in your browser to access the dashboard.

---

## 9. Defense Note

> **Academic and Architecture Alignment:**
> The core analytical, segmentation, and machine learning logic was first researched, validated, and developed on the base empirical dataset in **Notebooks 01–03**.
> 
> To demonstrate modern big data software engineering and prevent production instability, the 10,000,000 transaction dataset is handled through a separate, decoupled chunk-wise processing pipeline documented in **Notebook 04** and implemented in `scripts/generate_10m_processed_data.py`.
> 
> The live web dashboard intentionally consumes the pre-computed summary outputs rather than parsing raw multi-gigabyte files at request time. This design mirrors production enterprise data marts, ensuring zero-latency dashboard rendering, robust scalability, and complete immunity to server memory exhaustion.
