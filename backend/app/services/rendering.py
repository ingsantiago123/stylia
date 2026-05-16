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

from difflib import SequenceMatcher

import fitz  # PyMuPDF
from docx import Document as DocxDocument
from docx.oxml.ns import qn

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


def _compute_deleted_phrases_in_original(
    original: str, corrected: str, context_words: int = 2, min_len: int = 5
) -> list[str]:
    """
    Diff a nivel de palabras: devuelve frases del texto ORIGINAL que fueron
    eliminadas o reemplazadas, con palabras de contexto para unicidad en búsqueda PDF.
    """
    orig_words = original.split()
    corr_words = corrected.split()
    if not orig_words or not corr_words:
        return []
    matcher = SequenceMatcher(None, orig_words, corr_words, autojunk=False)
    phrases: list[str] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag not in ("delete", "replace"):
            continue
        deleted = orig_words[i1:i2]
        if not deleted:
            continue
        ctx_before = orig_words[max(0, i1 - context_words):i1]
        ctx_after = orig_words[i2:min(len(orig_words), i2 + context_words)]
        phrase = " ".join(ctx_before + deleted + ctx_after)
        if len(phrase.strip()) >= min_len:
            phrases.append(phrase.strip())
    return phrases


def _compute_changed_phrases_in_corrected(
    original: str, corrected: str, context_words: int = 2, min_len: int = 5
) -> list[str]:
    """
    Word-level diff: returns context-enriched phrases from the corrected text
    that correspond to changed or inserted word regions.
    context_words = unchanged words included on each side to make the phrase unique.
    """
    orig_words = original.split()
    corr_words = corrected.split()
    if not orig_words or not corr_words:
        return []
    matcher = SequenceMatcher(None, orig_words, corr_words, autojunk=False)
    phrases: list[str] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag not in ("insert", "replace"):
            continue
        changed = corr_words[j1:j2]
        if not changed:
            continue
        ctx_before = corr_words[max(0, j1 - context_words):j1]
        ctx_after = corr_words[j2:min(len(corr_words), j2 + context_words)]
        phrase = " ".join(ctx_before + changed + ctx_after)
        if len(phrase.strip()) >= min_len:
            phrases.append(phrase.strip())
    return phrases


