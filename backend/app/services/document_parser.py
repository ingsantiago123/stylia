"""
Etapa B.6 — Parser estructural único (Fase 2 del plan, DIAGNOSTICO_STYLIA.md §2.2.2).

Camina `document.xml` con lxml en ORDEN REAL del documento (w:p y w:tbl
intercalados) y produce `document_nodes`: un AST tipado y persistente con
identidad determinista (oxml_path + content_hash).

Captura lo que el pipeline legacy NO ve:
  - tablas anidadas (tabla dentro de celda)
  - cuadros de texto (w:txbxContent)
  - notas al pie / notas al final (footnotes.xml / endnotes.xml)
  - content controls (w:sdt, descendidos transparentemente)
  - celdas combinadas (vMerge/gridSpan resueltos a un solo nodo físico)

`legacy_location` replica el esquema del pipeline actual (body:N,
table:T:R:C:P, header:S:P) SOLO para los elementos que ese pipeline ve,
de modo que las proyecciones (paginación, clasificación) puedan unirse
con blocks/patches por clave exacta, sin matching por texto.

NO bloqueante: si falla, el pipeline continúa con el flujo clásico.
"""

from __future__ import annotations

import hashlib
import io
import logging
import re
import uuid

from docx import Document as DocxDocument

from app.models.document_node import DocumentNode

logger = logging.getLogger(__name__)

_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
_MC = "{http://schemas.openxmlformats.org/markup-compatibility/2006}"

_FOOTNOTES_RELTYPE = (
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/footnotes"
)
_ENDNOTES_RELTYPE = (
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/endnotes"
)

_HEADING_NAME_RX = re.compile(r"(?:heading|t[íi]tulo)\s*(\d)?", re.IGNORECASE)
_TOTAL_KEYWORDS = ("total", "suma", "subtotal", "totales")
_NORM_WS = re.compile(r"\s+")


# =====================================================================
# Utilidades de texto / hash
# =====================================================================

def _content_hash(text: str) -> str:
    norm = _NORM_WS.sub(" ", (text or "")).strip().lower()
    return hashlib.blake2b(norm.encode("utf-8"), digest_size=8).hexdigest()


def _is_excluded(el, stop_el) -> bool:
    """True si `el` está dentro de un txbxContent, mc:Fallback o w:tabs
    ENTRE el elemento y `stop_el` (el párrafo cuyo texto se extrae)."""
    for anc in el.iterancestors():
        if anc is stop_el:
            return False
        tag = anc.tag
        if tag in (f"{_W}txbxContent", f"{_MC}Fallback", f"{_W}tabs", f"{_W}pPr"):
            return True
    return False


def _para_text_and_flags(p_elem) -> tuple[str, dict]:
    """Texto plano de un w:p (coherente con paragraph.text de python-docx:
    w:t + tabs + breaks) y flags estructurales del párrafo.

    Excluye texto dentro de textboxes (son nodos propios) y de mc:Fallback
    (duplicado de mc:Choice en AlternateContent).
    """
    parts: list[str] = []
    flags = {
        "has_hyperlink": False,
        "has_field": False,
        "has_footnote_ref": False,
        "has_drawing": False,
        "has_textbox": False,
        "has_page_break": False,
    }
    for el in p_elem.iter():
        tag = el.tag
        if tag == f"{_W}t":
            if not _is_excluded(el, p_elem):
                parts.append(el.text or "")
        elif tag == f"{_W}tab":
            if not _is_excluded(el, p_elem):
                parts.append("\t")
        elif tag in (f"{_W}br", f"{_W}cr"):
            if not _is_excluded(el, p_elem):
                parts.append("\n")
                if el.get(f"{_W}type") == "page":
                    flags["has_page_break"] = True
        elif tag == f"{_W}hyperlink":
            flags["has_hyperlink"] = True
        elif tag in (f"{_W}fldSimple", f"{_W}fldChar"):
            flags["has_field"] = True
        elif tag == f"{_W}footnoteReference":
            flags["has_footnote_ref"] = True
        elif tag in (f"{_W}drawing", f"{_W}pict"):
            flags["has_drawing"] = True
        elif tag == f"{_W}txbxContent":
            flags["has_textbox"] = True
    return "".join(parts), flags


