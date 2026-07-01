"""
Servicio de Ingesta (Etapa A).
DOCX: guarda en MinIO → convierte a PDF (LibreOffice) → cuenta páginas.
PDF (nativo): guarda en MinIO → valida capa de texto → convierte a DOCX
(pdf2docx) → el resto del pipeline opera sobre ese DOCX y entrega
DOCX + PDF corregidos. PDFs escaneados (sin texto) se rechazan con un
error claro: requieren OCR (fase futura del roadmap).
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


def _pdf_has_text_layer(pdf_bytes: bytes, sample_pages: int = 5, min_chars: int = 100) -> bool:
    """True si el PDF tiene capa de texto extraíble (born-digital).

    Un PDF escaneado (solo imágenes) no puede corregirse sin OCR: se muestrean
    las primeras páginas y se exige un mínimo de caracteres reales.
    """
    import fitz  # PyMuPDF

    pdf = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        total_chars = 0
        for page_idx in range(min(sample_pages, len(pdf))):
            total_chars += len(pdf[page_idx].get_text().strip())
            if total_chars >= min_chars:
                return True
        return total_chars >= min_chars
    finally:
        pdf.close()


def _convert_pdf_to_docx(pdf_path: str, tmpdir: str) -> str:
    """Convierte un PDF digital a DOCX con pdf2docx.

    pdf2docx reconstruye párrafos, tablas y formato básico desde el layout
    (usa PyMuPDF por debajo). Es la vía de entrada al pipeline DOCX-first:
    el resto del sistema (B.5/B.6, corrección, splice, render) no cambia.
    """
    from pdf2docx import Converter

    docx_path = str(Path(tmpdir) / f"{Path(pdf_path).stem}_converted.docx")
    cv = Converter(pdf_path)
    try:
        cv.convert(docx_path)
    finally:
        cv.close()
    if not Path(docx_path).exists():
        raise RuntimeError("pdf2docx no generó el archivo DOCX")
    return docx_path


def process_ingestion_sync(doc_id: str, source_key: str, filename: str, original_format: str) -> dict:
    """
    Procesamiento síncrono de ingesta (ejecutado por Celery worker).

    DOCX: convierte a PDF (LibreOffice) para previews/paginación.
    PDF:  valida capa de texto y convierte a DOCX (pdf2docx); el DOCX
          generado se sube a MinIO y se devuelve como `docx_uri` para que
          el pipeline opere DOCX-first sobre él.

    Retorna dict {pdf_uri, total_pages, docx_uri|None}.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        # Descargar archivo original
        local_path = str(Path(tmpdir) / filename)
        minio_client.download_file_to_path(source_key, local_path)

        docx_uri: str | None = None

        if original_format == "docx":
            # Convertir DOCX → PDF
            logger.info(f"Convirtiendo {filename} a PDF...")
            pdf_path = convert_docx_to_pdf(local_path, tmpdir)
        else:
            # PDF nativo: el PDF original ES la fuente visual
            pdf_path = local_path
            with open(pdf_path, "rb") as f:
                _pdf_probe = f.read()
            if not _pdf_has_text_layer(_pdf_probe):
                raise ValueError(
                    "El PDF no tiene capa de texto (escaneado o solo imágenes). "
                    "La corrección requiere texto extraíble — el soporte OCR "
                    "está planificado para una fase posterior."
                )
            logger.info(f"Convirtiendo {filename} (PDF) a DOCX con pdf2docx...")
            docx_path = _convert_pdf_to_docx(pdf_path, tmpdir)
            docx_key = f"docx/{doc_id}/{Path(filename).stem}_converted.docx"
            with open(docx_path, "rb") as f:
                minio_client.upload_file(
                    docx_key, f.read(),
                    content_type=(
                        "application/vnd.openxmlformats-officedocument"
                        ".wordprocessingml.document"
                    ),
                )
            docx_uri = docx_key
            logger.info(f"Documento {doc_id}: PDF convertido a DOCX → {docx_key}")

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
            "docx_uri": docx_uri,
        }
