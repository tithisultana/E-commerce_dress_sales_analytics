from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .app.data import DatasetError
from .app.routes import router


app = FastAPI(title="Dress Sales Analytics API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)


@app.exception_handler(DatasetError)
async def dataset_error_handler(request: Request, exc: DatasetError) -> JSONResponse:
    return JSONResponse(status_code=503, content={"detail": str(exc)})