def _para_numpr(p_elem) -> tuple[int | None, int]:
    ppr = p_elem.find(f"{_W}pPr")
    if ppr is None:
        return None, 0
    numpr = ppr.find(f"{_W}numPr")
    if numpr is None:
        return None, 0
    numid_el = numpr.find(f"{_W}numId")
    ilvl_el = numpr.find(f"{_W}ilvl")
    try:
        num_id = int(numid_el.get(f"{_W}val")) if numid_el is not None else None
    except (TypeError, ValueError):
        num_id = None
    try:
        ilvl = int(ilvl_el.get(f"{_W}val")) if ilvl_el is not None else 0
    except (TypeError, ValueError):
        ilvl = 0
    return num_id, ilvl


def _para_style_id(p_elem) -> str | None:
    ppr = p_elem.find(f"{_W}pPr")
    if ppr is None:
        return None
    pstyle = ppr.find(f"{_W}pStyle")
    if pstyle is None:
        return None
    return pstyle.get(f"{_W}val")


def _build_style_map(doc: DocxDocument) -> dict[str, str]:
    """styleId → nombre legible (p.ej. 'Heading1' → 'heading 1')."""
    style_map: dict[str, str] = {}
    try:
        for st in doc.styles.element.findall(f"{_W}style"):
            sid = st.get(f"{_W}styleId")
            name_el = st.find(f"{_W}name")
            if sid and name_el is not None:
                style_map[sid] = name_el.get(f"{_W}val") or sid
    except Exception:
        pass
    return style_map


def _heading_level(style_name: str | None) -> int | None:
    if not style_name:
        return None
    m = _HEADING_NAME_RX.search(style_name)
    if not m:
        return None
    try:
        return int(m.group(1)) if m.group(1) else 1
    except (TypeError, ValueError):
        return 1


# =====================================================================
# Builder de nodos
# =====================================================================

class _NodeBuilder:
    """Acumula nodos en orden, asignando order_key secuencial."""

    def __init__(self, doc_id, revision: int):
        self.doc_id = uuid.UUID(str(doc_id))
        self.revision = revision
        self.nodes: list[DocumentNode] = []
        self._counter = 0
        self.stats = {
            "paragraphs": 0, "headings": 0, "lists": 0, "list_items": 0,
            "tables": 0, "cells": 0, "footnotes": 0, "textboxes": 0,
            "headers_footers": 0,
        }

    def add(
        self,
        node_type: str,
        oxml_path: str,
        text: str | None = None,
        attrs: dict | None = None,
        parent: DocumentNode | None = None,
        legacy_location: str | None = None,
        depth: int = 0,
    ) -> DocumentNode:
        self._counter += 1
        node = DocumentNode(
            id=uuid.uuid4(),
            doc_id=self.doc_id,
            revision=self.revision,
            parent_id=parent.id if parent is not None else None,
            node_type=node_type,
            order_key=f"{self._counter:08d}",
            depth=depth,
            oxml_path=oxml_path[:160],
            content_hash=_content_hash(text) if text else None,
            legacy_location=legacy_location,
            original_text=text,
            attrs=attrs or {},
        )
        self.nodes.append(node)
        return node


# =====================================================================
# Recorrido del body (orden real del documento)
# =====================================================================

def _iter_block_children(container_elem):
    """Itera hijos w:p y w:tbl en orden, descendiendo transparentemente
    en w:sdt/w:sdtContent. Devuelve tuplas (kind, elem, inside_sdt)."""
    for child in container_elem:
        tag = child.tag
        if tag == f"{_W}p":
            yield ("p", child, False)
        elif tag == f"{_W}tbl":
            yield ("tbl", child, False)
        elif tag == f"{_W}sdt":
            content = child.find(f"{_W}sdtContent")
            if content is not None:
                for kind, el, _ in _iter_block_children(content):
                    yield (kind, el, True)


