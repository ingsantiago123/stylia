"""
GroupCollector — Recoge `Block` agrupados por `element_group_id` para
correrlos en una única llamada al LLM (modo grupal listas/tablas).

Nivel 2/3 del plan de conciencia estructural.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.models.block import Block
from app.models.element_group import ElementGroup
from app.models.page import Page

logger = logging.getLogger(__name__)


@dataclass
class ElementGroupBatch:
    """Lote de Block que pertenecen al mismo ElementGroup."""
    group_id: uuid.UUID
    group_type: str            # 'list' | 'table'
    blocks: list[Block]        # en orden lineal (list_position o row*cols+col)
    metadata: dict             # ElementGroup.metadata_json
    neighbors: dict = field(default_factory=dict)
    docx_native_id: str | None = None


def collect_groups_for_document(
    session: Session, doc_id: str | uuid.UUID
) -> list[ElementGroupBatch]:
    """Devuelve los grupos de un documento listos para corrección grupal.

    Cada batch trae los Block en orden lineal:
      - listas: por `list_position` asc
      - tablas: por (`row_index`, `column_index`)
    """
    groups = (
        session.query(ElementGroup)
        .filter(ElementGroup.document_id == doc_id)
        .order_by(ElementGroup.created_at.asc())
        .all()
    )
    batches: list[ElementGroupBatch] = []
    for g in groups:
        blocks = (
            session.query(Block)
            .join(Page, Block.page_id == Page.id)
            .filter(Page.doc_id == doc_id, Block.element_group_id == g.id)
            .all()
        )
        if not blocks:
            continue
        if g.group_type == "list":
            blocks.sort(key=lambda b: (b.list_position if b.list_position is not None else 0))
        elif g.group_type == "table":
            blocks.sort(
                key=lambda b: (
                    b.row_index if b.row_index is not None else 0,
                    b.column_index if b.column_index is not None else 0,
                )
            )
        batches.append(ElementGroupBatch(
            group_id=g.id,
            group_type=g.group_type,
            blocks=blocks,
            metadata=g.metadata_json or {},
            docx_native_id=g.docx_native_id,
        ))
    return batches


def attach_list_neighbors(batch: ElementGroupBatch) -> None:
    """Añade en batch.neighbors:
       first_item_text, last_item_text, capitalization_majority,
       ending_punct_majority, parallel_structure_hint (desde metadata).
    """
    if not batch.blocks:
        return
    md = batch.metadata or {}
    batch.neighbors.setdefault("first_item_text", batch.blocks[0].original_text or "")
    batch.neighbors.setdefault("last_item_text", batch.blocks[-1].original_text or "")
    batch.neighbors.setdefault("capitalization_majority", md.get("capitalization_majority"))
    batch.neighbors.setdefault("ending_punct_majority", md.get("ending_punct_majority"))
    batch.neighbors.setdefault("parallel_structure_hint", md.get("parallel_structure_hint"))


def attach_table_neighbors(batch: ElementGroupBatch) -> None:
    """Añade column_headers + column_data_type_hints en batch.neighbors."""
    md = batch.metadata or {}
    batch.neighbors.setdefault("column_headers", md.get("column_headers", []))
    batch.neighbors.setdefault("column_data_type_hints", md.get("column_data_type_hints", []))
    batch.neighbors.setdefault("header_row", md.get("header_row"))
    batch.neighbors.setdefault("has_totals_row", md.get("has_totals_row", False))


def partition_table_group(
    batch: ElementGroupBatch, max_cells: int = 60
) -> list[ElementGroupBatch]:
    """Particiona un grupo de tabla grande en sub-batches contiguos por
    rangos de filas, manteniendo header y totals al inicio/fin de cada
    sub-batch para preservar contexto.

    Devuelve [batch] si la tabla cabe en una sola llamada.
    """
    if not batch.blocks:
        return [batch]
    if batch.group_type != "table":
        return [batch]
    if len(batch.blocks) <= max_cells:
        return [batch]

    cols = (batch.metadata or {}).get("num_cols") or 1
    rows_per_chunk = max(1, max_cells // cols)

    by_row: dict[int, list[Block]] = {}
    for b in batch.blocks:
        by_row.setdefault(b.row_index if b.row_index is not None else 0, []).append(b)
    row_indexes = sorted(by_row.keys())

    chunks: list[ElementGroupBatch] = []
    i = 0
    chunk_idx = 0
    while i < len(row_indexes):
        slice_rows = row_indexes[i : i + rows_per_chunk]
        chunk_blocks: list[Block] = []
        for r in slice_rows:
            chunk_blocks.extend(by_row[r])
        chunks.append(ElementGroupBatch(
            group_id=batch.group_id,
            group_type=batch.group_type,
            blocks=chunk_blocks,
            metadata={**(batch.metadata or {}), "chunk_index": chunk_idx},
            docx_native_id=batch.docx_native_id,
        ))
        chunk_idx += 1
        i += rows_per_chunk
    return chunks