def _generate_annotated_previews(
    doc_id: str,
    corrected_pdf_bytes: bytes,
    all_patches: list[dict],
    render_mode: str = "final",
) -> int:
    """
    Genera previews PNG anotados del PDF corregido.

    Dos capas de anotación por corrección:
    - "paragraph": bbox de la zona del párrafo (outline en frontend, sin highlight baked)
    - "change": bbox exacto de las palabras cambiadas (highlight baked en el PNG)

    render_mode:
    - "candidate": sube a preview_candidate/ y annotations_candidate/
    - "final": sube a preview_corrected/ y annotations/

    Retorna el número total de páginas.
    """
    if render_mode == "candidate":
        preview_prefix = f"pages/{doc_id}/preview_candidate"
        annot_prefix = f"pages/{doc_id}/annotations_candidate"
    else:
        preview_prefix = f"pages/{doc_id}/preview_corrected"
        annot_prefix = f"pages/{doc_id}/annotations"

    pdf_doc = fitz.open(stream=corrected_pdf_bytes, filetype="pdf")
    total_pages = len(pdf_doc)
    page_annotations: dict[int, list] = {p + 1: [] for p in range(total_pages)}
    annotations_found = 0

    total_paragraphs = len(all_patches) or 1

    for patch_idx, patch in enumerate(all_patches):
        orig = patch["original_text"].strip()
        corr = patch["corrected_text"].strip()
        if orig == corr or len(corr) < 3:
            continue

        meta = _get_patch_metadata(patch)
        color = HIGHLIGHT_COLORS.get(meta["category"], DEFAULT_HIGHLIGHT)
        p_ids = patch.get("patch_ids") or ([patch["patch_id"]] if patch.get("patch_id") else [])

        para_idx = patch.get("paragraph_index", patch_idx)
        est_page = min(int(para_idx / total_paragraphs * total_pages), total_pages - 1)
        search_window = 2
        nearby = list(range(max(0, est_page - search_window),
                            min(total_pages, est_page + search_window + 1)))
        remaining = [p for p in range(total_pages) if p not in set(nearby)]

        # Locate the paragraph in the PDF (progressive prefix fallback)
        found_page_idx: int | None = None
        found_quads: list | None = None

        for max_len in [150, 70, 35]:
            search_text = corr[:max_len] if len(corr) > max_len else corr
            if len(search_text) < 4:
                break
            for page_idx in (nearby + remaining):
                quads = pdf_doc[page_idx].search_for(search_text, quads=True)
                if quads:
                    found_page_idx = page_idx
                    found_quads = list(quads)
                    break
            if found_page_idx is not None:
                break

        if found_page_idx is None or not found_quads:
            continue

        annotations_found += 1
        page_no = found_page_idx + 1
        page = pdf_doc[found_page_idx]
        page_rect = page.rect

        ann_base = {
            "patch_ids": p_ids,
            "category": meta["category"],
            "severity": meta["severity"],
            "explanation": meta["explanation"],
            "confidence": patch.get("confidence"),
            "source": patch.get("source", ""),
            "review_status": patch.get("review_status", ""),
            "original_snippet": orig[:100],
            "corrected_snippet": corr[:100],
        }

        # Layer 1: paragraph-level outline (no PDF highlight baked in)
        for quad in found_quads:
            r = quad.rect
            page_annotations[page_no].append({
                **ann_base,
                "annot_type": "paragraph",
                "x_pct": round(r.x0 / page_rect.width * 100, 2),
                "y_pct": round(r.y0 / page_rect.height * 100, 2),
                "w_pct": round((r.x1 - r.x0) / page_rect.width * 100, 2),
                "h_pct": round((r.y1 - r.y0) / page_rect.height * 100, 2),
            })

        # Layer 2: precise changed-word positions (highlight baked into PNG)
        for phrase in _compute_changed_phrases_in_corrected(orig, corr):
            if len(phrase) < 4:
                continue
            change_quads = page.search_for(phrase, quads=True)
            if not change_quads:
                continue
            hl = page.add_highlight_annot(change_quads)
            hl.set_colors(stroke=color)
            hl.set_opacity(0.50)
            hl.update()
            for cquad in change_quads:
                r = cquad.rect
                page_annotations[page_no].append({
                    **ann_base,
                    "annot_type": "change",
                    "x_pct": round(r.x0 / page_rect.width * 100, 2),
                    "y_pct": round(r.y0 / page_rect.height * 100, 2),
                    "w_pct": round((r.x1 - r.x0) / page_rect.width * 100, 2),
                    "h_pct": round((r.y1 - r.y0) / page_rect.height * 100, 2),
                })

    # Render pages as PNG (with baked highlights) and upload with annotation JSON
    for page_idx in range(total_pages):
        page_no = page_idx + 1
        page = pdf_doc[page_idx]
        pix = page.get_pixmap(dpi=150)
        png_bytes = pix.tobytes("png")

        preview_key = f"{preview_prefix}/{page_no}.png"
        minio_client.upload_file(preview_key, png_bytes, content_type="image/png")

        annot_data = json.dumps(
            {"annotations": page_annotations[page_no]},
            ensure_ascii=False,
        )
        annot_key = f"{annot_prefix}/{page_no}.json"
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