def _walk_table(
    builder: _NodeBuilder,
    tbl_elem,
    oxml_prefix: str,
    parent: DocumentNode | None,
    depth: int,
    legacy_table_idx: int | None,
    style_map: dict[str, str],
    doc: DocxDocument,
    counters: dict,
) -> None:
    """Procesa una tabla (posiblemente anidada). Celdas vMerge-continuación
    no generan nodo (la celda física vive en su fila de origen)."""
    rows = tbl_elem.findall(f"{_W}tr")
    num_rows = len(rows)

    # Pre-scan: dimensiones de grid y textos por fila para roles
    grid_cols = 0
    row_texts: list[str] = []
    for tr in rows:
        col = 0
        texts = []
        for tc in tr.findall(f"{_W}tc"):
            span = _cell_grid_span(tc)
            col += span
            for p in tc.findall(f"{_W}p"):
                t, _ = _para_text_and_flags(p)
                texts.append(t)
        grid_cols = max(grid_cols, col)
        row_texts.append(" ".join(texts).strip().lower())

    totals_row_idx = None
    if num_rows > 1 and any(k in row_texts[-1] for k in _TOTAL_KEYWORDS):
        totals_row_idx = num_rows - 1

    table_node = builder.add(
        node_type="table",
        oxml_path=f"{oxml_prefix}",
        attrs={
            "num_rows": num_rows,
            "num_cols": grid_cols,
            "totals_row_index": totals_row_idx,
            "nested": parent is not None and parent.node_type == "table_cell",
        },
        parent=parent,
        legacy_location=(f"table:{legacy_table_idx}" if legacy_table_idx is not None else None),
        depth=depth,
    )
    builder.stats["tables"] += 1

    for r_idx, tr in enumerate(rows):
        grid_col = 0
        c_idx = 0
        for tc in tr.findall(f"{_W}tc"):
            span = _cell_grid_span(tc)
            vmerge = _cell_vmerge(tc)
            if vmerge == "continue":
                grid_col += span
                c_idx += 1
                continue

            role = "data"
            if r_idx == 0:
                role = "header"
            elif totals_row_idx is not None and r_idx == totals_row_idx:
                role = "total"

            cell_path = f"{oxml_prefix}/tc[{r_idx},{grid_col}]"
            cell_node = builder.add(
                node_type="table_cell",
                oxml_path=cell_path,
                attrs={
                    "row": r_idx, "col": grid_col,
                    "col_span": span, "role": role,
                },
                parent=table_node,
                depth=depth + 1,
            )
            builder.stats["cells"] += 1

            # Contenido de la celda: párrafos y tablas anidadas, en orden
            p_in_cell = 0
            nested_tbl = 0
            for kind, el, _in_sdt in _iter_block_children(tc):
                if kind == "p":
                    text, flags = _para_text_and_flags(el)
                    legacy = None
                    if legacy_table_idx is not None:
                        legacy = f"table:{legacy_table_idx}:{r_idx}:{c_idx}:{p_in_cell}"
                    if text.strip():
                        builder.add(
                            node_type="paragraph",
                            oxml_path=f"{cell_path}/p[{p_in_cell}]",
                            text=text,
                            attrs={**flags, "in_table": True},
                            parent=cell_node,
                            legacy_location=legacy,
                            depth=depth + 2,
                        )
                        builder.stats["paragraphs"] += 1
                    _collect_textboxes(builder, el, cell_node, depth + 2, counters)
                    p_in_cell += 1
                elif kind == "tbl":
                    # Tabla anidada: invisible para el pipeline legacy
                    _walk_table(
                        builder, el,
                        oxml_prefix=f"{cell_path}/tbl[{nested_tbl}]",
                        parent=cell_node, depth=depth + 2,
                        legacy_table_idx=None,
                        style_map=style_map, doc=doc, counters=counters,
                    )
                    nested_tbl += 1
            grid_col += span
            c_idx += 1


