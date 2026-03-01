"""
Servicio de Ingesta (Etapa A).
Recibe DOCX → guarda en MinIO → convierte a PDF → cuenta páginas → crea registros.
"""

import logging
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.document import Document
from app.models.page import Page
from app.models.job import Job
from app.utils import minio_client
from app.utils.pdf_utils import convert_docx_to_pdf, count_pdf_pages

logger = logging.getLogger(__name__)


async def ingest_document(
    db: AsyncSession,
    file_data: bytes,
    filename: str,
) -> Document:
    """
    Ingesta de un documento DOCX.
    1. Guarda el original en MinIO
    2. Crea registro en BD
    3. Retorna el documento para que el endpoint lance el procesamiento
    """
    doc_id = uuid.uuid4()
    original_format = "docx" if filename.lower().endswith(".docx") else "pdf"

    # Determinar content type
    content_type = (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        if original_format == "docx"
        else "application/pdf"
    )

    # Subir original a MinIO: source/{doc_id}/{filename}
    source_key = f"source/{doc_id}/{filename}"
    minio_client.upload_file(source_key, file_data, content_type=content_type)

    # Crear registro en BD
    document = Document(
        id=doc_id,
        filename=filename,
        original_format=original_format,
        source_uri=source_key,
        docx_uri=source_key if original_format == "docx" else None,
        status="uploaded",
        config_json={
            "language": "es",
            "perfeccionista": True,
            "custom_dictionary": [],
            "glossary": {},
            "lt_disabled_rules": [],
        },
    )
    db.add(document)
    await db.flush()

    logger.info(f"Documento ingresado: {doc_id} ({filename})")
    return document


def process_ingestion_sync(doc_id: str, source_key: str, filename: str, original_format: str) -> dict:
    """
    Procesamiento síncrono de ingesta (ejecutado por Celery worker).
    1. Descarga el archivo de MinIO
    2. Si es DOCX, convierte a PDF
    3. Cuenta páginas del PDF
    4. Sube el PDF a MinIO
    
    Retorna dict con resultados para actualizar la BD.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        # Descargar archivo original
        original_ext = Path(filename).suffix.lower()
        local_path = str(Path(tmpdir) / filename)
        minio_client.download_file_to_path(source_key, local_path)

        if original_format == "docx":
            # Convertir DOCX → PDF
            logger.info(f"Convirtiendo {filename} a PDF...")
            pdf_path = convert_docx_to_pdf(local_path, tmpdir)
        else:
            pdf_path = local_path

        # Leer PDF
        with open(pdf_path, "rb") as f:
            pdf_bytes = f.read()

        # Contar páginas
        total_pages = count_pdf_pages(pdf_bytes)
        logger.info(f"Documento {doc_id}: {total_pages} páginas")

        # Subir PDF a MinIO
        pdf_key = f"pdf/{doc_id}/{Path(filename).stem}.pdf"
        minio_client.upload_file(pdf_key, pdf_bytes, content_type="application/pdf")

        return {
            "pdf_uri": pdf_key,
            "total_pages": total_pages,
        }
