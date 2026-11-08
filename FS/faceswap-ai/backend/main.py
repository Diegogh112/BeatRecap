"""
FaceSwap AI — Punto de entrada de la aplicación FastAPI.
"""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.database import Base, engine
from app.core.logging import setup_logging
from app.core.storage import ensure_dirs


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Inicialización y cierre de la aplicación."""
    setup_logging(settings.debug)
    ensure_dirs()

    # Crear tablas de la BD
    import app.models.project  # noqa: F401 — registra los modelos
    import app.models.job      # noqa: F401
    Base.metadata.create_all(bind=engine)
    logger.info(f"Base de datos inicializada: {settings.database_url}")
    logger.info(f"FaceSwap AI iniciado en modo: {settings.app_env.upper()}")

    yield

    logger.info("FaceSwap AI detenido")


app = FastAPI(
    title="FaceSwap AI API",
    description="API para intercambio de rostros en videos mediante IA",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

# ── CORS ───────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Rutas API ──────────────────────────────────────────────────────────────────
app.include_router(api_router)


# ── Servir thumbnails estáticos ────────────────────────────────────────────────
@app.get("/api/v1/thumbnails/{project_id}/{filename}")
async def serve_thumbnail(project_id: str, filename: str):
    """Sirve las miniaturas de rostros detectados."""
    path = settings.thumbnail_path / project_id / filename
    if not path.exists():
        return JSONResponse(status_code=404, content={"detail": "Imagen no encontrada"})
    return FileResponse(str(path))


# ── Health check ───────────────────────────────────────────────────────────────
@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "env": settings.app_env,
        "gpu": settings.use_gpu,
        "gpu_provider": "DirectML (AMD)" if settings.use_gpu else "CPU",
        "models": {
            "insightface": settings.insightface_model,
            "inswapper": settings.inswapper_model_path.exists(),
            "gfpgan": settings.gfpgan_model_path.exists(),
        },
    }


# ── Manejo global de errores ───────────────────────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Error no manejado: {exc} — {request.url}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Error interno del servidor"},
    )