def _generate_original_page_annotations(
    doc_id: str,
    original_pdf_bytes: bytes,
    all_patches: list[dict],
) -> None:
    """
    Genera anotaciones JSON para las páginas del PDF ORIGINAL, marcando las
    palabras eliminadas o cambiadas respecto al texto corregido.

    Solo produce JSON (sin modificar el PNG original) en annotations_original/.
    """
    pdf_doc = fitz.open(stream=original_pdf_bytes, filetype="pdf")
    total_pages = len(pdf_doc)
    page_annotations: dict[int, list] = {p + 1: [] for p in range(total_pages)}
    total_paragraphs = len(all_patches) or 1

    for patch_idx, patch in enumerate(all_patches):
        orig = patch["original_text"].strip()
        corr = patch["corrected_text"].strip()
        if orig == corr or len(orig) < 3:
            continue

        meta = _get_patch_metadata(patch)
        p_ids = patch.get("patch_ids") or ([patch["patch_id"]] if patch.get("patch_id") else [])

        para_idx = patch.get("paragraph_index", patch_idx)
        est_page = min(int(para_idx / total_paragraphs * total_pages), total_pages - 1)
        search_window = 2
        nearby = list(range(max(0, est_page - search_window),
                            min(total_pages, est_page + search_window + 1)))
        remaining = [p for p in range(total_pages) if p not in set(nearby)]

        # Localizar el párrafo en el PDF original
        found_page_idx: int | None = None
        found_quads: list | None = None

        for max_len in [150, 70, 35]:
            search_text = orig[:max_len] if len(orig) > max_len else orig
            if len(search_text) < 4:
                break
            for page_idx in (nearby + remaining):
                quads = pdf_doc[page_idx].search_for(search_text, quads=True)
                if quads:
                    found_page_idx = page_idx
                    found_quads = list(quads)
                    break
            if found_page_idx is not None:
                break

        if found_page_idx is None or not found_quads:
            continue

        page_no = found_page_idx + 1
        page = pdf_doc[found_page_idx]
        page_rect = page.rect

        ann_base = {
            "patch_ids": p_ids,
            "category": meta["category"],
            "severity": meta["severity"],
            "explanation": meta["explanation"],
            "confidence": patch.get("confidence"),
            "source": patch.get("source", ""),
            "review_status": patch.get("review_status", ""),
            "original_snippet": orig[:100],
            "corrected_snippet": corr[:100],
        }

        # Contorno del párrafo original (sin relleno en el frontend)
        for quad in found_quads:
            r = quad.rect
            page_annotations[page_no].append({
                **ann_base,
                "annot_type": "paragraph",
                "x_pct": round(r.x0 / page_rect.width * 100, 2),
                "y_pct": round(r.y0 / page_rect.height * 100, 2),
                "w_pct": round((r.x1 - r.x0) / page_rect.width * 100, 2),
                "h_pct": round((r.y1 - r.y0) / page_rect.height * 100, 2),
            })

        # Palabras eliminadas/cambiadas (marcadas en rojo en el frontend)
        for phrase in _compute_deleted_phrases_in_original(orig, corr):
            if len(phrase) < 4:
                continue
            del_quads = page.search_for(phrase, quads=True)
            if not del_quads:
                continue
            for dquad in del_quads:
                r = dquad.rect
                page_annotations[page_no].append({
                    **ann_base,
                    "annot_type": "deleted",
                    "x_pct": round(r.x0 / page_rect.width * 100, 2),
                    "y_pct": round(r.y0 / page_rect.height * 100, 2),
                    "w_pct": round((r.x1 - r.x0) / page_rect.width * 100, 2),
                    "h_pct": round((r.y1 - r.y0) / page_rect.height * 100, 2),
                })

    pdf_doc.close()

    for page_no in range(1, total_pages + 1):
        annot_data = json.dumps(
            {"annotations": page_annotations[page_no]},
            ensure_ascii=False,
        )
        annot_key = f"pages/{doc_id}/annotations_original/{page_no}.json"
        minio_client.upload_file(
            annot_key, annot_data.encode("utf-8"),
            content_type="application/json",
        )

    logger.info(f"Documento {doc_id}: anotaciones originales generadas ({total_pages} páginas)")


_WORD_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def _clear_run_text_preserve_breaks(run) -> None:
    """Elimina elementos w:t del run preservando w:br y otros elementos estructurales."""
    for t_elem in list(run._r.findall(qn('w:t'))):
        run._r.remove(t_elem)


