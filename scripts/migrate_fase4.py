"""
Migración Fase 4 — Orquestación resumible (pipeline_runs).

Crea la tabla `pipeline_runs` (ver DIAGNOSTICO_STYLIA.md §2.2.3 y Fase 4):
un registro por ejecución del pipeline con checkpoints por etapa, costo
acumulado y kill-switch de costo. Los reintentos de Celery retoman desde el
último checkpoint en vez de re-pagar todo el documento.

Idempotente: CREATE TABLE/INDEX IF NOT EXISTS.

Uso:
    python scripts/migrate_fase4.py
o desde el contenedor:
    docker-compose exec backend python scripts/migrate_fase4.py
"""

from __future__ import annotations

import logging
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
BACKEND = os.path.join(ROOT, "backend")
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

from sqlalchemy import create_engine, text  # noqa: E402

from app.config import settings  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("migrate_fase4")


PIPELINE_RUNS_DDL = """
CREATE TABLE IF NOT EXISTS pipeline_runs (
    id UUID PRIMARY KEY,
    doc_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    run_no INTEGER NOT NULL DEFAULT 1,
    celery_task_id VARCHAR(155),
    status VARCHAR(20) NOT NULL DEFAULT 'running',
    current_stage VARCHAR(20),
    checkpoint_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    retries INTEGER NOT NULL DEFAULT 0,
    cost_usd DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    cost_limit_usd DOUBLE PRECISION,
    error_message TEXT,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMPTZ
);
"""

INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_pipeline_runs_doc ON pipeline_runs(doc_id, run_no)",
    "CREATE INDEX IF NOT EXISTS idx_pipeline_runs_status ON pipeline_runs(doc_id, status)",
]


def main() -> int:
    db_url = settings.database_url_sync
    if not db_url:
        logger.error("DATABASE_URL_SYNC no está configurada")
        return 1

    logger.info("Conectando a %s", db_url.split("@")[-1])
    engine = create_engine(db_url, future=True)

    with engine.begin() as conn:
        logger.info("Creando pipeline_runs (IF NOT EXISTS)...")
        conn.execute(text(PIPELINE_RUNS_DDL))
        for ix in INDEXES:
            logger.info("  %s", ix)
            conn.execute(text(ix))

    logger.info("Migración Fase 4 completada con éxito.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
