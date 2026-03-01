"""
Servicio de Renderizado (Etapa E).
MVP 1: Solo Ruta 1 — DOCX-first.
Aplica correcciones párrafo por párrafo al DOCX, preservando formato de runs.
"""

import json
import logging
import tempfile
from pathlib import Path

from docx import Document as DocxDocument

from app.config import settings
from app.utils import minio_client
from app.utils.pdf_utils import convert_docx_to_pdf

logger = logging.getLogger(__name__)


def _apply_text_to_paragraph_runs(paragraph, new_text: str) -> bool:
    """
    Aplica un nuevo texto a un párrafo preservando el formato del primer run.
    
    python-docx divide el párrafo en runs (fragmentos con formato propio).
    Para aplicar texto corregido sin corromper el formato:
    1. Se pone todo el texto en el primer run
    2. Se vacían los demás runs (para no duplicar texto)
    
    Retorna True si hubo cambios.
    """
    runs = paragraph.runs
    if not runs:
        return False

    old_text = paragraph.text
    if old_text == new_text:
        return False

    # Poner todo el texto corregido en el primer run
    runs[0].text = new_text
    # Vaciar los demás runs para que no dupliquen texto
    for run in runs[1:]:
        run.text = ""

    return True


def _get_paragraph_by_location(doc: DocxDocument, location: str):
    """
    Obtiene un párrafo del documento por su ubicación codificada.
    Formatos: 'body:N', 'table:T:R:C:P', 'header:S:P', 'footer:S:P'
    """
    parts = location.split(":")

    if parts[0] == "body":
        idx = int(parts[1])
        if idx < len(doc.paragraphs):
            return doc.paragraphs[idx]

    elif parts[0] == "table":
        t_idx, r_idx, c_idx, p_idx = int(parts[1]), int(parts[2]), int(parts[3]), int(parts[4])
        if t_idx < len(doc.tables):
            table = doc.tables[t_idx]
            if r_idx < len(table.rows):
                row = table.rows[r_idx]
                if c_idx < len(row.cells):
                    cell = row.cells[c_idx]
                    if p_idx < len(cell.paragraphs):
                        return cell.paragraphs[p_idx]

    elif parts[0] in ("header", "footer"):
        s_idx, p_idx = int(parts[1]), int(parts[2])
        if s_idx < len(doc.sections):
            section = doc.sections[s_idx]
            hf = section.header if parts[0] == "header" else section.footer
            if hf and p_idx < len(hf.paragraphs):
                return hf.paragraphs[p_idx]

    return None


def _apply_docx_patches(docx_path: str, patches: list[dict]) -> str:
    """
    Aplica correcciones por párrafo al DOCX original.
    Cada patch tiene {paragraph_index, location, original_text, corrected_text}.
    
    Verifica que el texto original coincida antes de aplicar.
    Retorna la ruta del DOCX corregido.
    """
    doc = DocxDocument(docx_path)
    changes_count = 0
    skipped_count = 0

    for patch in patches:
        location = patch["location"]
        original_text = patch["original_text"]
        corrected_text = patch["corrected_text"]

        paragraph = _get_paragraph_by_location(doc, location)
        if paragraph is None:
            logger.warning(f"No se encontró párrafo en ubicación {location}")
            skipped_count += 1
            continue

        # Verificar que el texto original coincide
        current_text = paragraph.text.strip()
        if current_text != original_text:
            logger.warning(
                f"Texto no coincide en {location}: "
                f"esperado='{original_text[:50]}...' actual='{current_text[:50]}...'"
            )
            skipped_count += 1
            continue

        # Aplicar corrección preservando formato
        if _apply_text_to_paragraph_runs(paragraph, corrected_text):
            changes_count += 1
            logger.debug(f"Párrafo {location} corregido: {patch['source']}")

    # Guardar DOCX corregido
    output_path = str(Path(docx_path).parent / f"{Path(docx_path).stem}_corrected.docx")
    doc.save(output_path)

    logger.info(
        f"DOCX corregido: {changes_count} párrafos modificados, "
        f"{skipped_count} omitidos → {output_path}"
    )
    return output_path


def render_docx_first_sync(
    doc_id: str,
    docx_uri: str,
    filename: str,
    all_patches: list[dict],
) -> dict:
    """
    Renderizado Ruta 1: DOCX-first.
    1. Descarga el DOCX original
    2. Aplica correcciones párrafo por párrafo (LanguageTool + GPT)
    3. Genera DOCX corregido
    4. Convierte a PDF con LibreOffice
    5. Sube ambos a MinIO
    
    Retorna dict con URIs de los archivos generados.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        # Descargar DOCX original
        local_docx = str(Path(tmpdir) / filename)
        minio_client.download_file_to_path(docx_uri, local_docx)

        if not all_patches:
            logger.info(f"Documento {doc_id}: sin correcciones que aplicar")
            return {"corrected_docx_uri": None, "corrected_pdf_uri": None, "changes_count": 0}

        logger.info(f"Documento {doc_id}: {len(all_patches)} párrafos a corregir")

        # Aplicar correcciones por párrafo
        corrected_docx_path = _apply_docx_patches(local_docx, all_patches)

        # Convertir DOCX corregido a PDF
        corrected_pdf_path = convert_docx_to_pdf(corrected_docx_path, tmpdir)

        # Subir DOCX corregido a MinIO
        stem = Path(filename).stem
        corrected_docx_key = f"docx/{doc_id}/{stem}_corrected.docx"
        with open(corrected_docx_path, "rb") as f:
            minio_client.upload_file(
                corrected_docx_key, f.read(),
                content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            )

        # Subir PDF corregido a MinIO
        corrected_pdf_key = f"final/{doc_id}/{stem}_corrected.pdf"
        with open(corrected_pdf_path, "rb") as f:
            minio_client.upload_file(
                corrected_pdf_key, f.read(),
                content_type="application/pdf"
            )

        logger.info(
            f"Documento {doc_id} renderizado: "
            f"DOCX → {corrected_docx_key}, PDF → {corrected_pdf_key}"
        )

        return {
            "corrected_docx_uri": corrected_docx_key,
            "corrected_pdf_uri": corrected_pdf_key,
            "changes_count": len(all_patches),
        }