def _get_page_break_info(paragraph) -> tuple[int, int, float] | None:
    """
    Encuentra el salto de página interno en un párrafo.

    Returns (run_idx, text_before_break_len, fraction_before) or None if not found.
    fraction_before: proporción de texto que está ANTES del salto (0.0–1.0).
    """
    total_text = paragraph.text or ""
    total_len = max(len(total_text), 1)
    text_so_far = 0

    for run_idx, run in enumerate(paragraph.runs):
        run_text = run.text or ""
        # Buscar w:br type="page" dentro del run
        for br_elem in run._r.findall(f".//{{{_WORD_NS}}}br"):
            br_type = br_elem.get(f"{{{_WORD_NS}}}type")
            if br_type == "page":
                # Textos en w:t BEFORE el br en este run
                text_before_br = ""
                for child in run._r:
                    tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
                    if tag == "br" and child.get(f"{{{_WORD_NS}}}type") == "page":
                        break
                    if tag == "t":
                        text_before_br += child.text or ""
                text_before_break = text_so_far + len(text_before_br)
                fraction = text_before_break / total_len
                return (run_idx, text_before_break, fraction)
        text_so_far += len(run_text)
    return None


def _apply_text_with_page_break(paragraph, new_text: str, fraction_before: float) -> bool:
    """
    Aplica new_text a un párrafo que contiene un salto de página interno.

    Divide new_text proporcionalmente según fraction_before:
    - Texto antes del salto → runs anteriores al w:br
    - Texto después del salto → runs posteriores al w:br

    Preserva el w:br en su posición original.
    Retorna True si aplicó cambios.
    """
    runs = paragraph.runs
    if not runs:
        return False

    split_pos = max(0, min(int(len(new_text) * fraction_before), len(new_text)))

    # Respetar palabra completa: no cortar en medio de una palabra
    if 0 < split_pos < len(new_text):
        # Buscar el espacio más cercano a la izquierda del split_pos
        space_pos = new_text.rfind(" ", 0, split_pos + 1)
        if space_pos > split_pos - 30:  # solo si el espacio está cerca
            split_pos = space_pos + 1

    text_before = new_text[:split_pos].rstrip()
    text_after = new_text[split_pos:].lstrip()

    # Encontrar el run que contiene el w:br type="page"
    br_run_idx = None
    for i, run in enumerate(runs):
        for br_elem in run._r.findall(f".//{{{_WORD_NS}}}br"):
            if br_elem.get(f"{{{_WORD_NS}}}type") == "page":
                br_run_idx = i
                break
        if br_run_idx is not None:
            break

    if br_run_idx is None:
        # Fallback: no encontró el break, usar comportamiento normal
        runs[0].text = new_text
        for run in runs[1:]:
            _clear_run_text_preserve_breaks(run)
        return True

    # Runs antes del salto: poner text_before en el último run antes del br
    if br_run_idx > 0:
        dominant_before = max(runs[:br_run_idx], key=lambda r: len(r.text or ""))
        _copy_run_format(runs[0], dominant_before)
        runs[0].text = text_before
        for run in runs[1:br_run_idx]:
            _clear_run_text_preserve_breaks(run)
    else:
        # El br está en el run 0: texto_before va en este mismo run (antes del br)
        _set_run_text_before_br(runs[0], text_before)

    # Run del salto: preservar el w:br, poner text_after después de él
    _set_run_text_after_br(runs[br_run_idx], text_after)

    # Runs después del salto: limpiar
    for run in runs[br_run_idx + 1:]:
        _clear_run_text_preserve_breaks(run)

    return True


def _set_run_text_before_br(run, text: str) -> None:
    """Coloca texto ANTES del primer w:br type="page" en el run, preservando el br."""
    from lxml import etree
    r_elem = run._r
    # Eliminar w:t existentes que estén ANTES del br
    br_pos = None
    for i, child in enumerate(r_elem):
        tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
        if tag == "br" and child.get(f"{{{_WORD_NS}}}type") == "page":
            br_pos = i
            break
        if tag == "t":
            r_elem.remove(child)

    if not text:
        return

    # Insertar w:t con el texto antes del br (o al inicio si no hay br)
    t_elem = etree.SubElement(r_elem, qn("w:t"))
    t_elem.text = text
    if text.startswith(" ") or text.endswith(" "):
        t_elem.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")

    if br_pos is not None:
        # Mover el w:t al índice correcto (antes del br)
        r_elem.remove(t_elem)
        r_elem.insert(br_pos, t_elem)


