"""
Servicio de Extracción de Layout (Etapa B).
Extrae bloques de texto con posición, fuente y contenido de cada página del PDF.
MVP 1: Solo PyMuPDF get_text("dict") para PDFs born-digital.
"""

import json
import logging
from concurrent.futures import ThreadPoolExecutor

from app.config import settings
from app.utils import minio_client

logger = logging.getLogger(__name__)


def _upload_page_artifacts(
    doc_id: str,
    page_no: int,
    layout_bytes: bytes,
    text_bytes: bytes,
    preview_bytes: bytes,
) -> dict:
    """Upload the 3 page artifacts to MinIO and return their keys."""
    layout_key = f"pages/{doc_id}/layout/{page_no}.json"
    text_key = f"pages/{doc_id}/text/{page_no}.txt"
    preview_key = f"pages/{doc_id}/preview/{page_no}.png"

    minio_client.upload_file(layout_key, layout_bytes, content_type="application/json")
    minio_client.upload_file(text_key, text_bytes, content_type="text/plain")
    minio_client.upload_file(preview_key, preview_bytes, content_type="image/png")

    return {"layout_uri": layout_key, "text_uri": text_key, "preview_uri": preview_key}


def extract_page_layout_sync(doc_id: str, pdf_uri: str, page_no: int) -> dict:
    """
    Extracción síncrona del layout de una página (ejecutada por Celery worker).
    Legacy single-page interface; downloads PDF each time.
    Prefer extract_all_pages_sync for batch processing.
    """
    from app.utils.pdf_utils import extract_page_text_blocks, render_page_preview

    pdf_bytes = minio_client.download_file(pdf_uri)
    page_idx = page_no - 1
    blocks = extract_page_text_blocks(pdf_bytes, page_idx)
    preview_png = render_page_preview(pdf_bytes, page_idx, dpi=150)
    return extract_page_from_bytes(doc_id, blocks, preview_png, page_no)


def extract_page_from_bytes(
    doc_id: str,
    blocks: list[dict],
    preview_png: bytes,
    page_no: int,
) -> dict:
    """
    Process pre-extracted blocks + preview for a single page.
    Uploads artifacts to MinIO and returns result dict.
    """
    text_blocks = [b for b in blocks if b["type"] == "text"]
    image_blocks = [b for b in blocks if b["type"] == "image"]
    full_text = "\n".join(b["text"] for b in text_blocks if b.get("text"))

    layout = {
        "page_no": page_no,
        "total_blocks": len(blocks),
        "text_blocks_count": len(text_blocks),
        "image_blocks_count": len(image_blocks),
        "blocks": blocks,
    }

    layout_bytes = json.dumps(layout, ensure_ascii=False, indent=2).encode("utf-8")
    text_bytes = full_text.encode("utf-8")

    uris = _upload_page_artifacts(doc_id, page_no, layout_bytes, text_bytes, preview_png)

    logger.info(
        f"Página {page_no} extraída: {len(text_blocks)} bloques de texto, "
        f"{len(image_blocks)} imágenes"
    )

    return {
        **uris,
        "blocks": text_blocks,
        "full_text": full_text,
    }


def extract_all_pages_sync(
    doc_id: str,
    pdf_bytes: bytes,
) -> list[dict]:
    """
    Batch extraction: opens PDF once, extracts all pages, uploads artifacts
    concurrently via thread pool.

    Returns list of result dicts (one per page, 1-indexed page_no).
    """
    from app.utils.pdf_utils import extract_and_render_all_pages

    # Single fitz.open for all pages
    all_page_data = extract_and_render_all_pages(pdf_bytes, dpi=150)
    results: list[dict] = []

    max_workers = settings.extraction_upload_workers

    def _process_page(page_idx: int) -> dict:
        page_no = page_idx + 1
        blocks, preview_png = all_page_data[page_idx]
        return extract_page_from_bytes(doc_id, blocks, preview_png, page_no)

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(_process_page, i): i for i in range(len(all_page_data))}
        # Collect in order
        ordered: dict[int, dict] = {}
        for future in futures:
            idx = futures[future]
            ordered[idx] = future.result()
        for i in range(len(all_page_data)):
            results.append(ordered[i])

    logger.info(
        f"Batch extraction: {len(results)} páginas extraídas "
        f"({max_workers} upload workers)"
    )
    return results
