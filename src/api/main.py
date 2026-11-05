"""FastAPI application factory and entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse

from src.api.routers import (
    automata_router,
    datasets_router,
    detect_router,
    evaluation_router,
    health_router,
    ml_router,
    packet_router,
    workflows_router,
)
from src.common.config import settings
from src.db.session import create_tables, get_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Ensure database schema tables are created upon startup if not overridden."""
    if get_db not in app.dependency_overrides:
        create_tables()
    yield


def create_app() -> FastAPI:
    """FastAPI application factory."""
    app = FastAPI(
        title="TOC Process Workflow Anomaly Detection API",
        version="1.0.0",
        description="Formal Automata & Machine Learning Hybrid Anomaly Detection REST Service",
        openapi_url="/api/v1/openapi.json",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # CORS configuration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Standardized Exception Handlers (Doc 08 §4: {"error": {"code": "...", "message": "..."}})
    @app.exception_handler(HTTPException)
    async def custom_http_exception_handler(request: Request, exc: HTTPException):
        detail = exc.detail
        if isinstance(detail, dict) and "code" in detail and "message" in detail:
            return JSONResponse(status_code=exc.status_code, content={"error": detail})
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": f"HTTP_{exc.status_code}", "message": str(detail)}},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Request payload validation failed",
                    "details": exc.errors(),
                }
            },
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": {"code": "INTERNAL_SERVER_ERROR", "message": str(exc)}},
        )

    # Root redirect to documentation
    @app.get("/", include_in_schema=False)
    def root():
        return RedirectResponse(url="/docs")

    # API v1 Router Registration
    api_v1_prefix = "/api/v1"
    app.include_router(health_router, prefix=api_v1_prefix)
    app.include_router(workflows_router, prefix=api_v1_prefix)
    app.include_router(automata_router, prefix=api_v1_prefix)
    app.include_router(datasets_router, prefix=api_v1_prefix)
    app.include_router(ml_router, prefix=api_v1_prefix)
    app.include_router(detect_router, prefix=api_v1_prefix)
    app.include_router(evaluation_router, prefix=api_v1_prefix)
    app.include_router(packet_router, prefix=api_v1_prefix)

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("src.api.main:app", host=settings.API_HOST, port=settings.API_PORT, reload=True)
