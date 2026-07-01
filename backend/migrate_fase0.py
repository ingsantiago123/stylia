"""
Migración Fase 0 — Hotfixes del diagnóstico (DIAGNOSTICO_STYLIA.md).

Añade `patches.location`: la ubicación DOCX nativa de cada patch se persiste
en BD. Antes vivía únicamente en `patches_docx.json` (MinIO) y se
reconstruía por la clave frágil (paragraph_index, original_text[:50]), lo
que rompía el render de los patches grupales (paragraph_index=NULL) y hacía
de MinIO una segunda fuente de verdad desincronizable.

Idempotente: usa ALTER TABLE ... ADD COLUMN IF NOT EXISTS. Puede correrse
múltiples veces sin efectos secundarios.

Uso:
    python scripts/migrate_fase0.py
o desde el contenedor:
    docker-compose exec backend python scripts/migrate_fase0.py
o copiando al contenedor:
    docker cp scripts/migrate_fase0.py correctordeestilos-backend-1:/app/migrate_fase0.py
    docker exec correctordeestilos-backend-1 python /app/migrate_fase0.py
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
logger = logging.getLogger("migrate_fase0")


PATCH_COLUMNS = [
    ("location", "VARCHAR(80)"),
]

INDEXES = [
    # El render candidato/final deduplica y resuelve párrafos por location.
    "CREATE INDEX IF NOT EXISTS idx_patches_location ON patches(location)",
]


def main() -> int:
    db_url = settings.database_url_sync
    if not db_url:
        logger.error("DATABASE_URL_SYNC no está configurada")
        return 1

    logger.info("Conectando a %s", db_url.split("@")[-1])
    engine = create_engine(db_url, future=True)

    with engine.begin() as conn:
        for col, type_ in PATCH_COLUMNS:
            stmt = f"ALTER TABLE patches ADD COLUMN IF NOT EXISTS {col} {type_}"
            logger.info("  patches: %s %s", col, type_)
            conn.execute(text(stmt))

        for ix in INDEXES:
            logger.info("  %s", ix)
            conn.execute(text(ix))

    logger.info("Migración Fase 0 completada con éxito.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
