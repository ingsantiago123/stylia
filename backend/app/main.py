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

    # HITL redesign: nuevas columnas en patches y documents
    async with engine.begin() as conn:
        hitl_migrations = [
            "ALTER TABLE patches ADD COLUMN IF NOT EXISTS edited_text TEXT",
            "ALTER TABLE patches ADD COLUMN IF NOT EXISTS edited_at TIMESTAMPTZ",
            "ALTER TABLE patches ADD COLUMN IF NOT EXISTS recorrection_count INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE patches ADD COLUMN IF NOT EXISTS recorrection_note TEXT",
            "ALTER TABLE patches ALTER COLUMN decision_source TYPE VARCHAR(30)",
            "ALTER TABLE documents ADD COLUMN IF NOT EXISTS render_version INTEGER NOT NULL DEFAULT 1",
            "ALTER TABLE documents ALTER COLUMN status TYPE VARCHAR(30)",
        ]
        for sql in hitl_migrations:
            await conn.execute(text(sql))
        logger.info("HITL: columnas de edición manual, recorrección y render_version verificadas/creadas")

    # Plan v3: audit trail en patches + columna batch_id alias
    async with engine.begin() as conn:
        v3_migrations = [
            "ALTER TABLE patches ADD COLUMN IF NOT EXISTS lt_corrections_json JSONB",
            "ALTER TABLE patches ADD COLUMN IF NOT EXISTS llm_change_log_json JSONB",
            "ALTER TABLE patches ADD COLUMN IF NOT EXISTS reverted_lt_changes_json JSONB",
            "ALTER TABLE patches ADD COLUMN IF NOT EXISTS protected_regions_snapshot JSONB",
        ]
        for sql in v3_migrations:
            await conn.execute(text(sql))
        logger.info("Plan v3: columnas de audit trail en patches verificadas/creadas")

    # Plan v4: doble pasada + trazabilidad RAW
    async with engine.begin() as conn:
        v4_patch_migrations = [
            "ALTER TABLE patches ADD COLUMN IF NOT EXISTS corrected_pass1_text TEXT",
            "ALTER TABLE patches ADD COLUMN IF NOT EXISTS pass2_audit_json JSONB",
            # Ampliar source de varchar(20) a varchar(50) para 'languagetool+chatgpt+audit'
            "ALTER TABLE patches ALTER COLUMN source TYPE VARCHAR(50)",
        ]
        for sql in v4_patch_migrations:
            await conn.execute(text(sql))
        logger.info("Plan v4: columnas de doble pasada en patches verificadas/creadas")

    async with engine.begin() as conn:
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS document_global_context (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                doc_id UUID NOT NULL UNIQUE REFERENCES documents(id) ON DELETE CASCADE,
                global_summary TEXT,
                dominant_voice TEXT,
                dominant_register VARCHAR(50),
                key_themes_json JSONB,
                protected_globals_json JSONB,
                style_fingerprint_json JSONB,
                total_paragraphs INTEGER,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """))
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS llm_audit_log (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                doc_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                paragraph_index INTEGER,
                location VARCHAR(100),
                pass_number SMALLINT NOT NULL DEFAULT 1,
                call_purpose VARCHAR(40) NOT NULL,
                model_used VARCHAR(50),
                request_payload JSONB,
                response_payload JSONB,
                prompt_tokens INTEGER,
                completion_tokens INTEGER,
                total_tokens INTEGER,
                latency_ms INTEGER,
                error_text TEXT,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """))
        await conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_llm_audit_doc_para "
            "ON llm_audit_log (doc_id, paragraph_index, pass_number)"
        ))
        await conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_llm_audit_doc_created "
            "ON llm_audit_log (doc_id, created_at)"
        ))
        logger.info("Plan v4: tablas document_global_context y llm_audit_log verificadas/creadas")

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
