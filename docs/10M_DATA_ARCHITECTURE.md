# 10M Data Architecture
## E-Commerce Dress Sales Analytics — Real-Company-Style Dashboard Prototype

---

## 1. Project Overview

This project is a **real-company-style business analytics dashboard prototype** built on
10 million synthetic e-commerce dress sales transactions. It demonstrates the kind of
data architecture that production analytics dashboards use in actual companies — where
raw transactional data is **never** loaded directly into a web server.

The dashboard is designed as if deployed for a real fashion e-commerce company in
Bangladesh (selling dresses, T-shirts, co-ord sets, shirts, etc.) that needs to track
sales performance, customer behaviour, and product trends.

---

## 2. Storage Strategy — GitHub vs Google Drive

> [!IMPORTANT]
> **The 10M raw dataset is stored on Google Drive — NOT in GitHub.**
> GitHub stores code and small processed analytics outputs only.

| What | Where | Why |
|---|---|---|
| Source code | GitHub repository | Version-controlled, collaborative |
| Base dataset (10k rows) | `data/dress_sales.csv` in GitHub | Small enough to commit |
| **Raw 10M CSV (.csv.gz)** | **Google Drive** | ~680 MB — too large for GitHub |
| Processed summaries (3 files) | `data/processed/` in GitHub | Small outputs — a few MB total |
| ETL script | `scripts/` in GitHub | Version-controlled, re-runnable |

### Google Drive folder structure

```
Google Drive /
└── Ecommerce_Dress_Sales_10M /
    ├── raw/
    │   └── dress_sales_10M.csv.gz        ← ~680 MB · NOT in GitHub
    └── processed/
        ├── dashboard_summary_10M.json    ← ~50 KB  · copy → data/processed/ ✅
        ├── customer_agg_10M.csv          ← ~12 MB  · copy → data/processed/ ✅
        └── prediction_sample_10M.csv     ← ~150 KB · copy → data/processed/ ✅
```

### GitHub repository structure (relevant paths)

```
E-commerce_dress_sales_analytics/
├── data/
│   ├── dress_sales.csv               ← original 10k-row base dataset (committed)
│   ├── raw/                          ← gitignored — empty in GitHub
│   └── processed/                    ← committed — contains the 3 summary files
│       ├── dashboard_summary_10M.json
│       ├── customer_agg_10M.csv
│       └── prediction_sample_10M.csv
├── scripts/
│   └── generate_10m_processed_data.py  ← ETL script (committed)
├── docs/
│   └── 10M_DATA_ARCHITECTURE.md        ← this file (committed)
└── backend/
    └── app/
        ├── data.py        ← loads processed files (not the raw CSV)
        ├── analytics.py   ← serves pre-computed summaries
        ├── prediction.py  ← serves pre-trained model metrics
        └── routes.py      ← REST API endpoints
```

---

## 3. How Data Enters a Real Company's Analytics System

In a real company, sales data originates from multiple sources and flows through a
pipeline before reaching a dashboard:

```
┌─────────────────────────────────────────────────────────────────┐
│                    REAL-WORLD DATA SOURCES                       │
│                                                                  │
│  Website Order DB  │  POS System  │  Excel/CSV Exports          │
│  (PostgreSQL/MySQL)│  (in-store)  │  (manual uploads)           │
│                    │              │                              │
│  E-commerce APIs   │  Customer DB │  ERP / Accounting           │
│  (Shopify, Daraz,  │  / CRM       │  System                     │
│   WooCommerce)     │              │                              │
└────────────┬────────────────────────────────────────────────────┘
             │
             ▼
┌────────────────────────────────────────────┐
│       ETL / DATA PIPELINE                   │
│  (scheduled: hourly / daily / on-event)     │
│                                             │
│  • Extract raw transactions                 │
│  • Clean, validate, deduplicate             │
│  • Compute KPIs, aggregates, segments       │
│  • Write small summary files or to DWH      │
└────────────┬────────────────────────────────┘
             │
             ▼
┌────────────────────────────────────────────┐
│   DASHBOARD API (FastAPI / Node / Django)   │
│                                             │
│  Reads ONLY processed summaries.            │
│  Never touches raw transactional data.      │
└────────────┬────────────────────────────────┘
             │  JSON (milliseconds)
             ▼
┌────────────────────────────────────────────┐
│   REACT DASHBOARD (browser)                 │
│   Charts, KPI cards, tables, predictions   │
└────────────────────────────────────────────┘
```