def _set_run_text_after_br(run, text: str) -> None:
    """Coloca texto DESPUÉS del primer w:br type="page" en el run."""
    from lxml import etree
    r_elem = run._r

    # Eliminar w:t existentes DESPUÉS del br
    br_found = False
    for child in list(r_elem):
        tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
        if br_found and tag == "t":
            r_elem.remove(child)
        if tag == "br" and child.get(f"{{{_WORD_NS}}}type") == "page":
            br_found = True

    if not text:
        return

    # Añadir w:t con texto después (al final del run)
    t_elem = etree.SubElement(r_elem, qn("w:t"))
    t_elem.text = text
    if text.startswith(" ") or text.endswith(" "):
        t_elem.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")


def _copy_run_format(target, source) -> None:
    """Copia propiedades de formato clave de un run origen a un run destino."""
    try:
        if source.bold is not None:
            target.bold = source.bold
        if source.italic is not None:
            target.italic = source.italic
        if source.underline is not None:
            target.underline = source.underline
        if source.font.size is not None:
            target.font.size = source.font.size
        if source.font.name:
            target.font.name = source.font.name
    except Exception:
        pass
    try:
        if source.font.color.type is not None:
            target.font.color.rgb = source.font.color.rgb
    except Exception:
        pass


def _get_hyperlink_text_ranges(paragraph) -> list[tuple[int, int]]:
    """Calcula los rangos (start, end) de offset de texto que están dentro de hipervínculos.
    Si no hay hipervínculos, retorna lista vacía.
    """
    hyperlinks = paragraph._p.findall('.//' + qn('w:hyperlink'))
    if not hyperlinks:
        return []

    ranges: list[tuple[int, int]] = []
    full_text = paragraph.text
    cursor = 0
    for hl in hyperlinks:
        # Concatenar todo el w:t dentro del hyperlink
        link_text = "".join(t.text or "" for t in hl.findall('.//' + qn('w:t')))
        if not link_text:
            continue
        # Localizar el primer match a partir del cursor (handles repetidos)
        idx = full_text.find(link_text, cursor)
        if idx >= 0:
            ranges.append((idx, idx + len(link_text)))
            cursor = idx + len(link_text)
    return ranges


def _modification_overlaps_hyperlink(
    original: str, corrected: str, hl_ranges: list[tuple[int, int]]
) -> bool:
    """True si las regiones modificadas (diff) solapan con alguno de los rangos de hyperlink."""
    if not hl_ranges:
        return False
    matcher = SequenceMatcher(None, original, corrected, autojunk=False)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        # Hay modificación entre i1..i2 del original
        for hl_start, hl_end in hl_ranges:
            if i1 < hl_end and i2 > hl_start:
                return True
    return False


