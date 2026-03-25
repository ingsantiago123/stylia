"""
Servicio de Renderizado (Etapa E).
MVP 1: Solo Ruta 1 — DOCX-first.
Aplica correcciones párrafo por párrafo al DOCX, preservando formato de runs.
MVP 2: Genera previews anotados con highlights sobre texto corregido.
"""

import json
import logging
import tempfile
from pathlib import Path

import fitz  # PyMuPDF
from docx import Document as DocxDocument

from app.utils import minio_client
from app.utils.pdf_utils import convert_docx_to_pdf

logger = logging.getLogger(__name__)


# Colores RGB (0-1) para highlights por categoría editorial
HIGHLIGHT_COLORS = {
    "redundancia": (1.0, 0.65, 0.0),
    "claridad":    (0.3, 0.6, 1.0),
    "registro":    (0.5, 0.4, 1.0),
    "cohesion":    (0.0, 0.75, 0.85),
    "lexico":      (0.0, 0.7, 0.55),
    "estructura":  (0.6, 0.35, 1.0),
    "puntuacion":  (0.95, 0.75, 0.0),
    "ritmo":       (0.9, 0.4, 0.6),
    "muletilla":   (0.9, 0.3, 0.4),
}
DEFAULT_HIGHLIGHT = (0.83, 1.0, 0.0)  # krypton


def _get_patch_metadata(patch: dict) -> dict:
    """Extrae category/severity/explanation de un patch (MVP2 con changes list)."""
    changes = patch.get("changes", [])
    if changes and isinstance(changes, list) and len(changes) > 0:
        first = changes[0]
        return {
            "category": first.get("category", ""),
            "severity": first.get("severity"),
            "explanation": first.get("explanation"),
        }
    return {
        "category": patch.get("category", ""),
        "severity": patch.get("severity"),
        "explanation": patch.get("explanation"),
    }


def _generate_annotated_previews(
    doc_id: str,
    corrected_pdf_bytes: bytes,
    all_patches: list[dict],
) -> int:
    """
    Genera previews PNG anotados del PDF corregido.

    Para cada corrección:
    1. Busca el texto corregido en el PDF con PyMuPDF
    2. Añade highlight con color de categoría
    3. Registra posición (%) para overlay hover en el frontend

    Sube a MinIO:
    - pages/{doc_id}/preview_corrected/{page_no}.png  (PNG con highlights)
    - pages/{doc_id}/annotations/{page_no}.json        (metadata para hover)

    Retorna el número total de páginas.
    """
    pdf_doc = fitz.open(stream=corrected_pdf_bytes, filetype="pdf")
    total_pages = len(pdf_doc)
    page_annotations: dict[int, list] = {p + 1: [] for p in range(total_pages)}
    annotations_found = 0

    for patch in all_patches:
        orig = patch["original_text"].strip()
        corr = patch["corrected_text"].strip()
        if orig == corr or len(corr) < 3:
            continue

        meta = _get_patch_metadata(patch)
        color = HIGHLIGHT_COLORS.get(meta["category"], DEFAULT_HIGHLIGHT)

        # Buscar texto corregido en el PDF (prefijos progresivos)
        found = False
        for max_len in [150, 70, 35]:
            search_text = corr[:max_len] if len(corr) > max_len else corr
            if len(search_text) < 4:
                break

            for page_idx in range(total_pages):
                page = pdf_doc[page_idx]
                quads = page.search_for(search_text, quads=True)

                if quads:
                    # Añadir highlight
                    annot = page.add_highlight_annot(quads)
                    annot.set_colors(stroke=color)
                    annot.set_opacity(0.35)
                    annot.update()
                    annotations_found += 1

                    # Registrar posiciones para overlay frontend
                    page_no = page_idx + 1
                    page_rect = page.rect
                    for quad in quads:
                        r = quad.rect
                        page_annotations[page_no].append({
                            "x_pct": round(r.x0 / page_rect.width * 100, 2),
                            "y_pct": round(r.y0 / page_rect.height * 100, 2),
                            "w_pct": round((r.x1 - r.x0) / page_rect.width * 100, 2),
                            "h_pct": round((r.y1 - r.y0) / page_rect.height * 100, 2),
                            "category": meta["category"],
                            "severity": meta["severity"],
                            "explanation": meta["explanation"],
                            "confidence": patch.get("confidence"),
                            "source": patch.get("source", ""),
                            "original_snippet": orig[:100],
                            "corrected_snippet": corr[:100],
                        })

                    found = True
                    break  # Encontrado en esta página, no buscar más

            if found:
                break  # Encontrado con este prefijo, no probar más cortos

    # Renderizar cada página como PNG (con annotations visibles) y subir
    for page_idx in range(total_pages):
        page_no = page_idx + 1
        page = pdf_doc[page_idx]
        pix = page.get_pixmap(dpi=150)
        png_bytes = pix.tobytes("png")

        # PNG anotado
        preview_key = f"pages/{doc_id}/preview_corrected/{page_no}.png"
        minio_client.upload_file(preview_key, png_bytes, content_type="image/png")

        # Metadata JSON para hover del frontend
        annot_data = json.dumps(
            {"annotations": page_annotations[page_no]},
            ensure_ascii=False,
        )
        annot_key = f"pages/{doc_id}/annotations/{page_no}.json"
        minio_client.upload_file(
            annot_key, annot_data.encode("utf-8"),
            content_type="application/json",
        )

    pdf_doc.close()
    logger.info(
        f"Documento {doc_id}: {total_pages} previews anotados, "
        f"{annotations_found} correcciones marcadas"
    )
    return total_pages


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
    5. Genera previews anotados con highlights (MVP2)
    6. Sube ambos a MinIO

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

        # Generar previews anotados con highlights sobre correcciones
        corrected_pdf_bytes = Path(corrected_pdf_path).read_bytes()
        _generate_annotated_previews(doc_id, corrected_pdf_bytes, all_patches)

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
