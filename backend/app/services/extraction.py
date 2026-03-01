"""
Servicio de Extracción de Layout (Etapa B).
Extrae bloques de texto con posición, fuente y contenido de cada página del PDF.
MVP 1: Solo PyMuPDF get_text("dict") para PDFs born-digital.
"""

import json
import logging

from app.utils import minio_client
from app.utils.pdf_utils import extract_page_text_blocks, render_page_preview

logger = logging.getLogger(__name__)


def extract_page_layout_sync(doc_id: str, pdf_uri: str, page_no: int) -> dict:
    """
    Extracción síncrona del layout de una página (ejecutada por Celery worker).
    
    1. Descarga el PDF de MinIO
    2. Extrae bloques de texto con PyMuPDF
    3. Genera preview PNG
    4. Sube artefactos a MinIO
    
    Retorna dict con URIs y bloques para actualizar la BD.
    """
    # Descargar PDF
    pdf_bytes = minio_client.download_file(pdf_uri)

    # Extraer bloques (page_no es 1-indexed en BD, 0-indexed en PyMuPDF)
    page_idx = page_no - 1
    blocks = extract_page_text_blocks(pdf_bytes, page_idx)

    # Separar bloques de texto e imagen
    text_blocks = [b for b in blocks if b["type"] == "text"]
    image_blocks = [b for b in blocks if b["type"] == "image"]

    # Construir texto plano de la página
    full_text = "\n".join(b["text"] for b in text_blocks if b.get("text"))

    # Generar layout JSON
    layout = {
        "page_no": page_no,
        "total_blocks": len(blocks),
        "text_blocks_count": len(text_blocks),
        "image_blocks_count": len(image_blocks),
        "blocks": blocks,
    }

    # Subir layout JSON a MinIO
    layout_key = f"pages/{doc_id}/layout/{page_no}.json"
    layout_bytes = json.dumps(layout, ensure_ascii=False, indent=2).encode("utf-8")
    minio_client.upload_file(layout_key, layout_bytes, content_type="application/json")

    # Subir texto plano
    text_key = f"pages/{doc_id}/text/{page_no}.txt"
    minio_client.upload_file(text_key, full_text.encode("utf-8"), content_type="text/plain")

    # Generar y subir preview
    preview_key = f"pages/{doc_id}/preview/{page_no}.png"
    preview_bytes = render_page_preview(pdf_bytes, page_idx, dpi=150)
    minio_client.upload_file(preview_key, preview_bytes, content_type="image/png")

    logger.info(
        f"Página {page_no} extraída: {len(text_blocks)} bloques de texto, "
        f"{len(image_blocks)} imágenes"
    )

    return {
        "layout_uri": layout_key,
        "text_uri": text_key,
        "preview_uri": preview_key,
        "blocks": text_blocks,
        "full_text": full_text,
    }
