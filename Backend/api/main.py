# Backend/api/main.py

import os
import sys

from dotenv import load_dotenv
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.requests import Request

# Adiciona o diretório raiz ao path para encontrar os outros módulos
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from api.core.database import init_db
from api.core.deps import get_current_user
from api.core.security import decode_token
from api.endpoints import state as session_state
from api.endpoints.auth import router as auth_router
from api.endpoints.data import router as data_router
from api.endpoints.predictions import router as predictions_router
from api.endpoints.reports import router as reports_router
from api.endpoints.simulations import router as simulations_router

load_dotenv()

app = FastAPI(
    title="Simple Tech API",
    description="Cloud financial management: cash flow analysis, ML forecasting, and scenario simulation.",
    version="2.0.0",
)

_default_cors = (
    "http://localhost:8080,"
    "http://localhost:5173,"
    "http://127.0.0.1:8080,"
    "https://matheusmaggiorini.github.io"
)
_cors_origins = os.getenv("CORS_ORIGINS", _default_cors).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _cors_origins if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)

_protected = [Depends(get_current_user)]
app.include_router(data_router, prefix="/api/data", tags=["Data Management"], dependencies=_protected)
app.include_router(
    predictions_router,
    prefix="/api/predictions",
    tags=["Predictions"],
    dependencies=_protected,
)
app.include_router(
    simulations_router,
    prefix="/api/simulations",
    tags=["Simulations"],
    dependencies=_protected,
)
app.include_router(reports_router, prefix="/api", tags=["Reports"], dependencies=_protected)


@app.middleware("http")
async def bind_user_context(request: Request, call_next):
    """Set per-request user id for session state (ContextVar) from JWT."""
    auth = request.headers.get("Authorization")
    if auth and auth.startswith("Bearer "):
        payload = decode_token(auth[7:].strip())
        if payload and payload.get("sub") is not None:
            try:
                session_state.set_current_user(int(payload["sub"]))
            except (TypeError, ValueError):
                pass
    return await call_next(request)


@app.on_event("startup")
async def startup() -> None:
    init_db()


@app.get("/", tags=["Root"])
async def read_root():
    return {
        "message": "Simple Tech API is running",
        "docs_url": "/docs",
        "version": "2.0.0",
    }


@app.get("/health", tags=["Health Check"])
async def health_check():
    return {"status": "healthy"}


@app.get("/api/auth/me", tags=["Authentication"])
async def get_me(user: dict = Depends(get_current_user)):
    return {"id": user["id"], "email": user["email"], "name": user["name"]}


if __name__ == "__main__":
    import uvicorn

    print("Starting Simple Tech API at http://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)