**Real-company tooling for this pipeline:**
- Apache Spark / PySpark — for very large datasets
- dbt (data build tool) — SQL-based transformations
- Apache Airflow / Prefect / Dagster — scheduling ETL jobs
- AWS S3 / Google Cloud Storage / Azure Blob — external storage for raw files
- BigQuery / Snowflake / Redshift — data warehouse

---

## 4. How This Academic Project Mirrors That Pattern

```
┌──────────────────────────────────────────────────────────────┐
│   ACADEMIC EQUIVALENT DATA SOURCES                            │
│                                                               │
│   data/dress_sales.csv  (10,001-row real base dataset)        │
│   Expanded synthetically to 10,000,000 rows by the script     │
└────────────┬─────────────────────────────────────────────────┘
             │
             ▼
┌──────────────────────────────────────────────────────────────┐
│   scripts/generate_10m_processed_data.py                      │
│   (run once in Google Colab — mirrors the ETL pipeline)       │
│                                                               │
│   • Auto-detects Google Colab environment                     │
│   • Mounts Google Drive automatically                         │
│   • Generates 10M rows in 100k-row chunks (RAM-safe)          │
│   • Aggregates KPIs, monthly, category, payment, location     │
│   • Runs MiniBatchKMeans segmentation on customer table        │
│   • Saves raw 10M gz → Google Drive (NOT GitHub)             │
│   • Saves 3 processed summary files → Google Drive           │
└────────────┬─────────────────────────────────────────────────┘
             │
             ▼
┌──────────────────────────────────────────────────────────────┐
│   Google Drive: Ecommerce_Dress_Sales_10M/                    │
│   (external storage — not in GitHub)                          │
│                                                               │
│   raw/dress_sales_10M.csv.gz      ~680 MB  ← stays on Drive  │
│   processed/dashboard_summary_10M.json     ← copy to project │
│   processed/customer_agg_10M.csv           ← copy to project │
│   processed/prediction_sample_10M.csv      ← copy to project │
└────────────┬─────────────────────────────────────────────────┘
             │  Manual copy of 3 processed files only
             ▼
┌──────────────────────────────────────────────────────────────┐
│   data/processed/  (committed to GitHub)                      │
│                                                               │
│   dashboard_summary_10M.json  ~50 KB                          │
│     KPIs, monthly trends, categories, payments,               │
│     locations, weekday patterns, top products,                │
│     cluster summary, methodology, model metadata              │
│                                                               │
│   customer_agg_10M.csv  ~12 MB                                │
│     One row per unique customer:                              │
│     Customer_ID, spend, items, orders, age,                   │
│     rating, location, cluster                                 │
│                                                               │
│   prediction_sample_10M.csv  ~150 KB                          │
│     ≤4,500 stratified-sampled rows for scatter chart          │
└────────────┬─────────────────────────────────────────────────┘
             │
             ▼
┌──────────────────────────────────────────────────────────────┐
│   backend/app/ (FastAPI — reads summaries ONLY)               │
│                                                               │
│   data.py        → loaders for the 3 processed files         │
│   analytics.py   → serves pre-computed summaries              │
│   prediction.py  → serves pre-trained model metrics           │
│   routes.py      → REST API endpoints                         │
└────────────┬─────────────────────────────────────────────────┘
             │  JSON responses (milliseconds per request)
             ▼
┌──────────────────────────────────────────────────────────────┐
│   frontend/src/ (React + Recharts)                            │
│   Dashboard: KPI cards, charts, customer table, prediction    │
└──────────────────────────────────────────────────────────────┘
```

---

## 5. Why Raw 10M Data Cannot Be Loaded on the Web Server

| Problem | What happens if the raw 10M CSV is loaded at request time |
|---|---|
| **Memory (RAM)** | A 10M-row CSV is ~800 MB–2 GB in RAM. Most cloud instances have 512 MB–2 GB. Server crashes immediately on startup. |
| **Startup time** | Parsing 10M rows takes 30–120 seconds. The API is completely unreachable during this time. |
| **ML training** | Training a Random Forest on 8M rows takes hours on a web server CPU. Dashboard would never load. |
| **Response size** | Sending all customer records to the browser as JSON would freeze and crash the browser tab. |
| **Scalability** | Multiple concurrent users = multiple in-memory copies of the dataset. RAM multiplies linearly. |
| **Cost** | Larger RAM cloud instances cost 3–10× more per month. |

