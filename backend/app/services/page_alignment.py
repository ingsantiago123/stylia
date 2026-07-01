"""
Etapa B.7 — Alineación real PDF ↔ AST (Fase 3 del plan, DIAGNOSTICO_STYLIA.md §2.5).

Alinea el flujo de palabras del PDF (con página real por palabra, vía PyMuPDF)
contra el flujo de tokens de los `document_nodes` en orden de documento, y
escribe `page_start` / `page_end` / `page_break_offset` en cada nodo.

Sustituye las TRES estimaciones lineales `idx/total*páginas` del pipeline:
la página de un párrafo deja de ser una invención y pasa a ser un dato.

Algoritmo: aligner greedy de dos punteros con ventana de resincronización
(O(n), no SequenceMatcher global O(n·m)). Los textos son casi idénticos
(el PDF es proyección del DOCX vía LibreOffice); las divergencias típicas
son guionado de fin de línea, ligaduras y artefactos de extracción, que la
resincronización absorbe.

NO bloqueante: si falla, los nodos quedan sin página y los prompts omiten
el bloque PÁGINA (comportamiento previo).
"""

from __future__ import annotations

import logging
import re

import fitz  # PyMuPDF

from app.models.document_node import DocumentNode

logger = logging.getLogger(__name__)

# Tipos de nodo cuyo texto aparece en el cuerpo del PDF en orden de documento.
# Headers/footers se repiten por página y footnotes saltan al pie: alinearlos
# contaminaría el stream; quedan sin página (no la necesitan para el prompt).
_ALIGNABLE_TYPES = ("paragraph", "heading", "list_item")

_TOKEN_CLEAN_RX = re.compile(r"^\W+|\W+$", re.UNICODE)

# Ventana de resincronización: cuántos tokens adelante buscar cuando los
# punteros divergen (guionado, artefactos OCR-like de extracción).
_RESYNC_WINDOW = 40
# Confirmación: cuántos tokens consecutivos deben coincidir para aceptar
# un punto de resincronización.
_RESYNC_CONFIRM = 2


def _norm_token(tok: str) -> str:
    return _TOKEN_CLEAN_RX.sub("", tok).lower()


def _tokenize_with_offsets(text: str) -> list[tuple[str, int]]:
    """[(token_normalizado, char_offset_inicio)] — solo tokens no vacíos."""
    out: list[tuple[str, int]] = []
    for m in re.finditer(r"\S+", text):
        norm = _norm_token(m.group(0))
        if norm:
            out.append((norm, m.start()))
    return out


def _extract_pdf_tokens(pdf_bytes: bytes) -> list[tuple[str, int]]:
    """[(token_normalizado, page_no_1based)] en orden de lectura del PDF."""
    tokens: list[tuple[str, int]] = []
    pdf = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        for page_idx in range(len(pdf)):
            for w in pdf[page_idx].get_text("words"):
                norm = _norm_token(w[4])
                if norm:
                    tokens.append((norm, page_idx + 1))
    finally:
        pdf.close()
    return tokens


def _match_at(pdf_tokens, node_tokens, i: int, j: int) -> bool:
    """True si hay _RESYNC_CONFIRM coincidencias consecutivas en (i, j)."""
    for k in range(_RESYNC_CONFIRM):
        if i + k >= len(pdf_tokens) or j + k >= len(node_tokens):
            return k > 0  # final de stream: aceptar match parcial
        if pdf_tokens[i + k][0] != node_tokens[j + k][0]:
            return False
    return True


def align_nodes_to_pdf_sync(doc_id: str, pdf_bytes: bytes, session) -> dict[str, dict]:
    """Alinea y persiste page_start/page_end/page_break_offset por nodo.

    Returns:
        Mapa legacy_location → {"page_start", "page_end", "crosses_page",
        "break_offset"} para inyectar en los prompts de la Etapa D.
    """
    from sqlalchemy import select as sa_select

    nodes = session.execute(
        sa_select(DocumentNode)
        .where(
            DocumentNode.doc_id == doc_id,
            DocumentNode.node_type.in_(_ALIGNABLE_TYPES),
            DocumentNode.original_text.isnot(None),
        )
        .order_by(DocumentNode.order_key)
    ).scalars().all()

    if not nodes:
        return {}

    pdf_tokens = _extract_pdf_tokens(pdf_bytes)
    if not pdf_tokens:
        return {}

    # Stream de tokens de nodos: (norm, node_idx, char_offset)
    node_tokens: list[tuple[str, int, int]] = []
    for n_idx, node in enumerate(nodes):
        for norm, off in _tokenize_with_offsets(node.original_text or ""):
            node_tokens.append((norm, n_idx, off))

    if not node_tokens:
        return {}

    # ── Aligner greedy con resincronización ──
    # matches[n_idx] = lista de (char_offset, page_no)
    matches: dict[int, list[tuple[int, int]]] = {}
    i = 0  # puntero PDF
    j = 0  # puntero nodos
    matched_count = 0

    while i < len(pdf_tokens) and j < len(node_tokens):
        if pdf_tokens[i][0] == node_tokens[j][0]:
            norm, n_idx, off = node_tokens[j]
            matches.setdefault(n_idx, []).append((off, pdf_tokens[i][1]))
            matched_count += 1
            i += 1
            j += 1
            continue

        # Resincronizar: buscar el par (di, dj) más cercano que vuelva a
        # coincidir con confirmación, dentro de la ventana.
        found = False
        best = None
        for total in range(1, _RESYNC_WINDOW * 2):
            for di in range(0, min(total, _RESYNC_WINDOW) + 1):
                dj = total - di
                if dj > _RESYNC_WINDOW:
                    continue
                if _match_at(pdf_tokens, node_tokens, i + di, j + dj):
                    best = (di, dj)
                    found = True
                    break
            if found:
                break
        if not found:
            # Stream irrecuperable en esta zona: avanzar ambos punteros
            i += 1
            j += 1
        else:
            i += best[0]
            j += best[1]

    coverage = matched_count / max(len(node_tokens), 1)

    # ── Proyectar a páginas por nodo ──
    page_map: dict[str, dict] = {}
    aligned_nodes = 0
    for n_idx, node in enumerate(nodes):
        toks = matches.get(n_idx)
        if not toks:
            continue
        pages = [p for _, p in toks]
        p_start, p_end = min(pages), max(pages)
        break_offset = None
        if p_end > p_start:
            for off, p in toks:
                if p > p_start:
                    break_offset = off
                    break
        node.page_start = p_start
        node.page_end = p_end
        node.page_break_offset = break_offset
        aligned_nodes += 1
        if node.legacy_location:
            page_map[node.legacy_location] = {
                "page_start": p_start,
                "page_end": p_end,
                "crosses_page": p_end > p_start,
                "break_offset": break_offset,
            }

    session.commit()
    logger.info(
        "B.7 completado: %d/%d nodos con página real (cobertura tokens=%.1f%%)",
        aligned_nodes, len(nodes), coverage * 100,
    )
    return page_map
