"""
Punto de entrada de la aplicación FastAPI.
MVP 1: Dashboard básico + flujo DOCX → corrección → PDF.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import engine, Base
from app.api.v1 import documents


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Inicialización y cleanup de la aplicación."""
    # Startup: crear tablas si no existen (en MVP; en prod usar Alembic)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Inicializar bucket de MinIO
    from app.utils.minio_client import ensure_bucket
    await ensure_bucket()

    yield

    # Shutdown
    await engine.dispose()


app = FastAPI(
    title=settings.app_name,
    description="Sistema de corrección de estilo con preservación de formato — MVP 1",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS para el frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Registrar routers
app.include_router(documents.router, prefix="/api/v1")


@app.get("/health")
async def health_check():
    """Endpoint de salud."""
    return {"status": "ok", "service": settings.app_name}