**Solution used in this project:** Pre-compute everything offline in Google Colab.
Serve only lightweight summary files (totalling ~13 MB).
Dashboard response time: **< 200 ms per request**.

---

## 6. Why Google Drive for Raw Data?

| Option | Size limit | Cost | Suitable for raw 10M file? |
|---|---|---|---|
| GitHub repository | 100 MB per file (hard limit) | Free | ❌ File is ~680 MB |
| GitHub LFS | 2 GB with paid plan | Paid | ❌ Adds complexity, cost |
| **Google Drive** | 15 GB free | Free | ✅ Perfect for this use case |
| AWS S3 / GCS | Unlimited | Paid | ✅ Used in real companies |
| Local machine only | Limited by disk | Free | ⚠️ Not shareable with team |

Google Drive is the right choice for this academic project:
- Free, widely accessible, supports large files
- Google Colab integrates natively (one-line mount)
- Team members can share the Drive folder without needing GitHub LFS

---

## 7. Running the Data Generation Script

### Recommended: Google Colab

```python
# In a Colab notebook cell:

# Step 1: Clone the repository
!git clone https://github.com/tithisultana/E-commerce_dress_sales_analytics.git
%cd E-commerce_dress_sales_analytics

# Step 2: Install dependencies
!pip install pandas numpy scikit-learn

# Step 3: Run the script (Drive is mounted automatically)
!python scripts/generate_10m_processed_data.py
```

The script will:
1. Auto-detect Colab and mount Google Drive
2. Look for `dress_sales.csv` in `/content/E-commerce_dress_sales_analytics/data/`
3. Write raw file to `/content/drive/MyDrive/Ecommerce_Dress_Sales_10M/raw/`
4. Write processed files to `/content/drive/MyDrive/Ecommerce_Dress_Sales_10M/processed/`

```python
# Step 4 (after script finishes): Copy processed files into the project
import shutil
DRIVE = "/content/drive/MyDrive/Ecommerce_Dress_Sales_10M/processed"
DEST  = "/content/E-commerce_dress_sales_analytics/data/processed"

for f in ["dashboard_summary_10M.json", "customer_agg_10M.csv", "prediction_sample_10M.csv"]:
    shutil.copy(f"{DRIVE}/{f}", f"{DEST}/{f}")
    print(f"Copied: {f}")
```

### Local Fallback (for development without Colab)

```bash
# From the project root
pip install pandas numpy scikit-learn

python scripts/generate_10m_processed_data.py
```

Raw output → `data/raw/dress_sales_10M.csv.gz` (gitignored locally)
Processed → `data/processed/` (auto-written, ready to commit)

---

## 8. Chunk-Wise Processing — Why It Matters

The generation script processes data in **chunks of 100,000 rows**:

```python
# Key design pattern — chunk is generated, aggregated, then deleted:
for chunk_start in range(0, 10_000_000, 100_000):
    chunk = generate_chunk(rows=100_000)   # ~300 MB in RAM
    aggregate_into_running_totals(chunk)   # update accumulators
    del chunk                               # release 300 MB immediately
    # Only running totals survive to the next iteration
```

This means:
- Peak RAM ≈ **300–400 MB per chunk** (not 10+ GB for the full dataset)
- Runs on a Colab free tier (12 GB RAM) with headroom to spare
- Running aggregates (sums, counts, groupby totals) are maintained across all 100 chunks
- The final processed files are tiny — the web server only ever reads those

---

## 9. Scalability Notes

This architecture scales naturally to any data size:

| Scenario | What to change |
|---|---|
| More data (100M rows) | `TARGET_ROWS = 100_000_000` — chunk logic handles it automatically |
| Faster processing | Replace pandas chunks with Apache Spark |
| Automated daily refresh | Schedule the script as a cron job or Airflow DAG |
| Multiple data sources | Add more input paths/readers to the script |
| Cloud deployment | Write processed files to S3/GCS; backend reads from there |

