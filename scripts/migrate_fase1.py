"""
Migración Fase 1 — AST documental persistente (document_nodes).

Crea la tabla `document_nodes` (ver DIAGNOSTICO_STYLIA.md §2.2): un nodo por
elemento estructural del DOCX con identidad determinista (oxml_path +
content_hash) y proyección de paginación real (page_start/page_end).

Idempotente: CREATE TABLE/INDEX IF NOT EXISTS.

Uso:
    python scripts/migrate_fase1.py
o desde el contenedor:
    docker-compose exec backend python scripts/migrate_fase1.py
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
logger = logging.getLogger("migrate_fase1")


DOCUMENT_NODES_DDL = """
CREATE TABLE IF NOT EXISTS document_nodes (
    id UUID PRIMARY KEY,
    doc_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    revision INTEGER NOT NULL DEFAULT 1,
    parent_id UUID REFERENCES document_nodes(id) ON DELETE CASCADE,
    node_type VARCHAR(20) NOT NULL,
    order_key VARCHAR(16) NOT NULL,
    depth INTEGER NOT NULL DEFAULT 0,
    oxml_path VARCHAR(160) NOT NULL,
    content_hash VARCHAR(16),
    legacy_location VARCHAR(80),
    original_text TEXT,
    attrs JSONB NOT NULL DEFAULT '{}'::jsonb,
    classification VARCHAR(30),
    skip_reason VARCHAR(20),
    page_start INTEGER,
    page_end INTEGER,
    page_break_offset INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_nodes_doc_rev_path UNIQUE (doc_id, revision, oxml_path)
);
"""

INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_nodes_doc_order ON document_nodes(doc_id, revision, order_key)",
    "CREATE INDEX IF NOT EXISTS idx_nodes_legacy_loc ON document_nodes(doc_id, legacy_location)",
    "CREATE INDEX IF NOT EXISTS idx_nodes_parent ON document_nodes(parent_id)",
]


def main() -> int:
    db_url = settings.database_url_sync
    if not db_url:
        logger.error("DATABASE_URL_SYNC no está configurada")
        return 1

    logger.info("Conectando a %s", db_url.split("@")[-1])
    engine = create_engine(db_url, future=True)

    with engine.begin() as conn:
        logger.info("Creando document_nodes (IF NOT EXISTS)...")
        conn.execute(text(DOCUMENT_NODES_DDL))
        for ix in INDEXES:
            logger.info("  %s", ix)
            conn.execute(text(ix))

    logger.info("Migración Fase 1 completada con éxito.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