def _apply_text_to_paragraph_runs(paragraph, new_text: str) -> bool:
    """
    Aplica un nuevo texto a un párrafo preservando estructura de formato y elementos XML.

    Reglas de prioridad:
    1. Hipervínculos: si la corrección los toca, omitir (manual_review).
    2. Salto de página interno: dividir new_text proporcionalmente para preservar el corte.
    3. Run único: asignación directa.
    4. Múltiples runs: formato del dominante → run 0 con todo el texto, resto limpio.

    Retorna True si hubo cambios aplicados al párrafo.
    """
    runs = paragraph.runs
    if not runs:
        return False

    old_text = paragraph.text
    if old_text == new_text:
        return False

    # Detección quirúrgica de hipervínculos: solo omitir si la corrección los toca
    hl_ranges = _get_hyperlink_text_ranges(paragraph)
    if hl_ranges and _modification_overlaps_hyperlink(old_text, new_text, hl_ranges):
        logger.info(
            f"Párrafo omitido: la corrección toca un hipervínculo "
            f"(rangos hl={hl_ranges})"
        )
        return False

    # Detección de salto de página interno: dividir texto proporcionalmente
    pb_info = _get_page_break_info(paragraph)
    if pb_info is not None:
        _run_idx, _text_before_len, fraction_before = pb_info
        logger.debug(
            f"Párrafo con salto de página interno "
            f"(fracción antes: {fraction_before:.2f}) — aplicando división proporcional"
        )
        return _apply_text_with_page_break(paragraph, new_text, fraction_before)

    if len(runs) == 1:
        runs[0].text = new_text
        return True

    # Múltiples runs: copiar formato del run con más texto al primer run
    dominant = max(runs, key=lambda r: len(r.text or ""))
    r0 = runs[0]
    if dominant is not r0:
        _copy_run_format(r0, dominant)

    r0.text = new_text

    # Limpiar runs secundarios preservando w:br (saltos de línea/página/columna)
    for run in runs[1:]:
        _clear_run_text_preserve_breaks(run)

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


# =====================================================================
# Nivel 2 — Sanitización de prefijos de viñeta en patches grupales
# =====================================================================
import re as _re_rendering_group

_RENDER_LIST_PREFIX = _re_rendering_group.compile(
    r"^\s*(?:[•·▪‒–—●\-\*]|\d{1,3}[.)]|[a-zA-Z][.)]|[ivxlcdmIVXLCDM]+[.)])\s+"
)


def _strip_list_prefix(text: str) -> str:
    """Quita prefijos de viñeta/numeración que el LLM grupal pudo haber dejado.

    Defensivo: el prompt grupal pide "escribe SOLO el texto del ítem", pero
    si el LLM falla no duplicaremos viñetas en el DOCX final.
    """
    if not text:
        return text
    return _RENDER_LIST_PREFIX.sub("", text, count=1)


def _apply_individual_patch(doc, patch: dict) -> tuple[bool, str]:
    """Aplica un patch individual al DOCX abierto.

    Returns (applied, reason) — reason en {'ok', 'no_paragraph', 'mismatch'}.
    """
    location = patch["location"]
    original_text = patch["original_text"]
    corrected_text = patch["corrected_text"]

    paragraph = _get_paragraph_by_location(doc, location)
    if paragraph is None:
        return False, "no_paragraph"

    current_text = paragraph.text.strip()
    if current_text != original_text:
        return False, "mismatch"

    if _apply_text_to_paragraph_runs(paragraph, corrected_text):
        return True, "ok"
    return False, "ok"  # no rompió, simplemente sin runs


def _apply_group_patches(doc, group_id, patches: list[dict]) -> tuple[int, int]:
    """Aplica un set de patches que pertenecen al mismo grupo.

    Aplica en orden por group_call_index. Si el structural_role indica
    lista MANUAL ("list_item:*:manual"), preserva el prefijo en el texto
    (porque la viñeta es parte del contenido, no del DOCX). En el resto,
    sanitiza defensivamente cualquier prefijo de lista que el LLM haya
    dejado.
    """
    sorted_patches = sorted(
        patches, key=lambda p: p.get("group_call_index", 0) or 0
    )
    applied = 0
    skipped = 0
    for patch in sorted_patches:
        patch_clean = dict(patch)
        role = patch.get("structural_role") or ""
        is_manual = role.endswith(":manual")
        if not is_manual:
            patch_clean["corrected_text"] = _strip_list_prefix(patch["corrected_text"])
        ok, reason = _apply_individual_patch(doc, patch_clean)
        if ok:
            applied += 1
            logger.debug(
                f"Grupo {group_id} idx={patch.get('group_call_index')} aplicado"
            )
        else:
            skipped += 1
            logger.warning(
                f"Grupo {group_id} idx={patch.get('group_call_index')}: {reason}"
            )
    return applied, skipped