---

## 10. File Responsibilities Summary

| File / Directory | In GitHub? | Storage | Purpose |
|---|---|---|---|
| `data/dress_sales.csv` | ✅ Yes | GitHub | Original 10,001-row base dataset |
| `data/raw/` | ❌ Gitignored | Local only | Local raw file fallback (never committed) |
| **Google Drive raw/** | ❌ Not GitHub | **Google Drive** | **Raw 10M CSV — primary external storage** |
| `data/processed/dashboard_summary_10M.json` | ✅ Yes | GitHub | Pre-computed KPIs, trends, summaries |
| `data/processed/customer_agg_10M.csv` | ✅ Yes | GitHub | One row per customer + cluster label |
| `data/processed/prediction_sample_10M.csv` | ✅ Yes | GitHub | Scatter chart sample (≤4,500 rows) |
| `scripts/generate_10m_processed_data.py` | ✅ Yes | GitHub | ETL script — run in Colab |
| `docs/10M_DATA_ARCHITECTURE.md` | ✅ Yes | GitHub | This document |
| `backend/app/data.py` | ✅ Yes | GitHub | Loads processed files (not raw CSV) |

---

## 11. Data Dictionary — Processed Files

### `dashboard_summary_10M.json`

```json
{
  "meta":       { "generated_at", "generated_in", "total_rows_processed",
                  "raw_storage", "note" },
  "kpis":       { "revenue", "orders", "customers", "units",
                  "average_order_value", "average_rating" },
  "date_range": { "start", "end" },
  "monthly":    [ { "Period", "revenue", "orders", "units" }, ... ],
  "categories": [ { "Category", "revenue", "units", "orders",
                     "average_rating" }, ... ],
  "payments":   [ { "Payment_Method", "revenue", "orders", "share" }, ... ],
  "locations":  [ { "Location", "revenue", "orders", "units",
                     "customers" }, ... ],
  "weekday":    [ { "weekday", "revenue", "orders" }, ... ],
  "materials":  [ { "Material", "units" }, ... ],
  "sizes":      [ { "Size", "units" }, ... ],
  "products_top30": [ { "Product_ID", "Product_Name", "Category", "Brand",
                         "units", "revenue", "orders", "price",
                         "discount", "rating" }, ... ],
  "cluster_summary":  [ { "cluster", "customers", "spend", "items",
                           "orders" }, ... ],
  "customer_stats":   { "customer_count", "repeat_customers",
                         "average_customer_value",
                         "average_orders_per_customer" },
  "methodology":      { "rows", "columns", "date_start", "date_end",
                         "missing_values", "duplicate_rows_removed",
                         "revenue_definition", "segmentation",
                         "prediction" },
  "model_metrics":    { "training_rows", "testing_rows", "categories",
                         "brands", "sizes", "metrics", "selected_model",
                         "selection_method", "feature_importance" }
}
```

### `customer_agg_10M.csv`

| Column | Type | Description |
|---|---|---|
| `Customer_ID` | string | Unique customer identifier |
| `spend` | float | Total net spend (Net_Sales sum) |
| `items` | int | Total items purchased |
| `orders` | int | Total number of orders |
| `age` | float | Average age across transactions |
| `rating` | float | Average product rating given |
| `location` | string | Customer location (from first transaction) |
| `cluster` | int | K-Means cluster label (0, 1, or 2) |

### `prediction_sample_10M.csv`

| Column | Type | Description |
|---|---|---|
| `Customer_ID` | string | Unique customer identifier |
| `spend` | float | Total net spend |
| `orders` | int | Total order count |
| `cluster` | int | K-Means cluster label (scatter chart colour) |

---

> **Note:** This documentation is part of the academic project submission.
> The architecture described here mirrors real-company data engineering practices
> (external storage for large files, ETL pipelines, summary-based API serving)
> and demonstrates understanding of scalable dashboard design beyond simple CSV loading.
>
> In a real company, the raw data would come from a website order database,
> POS system, Excel/CSV sales report, e-commerce platform API (Shopify, Daraz,
> WooCommerce), or customer database — and would flow through a scheduled ETL
> job into a data warehouse. The web dashboard would read only pre-computed
> summaries from that warehouse. This project mirrors exactly that pattern.
