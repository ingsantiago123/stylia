"""
Punto de entrada de la aplicación FastAPI.
MVP 1: Dashboard básico + flujo DOCX → corrección → PDF.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.config import settings
from app.database import engine, Base
from app.api.v1 import documents

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Inicialización y cleanup de la aplicación."""
    # Startup: crear tablas si no existen (en MVP; en prod usar Alembic)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # MVP2: agregar columnas nuevas a tabla patches si no existen
    # (create_all NO agrega columnas a tablas existentes)
    async with engine.begin() as conn:
        migrations = [
            "ALTER TABLE patches ADD COLUMN IF NOT EXISTS category VARCHAR(30)",
            "ALTER TABLE patches ADD COLUMN IF NOT EXISTS severity VARCHAR(15)",
            "ALTER TABLE patches ADD COLUMN IF NOT EXISTS explanation TEXT",
            "ALTER TABLE patches ADD COLUMN IF NOT EXISTS confidence FLOAT",
            "ALTER TABLE patches ADD COLUMN IF NOT EXISTS rewrite_ratio FLOAT",
            "ALTER TABLE patches ADD COLUMN IF NOT EXISTS pass_number INTEGER",
            "ALTER TABLE patches ADD COLUMN IF NOT EXISTS model_used VARCHAR(50)",
            "ALTER TABLE patches ADD COLUMN IF NOT EXISTS paragraph_index INTEGER",
        ]
        for sql in migrations:
            await conn.execute(text(sql))
        logger.info("MVP2: columnas de patches verificadas/creadas")

    # MVP2: columnas de tokens/costos en documents
    async with engine.begin() as conn:
        cost_migrations = [
            "ALTER TABLE documents ADD COLUMN IF NOT EXISTS prompt_tokens INTEGER",
            "ALTER TABLE documents ADD COLUMN IF NOT EXISTS completion_tokens INTEGER",
            "ALTER TABLE documents ADD COLUMN IF NOT EXISTS total_tokens INTEGER",
            "ALTER TABLE documents ADD COLUMN IF NOT EXISTS llm_cost_usd FLOAT",
        ]
        for sql in cost_migrations:
            await conn.execute(text(sql))
        logger.info("MVP2: columnas de costos verificadas/creadas")

    # MVP2 Lote 3: columnas de análisis editorial en blocks
    async with engine.begin() as conn:
        analysis_migrations = [
            "ALTER TABLE blocks ADD COLUMN IF NOT EXISTS paragraph_type VARCHAR(30)",
            "ALTER TABLE blocks ADD COLUMN IF NOT EXISTS requires_llm BOOLEAN DEFAULT TRUE",
            "ALTER TABLE blocks ADD COLUMN IF NOT EXISTS section_id UUID REFERENCES section_summaries(id) ON DELETE SET NULL",
        ]
        for sql in analysis_migrations:
            await conn.execute(text(sql))
        logger.info("MVP2 Lote 3: columnas de análisis en blocks verificadas/creadas")

    # MVP2 Lote 4: columna route_taken en patches
    async with engine.begin() as conn:
        lote4_migrations = [
            "ALTER TABLE patches ADD COLUMN IF NOT EXISTS route_taken VARCHAR(15)",
        ]
        for sql in lote4_migrations:
            await conn.execute(text(sql))
        logger.info("MVP2 Lote 4: columna route_taken en patches verificada/creada")

    # MVP2 Lote 5: quality gates en patches
    async with engine.begin() as conn:
        lote5_migrations = [
            "ALTER TABLE patches ADD COLUMN IF NOT EXISTS gate_results JSONB",
            "ALTER TABLE patches ADD COLUMN IF NOT EXISTS review_reason TEXT",
        ]
        for sql in lote5_migrations:
            await conn.execute(text(sql))
        logger.info("MVP2 Lote 5: columnas quality gates en patches verificadas/creadas")

    # Progreso granular en documents
    async with engine.begin() as conn:
        progress_migrations = [
            "ALTER TABLE documents ADD COLUMN IF NOT EXISTS progress_stage VARCHAR(30)",
            "ALTER TABLE documents ADD COLUMN IF NOT EXISTS progress_stage_current INTEGER",
            "ALTER TABLE documents ADD COLUMN IF NOT EXISTS progress_stage_total INTEGER",
            "ALTER TABLE documents ADD COLUMN IF NOT EXISTS progress_message VARCHAR(200)",
            "ALTER TABLE documents ADD COLUMN IF NOT EXISTS heartbeat_at TIMESTAMPTZ",
            "ALTER TABLE documents ADD COLUMN IF NOT EXISTS stage_started_at TIMESTAMPTZ",
        ]
        for sql in progress_migrations:
            await conn.execute(text(sql))
        logger.info("Progreso granular: columnas en documents verificadas/creadas")

    # Corrección paralela por lotes: tabla correction_batches + columna batch_index en patches
    async with engine.begin() as conn:
        parallel_migrations = [
            "ALTER TABLE patches ADD COLUMN IF NOT EXISTS batch_index INTEGER",
            """CREATE TABLE IF NOT EXISTS correction_batches (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                doc_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                batch_index INTEGER NOT NULL,
                start_paragraph INTEGER NOT NULL,
                end_paragraph INTEGER NOT NULL,
                paragraphs_total INTEGER NOT NULL DEFAULT 0,
                paragraphs_corrected INTEGER NOT NULL DEFAULT 0,
                patches_count INTEGER NOT NULL DEFAULT 0,
                status VARCHAR(20) NOT NULL DEFAULT 'pending',
                celery_task_id VARCHAR(200),
                context_seed TEXT,
                last_corrected_text TEXT,
                lt_pass_completed BOOLEAN NOT NULL DEFAULT FALSE,
                llm_pass_completed BOOLEAN NOT NULL DEFAULT FALSE,
                boundary_checked BOOLEAN NOT NULL DEFAULT FALSE,
                error_message TEXT,
                started_at TIMESTAMPTZ,
                completed_at TIMESTAMPTZ,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                CONSTRAINT uq_correction_batches_doc_batch UNIQUE (doc_id, batch_index)
            )""",
        ]
        for sql in parallel_migrations:
            await conn.execute(text(sql))
        logger.info("Corrección paralela: correction_batches y batch_index verificadas/creadas")

    # Processing time tracking en documents
    async with engine.begin() as conn:
        timing_migrations = [
            "ALTER TABLE documents ADD COLUMN IF NOT EXISTS processing_started_at TIMESTAMPTZ",
            "ALTER TABLE documents ADD COLUMN IF NOT EXISTS processing_completed_at TIMESTAMPTZ",
            "ALTER TABLE documents ADD COLUMN IF NOT EXISTS stage_timings JSONB",
            "ALTER TABLE documents ADD COLUMN IF NOT EXISTS worker_hostname VARCHAR(200)",
        ]
        for sql in timing_migrations:
            await conn.execute(text(sql))
        logger.info("Timing tracking: columnas en documents verificadas/creadas")

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
