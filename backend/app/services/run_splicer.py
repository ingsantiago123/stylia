"""
Fase 6 — Motor de reconstrucción run-level (DIAGNOSTICO_STYLIA.md §2.4).

Aplica un texto corregido a un párrafo DOCX editando SOLO los w:t afectados
por el diff, en lugar de colapsar todos los runs en uno (el comportamiento
anterior, que destruía negritas/cursivas intra-párrafo y duplicaba el texto
de los hipervínculos).

Principios:
  1. Mapa de segmentos: se recorren los hijos del w:p en orden (runs directos
     y runs dentro de w:hyperlink), registrando cada w:t con su intervalo
     [start, end) sobre el texto plano. tabs/breaks son segmentos atómicos de
     1 carácter; drawings/referencias de nota/campos son barreras de ancho 0.
  2. Diff char-level original→corregido (SequenceMatcher). Las operaciones
     'equal' no tocan nada; replace/delete/insert se aplican por segmento.
  3. INVARIANTES duros: ninguna edición puede tocar un tab/break ni cruzar
     una barrera; el texto re-extraído tras aplicar debe ser EXACTAMENTE el
     corregido; el conteo de elementos no-texto no cambia. Cualquier
     violación → rollback (deepcopy del w:p) y se reporta False.
  4. Si la estructura del párrafo no es reconocible (el texto del mapa no
     coincide con paragraph.text), NO se toca: False.

El caller decide qué hacer con False (omitir el párrafo → manual_review).
Nunca hay fallback destructivo dentro de este módulo.
"""

from __future__ import annotations

import copy
import logging
from dataclasses import dataclass
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)

_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
_XML_SPACE = "{http://www.w3.org/XML/1998/namespace}space"

# Elementos de ancho 0 que actúan como barrera (no pueden quedar DENTRO de
# un rango reemplazado/eliminado, porque su posición relativa al texto
# circundante perdería sentido).
_BARRIER_TAGS = {
    f"{_W}drawing", f"{_W}pict", f"{_W}object",
    f"{_W}footnoteReference", f"{_W}endnoteReference",
    f"{_W}fldChar", f"{_W}commentReference",
}

# Elementos atómicos de 1 carácter (coinciden con la semántica de
# paragraph.text de python-docx: tab → '\t', br/cr → '\n').
_CHAR_TAGS = {
    f"{_W}tab": "\t",
    f"{_W}br": "\n",
    f"{_W}cr": "\n",
}


@dataclass
class _Segment:
    kind: str          # 'text' | 'char' | 'barrier'
    elem: object       # w:t / w:tab / w:br / barrera
    start: int         # offset inicial en el texto plano
    end: int           # offset final (start == end para barreras)
    char: str = ""     # para kind='char'


def _walk_segments(p_elem) -> list[_Segment] | None:
    """Construye el mapa de segmentos del párrafo en orden de documento.

    Replica la semántica de Paragraph.text de python-docx 1.1.x:
    runs directos + runs dentro de w:hyperlink. Si encuentra un contenedor
    desconocido QUE CONTIENE TEXTO (fldSimple, sdt inline, smartTag...),
    devuelve None: estructura no soportada, no tocar.
    """
    segments: list[_Segment] = []
    offset = 0

    def _walk_run(r_elem) -> bool:
        nonlocal offset
        for child in r_elem:
            tag = child.tag
            if tag == f"{_W}t":
                text = child.text or ""
                segments.append(_Segment("text", child, offset, offset + len(text)))
                offset += len(text)
            elif tag in _CHAR_TAGS:
                ch = _CHAR_TAGS[tag]
                segments.append(_Segment("char", child, offset, offset + 1, char=ch))
                offset += 1
            elif tag in _BARRIER_TAGS:
                segments.append(_Segment("barrier", child, offset, offset))
            elif tag == f"{_W}rPr":
                continue
            else:
                # Elemento desconocido dentro del run: si aporta texto, la
                # estructura no es segura de editar.
                if child.findall(f".//{_W}t"):
                    return False
        return True

    for child in p_elem:
        tag = child.tag
        if tag == f"{_W}r":
            if not _walk_run(child):
                return None
        elif tag == f"{_W}hyperlink":
            for sub in child:
                if sub.tag == f"{_W}r":
                    if not _walk_run(sub):
                        return None
                elif sub.findall(f".//{_W}t"):
                    return None
        elif tag == f"{_W}pPr":
            continue
        else:
            # bookmarkStart/End, proofErr, etc: ignorar si no aportan texto
            if child.findall(f".//{_W}t"):
                return None

    return segments


def _segments_text(segments: list[_Segment]) -> str:
    parts = []
    for seg in segments:
        if seg.kind == "text":
            parts.append(seg.elem.text or "")
        elif seg.kind == "char":
            parts.append(seg.char)
    return "".join(parts)