def _cell_grid_span(tc) -> int:
    tcpr = tc.find(f"{_W}tcPr")
    if tcpr is None:
        return 1
    gs = tcpr.find(f"{_W}gridSpan")
    if gs is None:
        return 1
    try:
        return max(1, int(gs.get(f"{_W}val")))
    except (TypeError, ValueError):
        return 1


def _cell_vmerge(tc) -> str | None:
    """'restart' | 'continue' | None."""
    tcpr = tc.find(f"{_W}tcPr")
    if tcpr is None:
        return None
    vm = tcpr.find(f"{_W}vMerge")
    if vm is None:
        return None
    val = vm.get(f"{_W}val")
    return val if val else "continue"


def _collect_textboxes(builder: _NodeBuilder, p_elem, parent, depth: int, counters: dict) -> None:
    """Extrae párrafos dentro de w:txbxContent (cuadros de texto) como nodos
    propios. Excluye los de mc:Fallback (duplicado del mc:Choice)."""
    for txbx in p_elem.iter(f"{_W}txbxContent"):
        skip = False
        for anc in txbx.iterancestors():
            if anc is p_elem:
                break
            if anc.tag == f"{_MC}Fallback":
                skip = True
                break
        if skip:
            continue
        counters["txbx"] += 1
        k = counters["txbx"]
        for j, p in enumerate(txbx.findall(f"{_W}p")):
            text, flags = _para_text_and_flags(p)
            if not text.strip():
                continue
            builder.add(
                node_type="textbox_paragraph",
                oxml_path=f"txbx[{k}]/p[{j}]",
                text=text,
                attrs=flags,
                parent=parent,
                depth=depth + 1,
            )
            builder.stats["textboxes"] += 1


# =====================================================================
# Punto de entrada
# =====================================================================

