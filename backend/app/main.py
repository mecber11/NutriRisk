"""NutriRisk AI application factory."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, select

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.errors import configure_logging, register_exception_handlers
from app.db.session import SessionLocal
from app.middleware.audit import AuditMiddleware
from app.middleware.security import RateLimitMiddleware, SecurityHeadersMiddleware

logger = logging.getLogger("nutririsk.app")

DESCRIPTION = """
**NutriRisk AI** — plataforma de predicción explicable de riesgo de desnutrición infantil.

Integra determinantes socioeconómicos, nutricionales y ambientales con modelos
espacialmente transferibles (Random Forest, XGBoost, CatBoost, híbridos espaciales
y CNN-LSTM), explicabilidad SHAP y análisis de equidad con Fairlearn.

* Datos de demostración **sintéticos** (claramente etiquetados).
* Estándares antropométricos **OMS 2006** (HAZ, WAZ, WHZ, BAZ).
* Bitácora inmutable de accesos y exportación PDF / Word / Excel.
"""


def _seed_if_empty() -> None:
    """Populate demo data once, only when the database is reachable and empty."""
    try:
        with SessionLocal() as db:
            from app.models.user import User

            users = db.scalar(select(func.count(User.id))) or 0
        if users == 0:
            from app.db.bootstrap import bootstrap

            logger.info("Base de datos vacía: ejecutando bootstrap de demostración")
            bootstrap()
    except Exception:  # noqa: BLE001
        logger.exception("No se pudo inicializar la base de datos")


@asynccontextmanager
async def lifespan(app: FastAPI):  # noqa: ANN201
    settings.ensure_directories()
    configure_logging("DEBUG" if settings.debug else "INFO")
    logger.info("Iniciando %s v%s (%s)", settings.app_name, settings.app_version, settings.environment)
    if settings.auto_seed:
        _seed_if_empty()
    yield
    logger.info("Deteniendo %s", settings.app_name)


def create_app() -> FastAPI:
    app = FastAPI(
        title=f"{settings.app_name} API",
        version=settings.app_version,
        description=DESCRIPTION,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        contact={"name": "NutriRisk AI", "email": "soporte@nutririsk.ai"},
        license_info={"name": "Uso académico — demostración con datos sintéticos"},
    )

    register_exception_handlers(app)

    # Middleware (last added = outermost).
    app.add_middleware(AuditMiddleware)
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Session-Id", "X-Client-Name", "X-N8N-Token"],
        expose_headers=["Content-Disposition", "X-RateLimit-Limit", "X-Report-Format"],
    )

    app.include_router(api_router, prefix=settings.api_v1_prefix)

    @app.get("/health", include_in_schema=False)
    def health_root() -> JSONResponse:
        return JSONResponse(
            {
                "status": "ok",
                "app": settings.app_name,
                "version": settings.app_version,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )

    @app.get("/api", include_in_schema=False)
    def api_index() -> dict:
        return {
            "app": settings.app_name,
            "version": settings.app_version,
            "docs": "/docs",
            "openapi": "/openapi.json",
            "api": settings.api_v1_prefix,
        }

    _mount_frontend(app)
    return app


def _mount_frontend(app: FastAPI) -> None:
    """Serve the built React SPA when available (single-container deployment)."""
    dist: Path = settings.frontend_dist
    assets = dist / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=str(assets)), name="assets")

    index_file = dist / "index.html"

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str, request: Request):  # noqa: ANN201
        if full_path.startswith(("api/", "docs", "redoc", "openapi.json")):
            raise HTTPException(status_code=404, detail="Recurso no encontrado")
        candidate = dist / full_path if full_path else None
        if candidate and candidate.is_file():
            return FileResponse(candidate)
        if index_file.is_file():
            return FileResponse(index_file)
        return JSONResponse(
            status_code=200,
            content={
                "app": settings.app_name,
                "message": "Frontend no compilado. Ejecute 'pnpm build' en frontend/ o use el contenedor web.",
                "docs": "/docs",
            },
        )


app = create_app()


