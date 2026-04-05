"""FastAPI application — entrypoint for the monitoring dashboard API.

Run: uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
"""

from __future__ import annotations

import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse

from api.config import get_settings

# Track server start time for uptime calculation
_start_time: float = 0.0


def get_uptime() -> float:
    """Return seconds since server start."""
    return time.time() - _start_time


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown lifecycle."""
    global _start_time
    _start_time = time.time()

    settings = get_settings()
    if not settings.api_key:
        import warnings
        warnings.warn(
            "HARMONIX_API_KEY is not set. API will reject all requests. "
            "Set via vault or HARMONIX_API_KEY env var.",
            stacklevel=2,
        )

    yield  # app runs here

    # Shutdown: nothing to clean up (SQLite connections are per-request)


app = FastAPI(
    title="Harmonix Monitoring API",
    description="Delta-neutral funding arbitrage monitoring dashboard API",
    version="0.1.0",
    lifespan=lifespan,
)

# -------------------------------------------------------------------
# CORS
# -------------------------------------------------------------------
settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["X-API-Key", "Content-Type"],
)


# -------------------------------------------------------------------
# Auth middleware — X-API-Key on all /api/* routes
# -------------------------------------------------------------------
@app.middleware("http")
async def api_key_auth(request: Request, call_next) -> Response:
    """Validate X-API-Key header on /api/* routes."""
    if request.url.path.startswith("/api/"):
        # CORS preflight sends OPTIONS without X-API-Key; must not 401 or the browser blocks the real request.
        if request.method == "OPTIONS":
            return await call_next(request)

        expected_key = get_settings().api_key
        if not expected_key:
            return JSONResponse(
                status_code=500,
                content={"detail": "API key not configured on server"},
            )

        provided_key = request.headers.get("X-API-Key", "")
        if provided_key != expected_key:
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid or missing API key"},
            )

    return await call_next(request)


# -------------------------------------------------------------------
# Register routers
# -------------------------------------------------------------------
from api.routers import portfolio, positions, cashflows, health, vault  # noqa: E402

app.include_router(portfolio.router)
app.include_router(positions.router)
app.include_router(cashflows.router)
app.include_router(health.router)
app.include_router(vault.router)


def custom_openapi() -> dict:
    """Expose X-API-Key in OpenAPI so Swagger UI shows Authorize and sends the header."""
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    openapi_schema.setdefault("components", {}).setdefault("securitySchemes", {})[
        "ApiKeyAuth"
    ] = {
        "type": "apiKey",
        "in": "header",
        "name": "X-API-Key",
        "description": "Same value as server env HARMONIX_API_KEY",
    }
    openapi_schema["security"] = [{"ApiKeyAuth": []}]
    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi  # type: ignore[method-assign]


# -------------------------------------------------------------------
# Root redirect
# -------------------------------------------------------------------
@app.get("/")
async def root():
    return {"message": "Harmonix Monitoring API", "docs": "/docs"}
