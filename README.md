# E-Commerce Dress Sales Analytics

A full-stack analytics dashboard built for academic demonstration and machine learning analysis. Dataset: Synthetic e-commerce dress sales transaction dataset created for academic demonstration and machine learning analysis. The notebooks and root-level CSV remain available as the project's academic evidence; identical working copies live in `notebooks/` and `data/` for the application structure.

## Project structure

- `data/dress_sales.csv` - synthetic application dataset, copied from the root-level source CSV
- `notebooks/` - copies of the three original EDA, prediction, and segmentation notebooks
- `backend/main.py` - FastAPI endpoints, analytics calculations, models, and prediction API
- `backend/requirements.txt` - Python dependencies
- `frontend/` - React, Vite, Recharts dashboard and responsive styles
- `data_dictionary.md` - source field definitions
- Root-level dataset and notebooks - original academic evidence, preserved unchanged

## Run locally

Start the API in one terminal:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
uvicorn backend.main:app --reload --port 8000
```

Start the dashboard in another terminal:

```bash
cd frontend
npm install
npm run dev
```

Open the Vite URL shown in the terminal (normally `http://localhost:5173`). FastAPI documentation is available at `http://localhost:8000/docs`. Set `VITE_API_URL` when the API runs at a different URL.

## Analytics and models

- Revenue is `Price × Quantity × (1 − Discount / 100)`; charts and KPIs are derived from the CSV.
- Customer groups use K-Means (`k=3`) over standardized gross spend, item count, and order count.
- Quantity prediction compares a Linear Regression baseline with a 200-tree Random Forest. Both use one-hot encoded product descriptors, an 80/20 random train/test split, and seed 42.
- The prediction page reports MAE, RMSE, and R² on the held-out test set before offering an interactive estimate.

The original notebook workflows were written for Google Colab and may request an upload of `dress_sales.csv` when run there.
