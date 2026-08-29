"""
FastAPI Application Entry Point

Creates and configures the FastAPI application with:
- CORS middleware
- Centralized exception handling
- API v1 router (all domain modules)
- Health check endpoint
- Lifespan management
- OpenAPI documentation
"""

from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.exceptions import register_exception_handlers


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown events."""
    settings = get_settings()
    print(f"[STARTUP] {settings.app_name} v{settings.app_version}")
    print(f"[STARTUP] Debug mode: {settings.backend_debug}")
    print(f"[STARTUP] API docs: http://{settings.backend_host}:{settings.backend_port}/docs")

    yield

    print("[SHUTDOWN] Application shutting down...")


def create_app() -> FastAPI:
    """Application factory."""
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "AI-Based Real-Time Threat Detection and Emergency Response Platform.\n\n"
            "## API Modules\n"
            "- **Auth**: Login, register, token management\n"
            "- **Users**: User management (admin)\n"
            "- **Cameras**: Camera CRUD and stream control\n"
            "- **Incidents**: Incident lifecycle management\n"
            "- **Detections**: Raw detection event queries\n"
            "- **Evidence**: Evidence capture and retrieval\n"
            "- **Alerts**: Real-time alert management\n"
            "- **Analytics**: Dashboard metrics and charts\n"
        ),
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # --- Middleware ---
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # --- Exception Handlers ---
    register_exception_handlers(app)

    # --- API Routers ---
    app.include_router(api_router)

    # --- Health Check (outside versioned API) ---
    @app.get("/api/v1/health", tags=["System"])
    async def health_check():
        """System health check endpoint. No authentication required."""
        return {
            "status": "healthy",
            "service": settings.app_name,
            "version": settings.app_version,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "environment": "development" if settings.backend_debug else "production",
        }

    @app.get("/", tags=["System"], include_in_schema=False)
    async def root():
        """Root endpoint."""
        return {
            "service": settings.app_name,
            "version": settings.app_version,
            "docs": "/docs",
            "health": "/api/v1/health",
        }

    return app


# Create the app instance (used by uvicorn)
app = create_app()