def _apply_docx_patches(docx_path: str, patches: list[dict]) -> str:
    """
    Aplica correcciones por párrafo al DOCX original.
    Cada patch tiene {paragraph_index, location, original_text, corrected_text}.

    Para patches con `group_id` no nulo (Nivel 2: corrección grupal de listas
    y tablas), se aplican agrupados y en orden por `group_call_index`, con
    sanitización defensiva de prefijos de viñeta/numeración.

    Verifica que el texto original coincida antes de aplicar.
    Retorna la ruta del DOCX corregido.
    """
    from collections import defaultdict as _dd
    doc = DocxDocument(docx_path)
    changes_count = 0
    skipped_count = 0

    grouped: dict = _dd(list)
    individual: list[dict] = []
    for p in patches:
        if p.get("group_id"):
            grouped[p["group_id"]].append(p)
        else:
            individual.append(p)

    # 1) Grupos primero, para resolver conflictos antes que los individuales
    for gid, gpatches in grouped.items():
        a, s = _apply_group_patches(doc, gid, gpatches)
        changes_count += a
        skipped_count += s

    # 2) Patches individuales (path histórico)
    for patch in individual:
        ok, reason = _apply_individual_patch(doc, patch)
        if ok:
            changes_count += 1
            logger.debug(f"Párrafo {patch['location']} corregido: {patch['source']}")
        else:
            skipped_count += 1
            if reason == "mismatch":
                logger.warning(
                    f"Texto no coincide en {patch['location']}: "
                    f"esperado='{patch['original_text'][:50]}...' "
                    f"actual='{(doc.paragraphs[0].text if doc.paragraphs else '')[:0]}'"
                )
            else:
                logger.warning(f"No se encontró párrafo en ubicación {patch['location']}")

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
    docx_bytes_cached: bytes | None = None,
    apply_mode: str = "all",
    render_mode: str = "final",
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
        # Descargar DOCX original (con cache si disponible)
        local_docx = str(Path(tmpdir) / filename)
        if docx_bytes_cached is not None:
            with open(local_docx, "wb") as _f:
                _f.write(docx_bytes_cached)
        else:
            minio_client.download_file_to_path(docx_uri, local_docx)

        if not all_patches:
            logger.info(f"Documento {doc_id}: sin correcciones que aplicar")
            return {"corrected_docx_uri": None, "corrected_pdf_uri": None, "changes_count": 0}

        # Filtrar patches según apply_mode (Human-in-the-Loop)
        if apply_mode == "accepted_only":
            all_patches = [p for p in all_patches if p.get("review_status") == "accepted"]
        elif apply_mode == "accepted_and_auto":
            all_patches = [
                p for p in all_patches
                if p.get("review_status") in ("accepted", "auto_accepted")
            ]
        # apply_mode == "all" → sin filtro (backward compatible, pipeline original)

        if not all_patches:
            logger.info(f"Documento {doc_id}: sin correcciones aprobadas que aplicar")
            return {"corrected_docx_uri": None, "corrected_pdf_uri": None, "changes_count": 0}

        logger.info(f"Documento {doc_id}: {len(all_patches)} párrafos a corregir (mode={apply_mode})")

        # Aplicar correcciones por párrafo
        corrected_docx_path = _apply_docx_patches(local_docx, all_patches)

        # Convertir DOCX corregido a PDF
        corrected_pdf_path = convert_docx_to_pdf(corrected_docx_path, tmpdir)

        # Generar previews anotados (candidato/final): contorno + palabras cambiadas
        corrected_pdf_bytes = Path(corrected_pdf_path).read_bytes()
        _generate_annotated_previews(doc_id, corrected_pdf_bytes, all_patches, render_mode=render_mode)

        # Generar anotaciones del PDF original: contorno + palabras eliminadas/cambiadas
        stem_inner = Path(filename).stem
        original_pdf_key = f"pdf/{doc_id}/{stem_inner}.pdf"
        try:
            original_pdf_bytes_data = minio_client.download_file(original_pdf_key)
            _generate_original_page_annotations(doc_id, original_pdf_bytes_data, all_patches)
        except Exception as _orig_err:
            logger.warning(f"No se pudieron generar anotaciones originales: {_orig_err}")

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