def parse_document_to_nodes_sync(
    doc_id: str,
    docx_bytes: bytes,
    session,
) -> dict:
    """Parsea el DOCX a `document_nodes`. Borra los nodos previos del
    documento (semántica de re-procesamiento actual) e incrementa revision.

    Returns: resumen {revision, total_nodes, **stats}.
    """
    from sqlalchemy import delete as sa_delete, func, select as sa_select

    doc = DocxDocument(io.BytesIO(docx_bytes))
    body = doc.element.body
    style_map = _build_style_map(doc)

    prev_rev = session.execute(
        sa_select(func.max(DocumentNode.revision)).where(DocumentNode.doc_id == doc_id)
    ).scalar()
    revision = (prev_rev or 0) + 1
    session.execute(sa_delete(DocumentNode).where(DocumentNode.doc_id == doc_id))

    builder = _NodeBuilder(doc_id, revision)
    counters = {"txbx": 0}

    # ── 1) Body en orden real (w:p y w:tbl intercalados, sdt transparente) ──
    body_p_idx = 0      # índice legacy: solo w:p hijos directos del body
    body_tbl_idx = 0    # índice legacy: solo w:tbl hijos directos del body
    raw_p_idx = 0       # índice posicional real (incluye sdt) para oxml_path
    raw_tbl_idx = 0

    # Lista actual en construcción (agrupar list_items consecutivos)
    current_list: DocumentNode | None = None
    current_list_key: tuple | None = None
    current_list_count = 0

    def _close_list():
        nonlocal current_list, current_list_key, current_list_count
        if current_list is not None:
            current_list.attrs = {**current_list.attrs, "item_count": current_list_count}
            builder.stats["lists"] += 1
        current_list = None
        current_list_key = None
        current_list_count = 0

    for kind, el, in_sdt in _iter_block_children(body):
        if kind == "p":
            text, flags = _para_text_and_flags(el)
            num_id, ilvl = _para_numpr(el)
            style_id = _para_style_id(el)
            style_name = style_map.get(style_id, style_id) if style_id else None
            h_level = _heading_level(style_name)

            legacy = None
            if not in_sdt:
                legacy = f"body:{body_p_idx}"
                body_p_idx += 1
            oxml_path = f"body/p[{raw_p_idx}]"
            raw_p_idx += 1

            if num_id is not None and h_level is None and text.strip():
                # Ítem de lista nativa: agrupar en contenedor 'list'
                key = (num_id, ilvl)
                if current_list is None or current_list_key != key:
                    _close_list()
                    current_list = builder.add(
                        node_type="list",
                        oxml_path=f"{oxml_path}#list",
                        attrs={"num_id": num_id, "ilvl": ilvl},
                        depth=0,
                    )
                    current_list_key = key
                builder.add(
                    node_type="list_item",
                    oxml_path=oxml_path,
                    text=text,
                    attrs={
                        **flags, "num_id": num_id, "ilvl": ilvl,
                        "position": current_list_count,
                        "style_name": style_name,
                    },
                    parent=current_list,
                    legacy_location=legacy,
                    depth=1,
                )
                current_list_count += 1
                builder.stats["list_items"] += 1
            else:
                _close_list()
                if text.strip():
                    builder.add(
                        node_type="heading" if h_level else "paragraph",
                        oxml_path=oxml_path,
                        text=text,
                        attrs={
                            **flags,
                            "style_name": style_name,
                            **({"level": h_level} if h_level else {}),
                        },
                        legacy_location=legacy,
                        depth=0,
                    )
                    if h_level:
                        builder.stats["headings"] += 1
                    else:
                        builder.stats["paragraphs"] += 1
            _collect_textboxes(builder, el, None, 0, counters)

        elif kind == "tbl":
            _close_list()
            legacy_idx = None
            if not in_sdt:
                legacy_idx = body_tbl_idx
                body_tbl_idx += 1
            _walk_table(
                builder, el,
                oxml_prefix=f"body/tbl[{raw_tbl_idx}]",
                parent=None, depth=0,
                legacy_table_idx=legacy_idx,
                style_map=style_map, doc=doc, counters=counters,
            )
            raw_tbl_idx += 1
    _close_list()

    # ── 2) Headers / Footers (vía python-docx, legacy-compatible) ──
    try:
        for s_idx, section in enumerate(doc.sections):
            for hf_type, hf in (("header", section.header), ("footer", section.footer)):
                if hf is None:
                    continue
                for p_idx, para in enumerate(hf.paragraphs):
                    text = para.text or ""
                    if not text.strip():
                        continue
                    builder.add(
                        node_type=hf_type,
                        oxml_path=f"{hf_type}[{s_idx}]/p[{p_idx}]",
                        text=text,
                        legacy_location=f"{hf_type}:{s_idx}:{p_idx}",
                        depth=0,
                    )
                    builder.stats["headers_footers"] += 1
    except Exception as e:
        logger.warning("B.6: headers/footers no extraídos: %s", e)

    # ── 3) Footnotes / Endnotes (invisibles para el pipeline legacy) ──
    for reltype, label in ((_FOOTNOTES_RELTYPE, "footnote"), (_ENDNOTES_RELTYPE, "endnote")):
        try:
            part = None
            for rel in doc.part.rels.values():
                if rel.reltype == reltype:
                    part = rel.target_part
                    break
            if part is None:
                continue
            root = part.element if hasattr(part, "element") else part._element
            for fn in root.findall(f"{_W}{label}"):
                fn_type = fn.get(f"{_W}type")
                if fn_type in ("separator", "continuationSeparator", "continuationNotice"):
                    continue
                fn_id = fn.get(f"{_W}id")
                for j, p in enumerate(fn.findall(f"{_W}p")):
                    text, flags = _para_text_and_flags(p)
                    if not text.strip():
                        continue
                    builder.add(
                        node_type="footnote",
                        oxml_path=f"{label}s/{label}[{fn_id}]/p[{j}]",
                        text=text,
                        attrs={**flags, "note_id": fn_id, "note_kind": label},
                        depth=0,
                    )
                    builder.stats["footnotes"] += 1
        except Exception as e:
            logger.warning("B.6: %ss no extraídos: %s", label, e)

    session.add_all(builder.nodes)
    session.commit()

    summary = {
        "revision": revision,
        "total_nodes": len(builder.nodes),
        **builder.stats,
    }
    logger.info("B.6 completado: %s", summary)
    return summary