def _find_target_segment(text_segs: list[_Segment], i1: int) -> _Segment | None:
    """Segmento de texto donde se inserta el reemplazo que comienza en i1.

    Preferencia: el que contiene i1 estrictamente; luego el que empieza en
    i1 (la inserción precede a su contenido posterior); luego el que termina
    en i1 (la inserción sigue a su contenido).
    """
    for seg in text_segs:
        if seg.start <= i1 < seg.end:
            return seg
    for seg in text_segs:
        if seg.start == i1:
            return seg
    for seg in text_segs:
        if seg.end == i1:
            return seg
    return None


def splice_paragraph_text(paragraph, new_text: str) -> bool:
    """Aplica `new_text` al párrafo editando solo los w:t afectados.

    Returns:
        True  → aplicado y verificado (texto final == new_text exacto).
        False → párrafo INTACTO (estructura no soportada, edición cruza
                una barrera, o la verificación falló y se hizo rollback).
    """
    p_elem = paragraph._p

    segments = _walk_segments(p_elem)
    if segments is None:
        logger.debug("splice: estructura de párrafo no soportada — no se toca")
        return False

    old_text = _segments_text(segments)
    # Sanity: nuestro mapa debe reproducir la semántica de paragraph.text.
    if old_text != paragraph.text:
        logger.debug(
            "splice: mapa de segmentos no coincide con paragraph.text — no se toca"
        )
        return False
    if old_text == new_text:
        return False

    text_segs = [s for s in segments if s.kind == "text"]
    if not text_segs:
        return False

    ops = SequenceMatcher(None, old_text, new_text, autojunk=False).get_opcodes()

    # ── Validación previa: ninguna edición toca chars atómicos ni cruza barreras ──
    for tag, i1, i2, j1, j2 in ops:
        if tag == "equal":
            continue
        for seg in segments:
            if seg.kind == "char":
                # Overlap con tab/br: prohibido (el corte/salto se preserva)
                if i1 < seg.end and i2 > seg.start:
                    logger.info(
                        "splice: edición toca un tab/salto (offset %d-%d) — párrafo omitido",
                        i1, i2,
                    )
                    return False
            elif seg.kind == "barrier":
                # Barrera de ancho 0 estrictamente dentro del rango editado
                if tag in ("replace", "delete") and i1 < seg.start < i2:
                    logger.info(
                        "splice: edición cruza un elemento no-texto (drawing/nota/campo) "
                        "— párrafo omitido",
                    )
                    return False
        if tag in ("replace", "insert"):
            if _find_target_segment(text_segs, i1) is None:
                logger.info("splice: inserción sin segmento de texto adyacente — omitido")
                return False

    # ── Backup para rollback ──
    parent = p_elem.getparent()
    backup = copy.deepcopy(p_elem)

    # ── Construir contenido nuevo por segmento de texto ──
    out: dict[int, list[str]] = {id(seg): [] for seg in text_segs}

    for tag, i1, i2, j1, j2 in ops:
        if tag == "equal":
            for seg in text_segs:
                lo = max(seg.start, i1)
                hi = min(seg.end, i2)
                if lo < hi:
                    out[id(seg)].append(old_text[lo:hi])
        elif tag in ("replace", "insert"):
            target = _find_target_segment(text_segs, i1)
            out[id(target)].append(new_text[j1:j2])
        # 'delete': no aporta nada

    # ── Aplicar ──
    try:
        for seg in text_segs:
            new_seg_text = "".join(out[id(seg)])
            seg.elem.text = new_seg_text
            if new_seg_text != new_seg_text.strip():
                seg.elem.set(_XML_SPACE, "preserve")
            elif seg.elem.get(_XML_SPACE):
                del seg.elem.attrib[_XML_SPACE]

        # ── Verificación post-aplicación (invariantes duros) ──
        verify_segs = _walk_segments(p_elem)
        if verify_segs is None:
            raise ValueError("estructura cambió durante el splice")
        final_text = _segments_text(verify_segs)
        if final_text != new_text:
            raise ValueError(
                f"texto final no coincide (esperado {len(new_text)} chars, "
                f"obtenido {len(final_text)})"
            )
        n_barriers_before = sum(1 for s in segments if s.kind in ("char", "barrier"))
        n_barriers_after = sum(1 for s in verify_segs if s.kind in ("char", "barrier"))
        if n_barriers_before != n_barriers_after:
            raise ValueError("conteo de elementos no-texto cambió")

    except Exception as e:
        # Rollback: restaurar el párrafo original
        logger.warning("splice: verificación falló (%s) — rollback del párrafo", e)
        try:
            if parent is not None:
                parent.replace(p_elem, backup)
        except Exception as re_err:
            logger.error("splice: rollback falló: %s", re_err)
        return False

    return True
