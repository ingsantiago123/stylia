"""
Modelo DocumentNode — AST documental persistente (Fase 1 del plan de
refactorización, ver DIAGNOSTICO_STYLIA.md §2.2).

Un nodo por elemento estructural del DOCX, en ORDEN REAL del documento
(párrafos y tablas intercalados, tablas anidadas, footnotes, textboxes).
La identidad es determinista (oxml_path + content_hash), no probabilística:
sustituye progresivamente al fuzzy matching de texto.

`legacy_location` mantiene compatibilidad con el esquema de ubicaciones del
pipeline actual (body:N | table:T:R:C:P | header:S:P | footer:S:P) para que
las proyecciones (páginas, clasificación) puedan unirse con blocks/patches
sin re-matching por texto.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    String, Integer, Text, DateTime, ForeignKey, UniqueConstraint, Index,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class DocumentNode(Base):
    __tablename__ = "document_nodes"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    doc_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    revision: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1,
        comment="Versión del parse; cada re-procesamiento incrementa",
    )
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("document_nodes.id", ondelete="CASCADE"),
        nullable=True,
    )
    node_type: Mapped[str] = mapped_column(
        String(20), nullable=False,
        comment=(
            "heading|paragraph|list|list_item|table|table_cell|footnote|"
            "header|footer|textbox_paragraph"
        ),
    )
    order_key: Mapped[str] = mapped_column(
        String(16), nullable=False,
        comment="Clave de orden total del documento (zero-padded)",
    )
    depth: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # ── Ancla OXML: identidad determinista ──
    oxml_path: Mapped[str] = mapped_column(
        String(160), nullable=False,
        comment="Path posicional en el XML, p.ej. body/p[17] | body/tbl[2]/tc[3,1]/p[0]",
    )
    content_hash: Mapped[str | None] = mapped_column(
        String(16), nullable=True,
        comment="blake2b-64 hex del texto normalizado (verificación de ancla)",
    )

    # ── Compatibilidad con el pipeline actual ──
    legacy_location: Mapped[str | None] = mapped_column(
        String(80), nullable=True,
        comment="Location del esquema legacy (body:N etc.) si el nodo es visible para él",
    )

    original_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    attrs: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict,
        comment=(
            "Por tipo: heading {style_name, level} · list_item {num_id, ilvl, "
            "fmt, position, total, detection} · table_cell {row, col, row_span, "
            "col_span, role} · paragraph {has_hyperlink, has_field, "
            "has_footnote_ref, has_drawing}"
        ),
    )

    classification: Mapped[str | None] = mapped_column(
        String(30), nullable=True,
        comment="paragraph_type asignado por Etapa C (por node_id, sin matching)",
    )
    skip_reason: Mapped[str | None] = mapped_column(
        String(20), nullable=True,
        comment="protected|field|toc — nodos que jamás se corrigen",
    )

    # ── Proyección de paginación (Fase 3) ──
    page_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    page_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    page_break_offset: Mapped[int | None] = mapped_column(
        Integer, nullable=True,
        comment="Offset de carácter donde cae el cruce de página, si cruza",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    __table_args__ = (
        UniqueConstraint("doc_id", "revision", "oxml_path", name="uq_nodes_doc_rev_path"),
        Index("idx_nodes_doc_order", "doc_id", "revision", "order_key"),
        Index("idx_nodes_legacy_loc", "doc_id", "legacy_location"),
        Index("idx_nodes_parent", "parent_id"),
    )

    def __repr__(self) -> str:
        return f"<DocumentNode {self.node_type} {self.oxml_path}>"
