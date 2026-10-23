from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Load environment variables from backend/.env or root .env if present
try:
    from dotenv import load_dotenv

    _backend_dir = Path(__file__).resolve().parent
    _env_backend = _backend_dir / ".env"
    _env_root = _backend_dir.parent / ".env"

    if _env_backend.is_file():
        load_dotenv(dotenv_path=_env_backend, override=False)
    elif _env_root.is_file():
        load_dotenv(dotenv_path=_env_root, override=False)
    else:
        load_dotenv(override=False)
except ImportError:
    pass

from .app.data import DatasetError
from .app.routes import router


app = FastAPI(title="Dress Sales Analytics API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
        "https://ecommerce-dress-sales-dashboard.onrender.com",
    ],
    allow_origin_regex=r"https://.*\.app\.github\.dev",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)


@app.exception_handler(DatasetError)
async def dataset_error_handler(request: Request, exc: DatasetError) -> JSONResponse:
    return JSONResponse(status_code=503, content={"detail": str(exc)})
