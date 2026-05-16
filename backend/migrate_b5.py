"""
Migración B.5 — Conciencia estructural por tipo de elemento.

Idempotente: usa ALTER TABLE ... ADD COLUMN IF NOT EXISTS y CREATE TABLE
IF NOT EXISTS. Puede correrse múltiples veces sin efectos secundarios.

Uso:
    python scripts/migrate_b5.py
o desde el contenedor:
    docker-compose exec backend python scripts/migrate_b5.py

Para entornos nuevos basta con que SQLAlchemy ejecute Base.metadata.create_all
al arrancar; este script existe para upgradar instalaciones EXISTENTES sin
perder datos.
"""

from __future__ import annotations

import logging
import os
import sys

# Permitir ejecutar desde la raíz del repo
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
BACKEND = os.path.join(ROOT, "backend")
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

from sqlalchemy import create_engine, text  # noqa: E402

from app.config import settings  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("migrate_b5")


# Columnas a añadir a tablas existentes. Cada entrada es (tabla, columna, tipo).
BLOCK_COLUMNS = [
    ("docx_location", "VARCHAR(80)"),
    ("style_name", "VARCHAR(80)"),
    ("style_level", "INTEGER"),
    ("list_id", "VARCHAR(40)"),
    ("list_position", "INTEGER"),
    ("list_total", "INTEGER"),
    ("list_format_type", "VARCHAR(20)"),
    ("list_level", "INTEGER"),
    ("table_id", "VARCHAR(40)"),
    ("row_index", "INTEGER"),
    ("column_index", "INTEGER"),
    ("row_total", "INTEGER"),
    ("col_total", "INTEGER"),
    ("table_cell_role", "VARCHAR(15)"),
    ("element_group_id", "UUID"),
]

PATCH_COLUMNS = [
    ("group_id", "UUID"),
    ("group_call_index", "INTEGER"),
    ("group_call_id", "VARCHAR(50)"),
    ("structural_role", "VARCHAR(30)"),
]

PROFILE_COLUMNS = [
    ("prompt_blocks", "JSONB"),
]

ELEMENT_GROUPS_DDL = """
CREATE TABLE IF NOT EXISTS element_groups (
    id UUID PRIMARY KEY,
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    group_type VARCHAR(10) NOT NULL,
    docx_native_id VARCHAR(40),
    item_count INTEGER NOT NULL DEFAULT 0,
    metadata_json JSONB,
    section_id UUID REFERENCES section_summaries(id) ON DELETE SET NULL,
    correction_status VARCHAR(15) NOT NULL DEFAULT 'pending',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""

INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_blocks_list ON blocks(list_id)",
    "CREATE INDEX IF NOT EXISTS idx_blocks_table ON blocks(table_id)",
    "CREATE INDEX IF NOT EXISTS idx_blocks_group ON blocks(element_group_id)",
    "CREATE INDEX IF NOT EXISTS idx_blocks_style ON blocks(style_name)",
    "CREATE INDEX IF NOT EXISTS idx_patches_group ON patches(group_id)",
    "CREATE INDEX IF NOT EXISTS idx_egroups_document ON element_groups(document_id)",
    "CREATE INDEX IF NOT EXISTS idx_egroups_section ON element_groups(section_id)",
    "CREATE INDEX IF NOT EXISTS idx_egroups_type ON element_groups(group_type)",
]


def main() -> int:
    db_url = settings.database_url_sync
    if not db_url:
        logger.error("DATABASE_URL_SYNC no está configurada")
        return 1

    logger.info("Conectando a %s", db_url.split("@")[-1])
    engine = create_engine(db_url, future=True)

    with engine.begin() as conn:
        # 1) Crear tabla element_groups si no existe
        logger.info("Creando element_groups (IF NOT EXISTS)...")
        conn.execute(text(ELEMENT_GROUPS_DDL))

        # 2) Añadir columnas a blocks
        for col, type_ in BLOCK_COLUMNS:
            stmt = f"ALTER TABLE blocks ADD COLUMN IF NOT EXISTS {col} {type_}"
            logger.info("  blocks: %s %s", col, type_)
            conn.execute(text(stmt))

        # 3) Añadir columnas a patches
        for col, type_ in PATCH_COLUMNS:
            stmt = f"ALTER TABLE patches ADD COLUMN IF NOT EXISTS {col} {type_}"
            logger.info("  patches: %s %s", col, type_)
            conn.execute(text(stmt))

        # 3b) Añadir columnas a document_profiles
        for col, type_ in PROFILE_COLUMNS:
            stmt = f"ALTER TABLE document_profiles ADD COLUMN IF NOT EXISTS {col} {type_}"
            logger.info("  document_profiles: %s %s", col, type_)
            conn.execute(text(stmt))

        # 4) Índices
        for ix in INDEXES:
            logger.info("  %s", ix)
            conn.execute(text(ix))

    logger.info("Migración B.5 completada con éxito.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
