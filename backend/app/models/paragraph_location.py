"""
Modelo ParagraphLocation — Mapa canónico paragraph_index → página/posición.

Single source of truth para saber en qué página y posición dentro de la página
está cada párrafo del DOCX. Reemplaza la heurística lineal de rendering.py.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Integer, Boolean, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ParagraphLocation(Base):
    __tablename__ = "paragraph_locations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    doc_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    paragraph_index: Mapped[int] = mapped_column(
        Integer, nullable=False,
        comment="Índice global del párrafo en el DOCX (0-based)"
    )
    location: Mapped[str] = mapped_column(
        String(200), nullable=False,
        comment="body:N | table:T:R:C:P | header:S:P | footer:S:P"
    )
    page_start: Mapped[int | None] = mapped_column(
        Integer, nullable=True,
        comment="Primera página visible donde aparece el párrafo (1-based)"
    )
    page_end: Mapped[int | None] = mapped_column(
        Integer, nullable=True,
        comment="Última página donde aparece (igual a page_start si no cruza páginas)"
    )
    position_in_page: Mapped[str | None] = mapped_column(
        String(10), nullable=True,
        comment="top | middle | bottom según bbox relativo a la altura de página"
    )
    is_continuation_from_prev_page: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False,
        comment="El párrafo viene de la página anterior (detectado por bbox)"
    )
    has_internal_page_break: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False,
        comment="El párrafo contiene <w:br w:type='page'/> interno"
    )
    paragraph_type: Mapped[str | None] = mapped_column(
        String(30), nullable=True,
        comment="Pre-cómputo del clasificador: narrativo|titulo|celda_tabla|etc."
    )
    block_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("blocks.id", ondelete="SET NULL"),
        nullable=True,
        comment="Bloque PDF correspondiente (si se cruzó con extracción)"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    __table_args__ = (
        Index("idx_paragraph_locations_doc_idx", "doc_id", "paragraph_index"),
        Index("idx_paragraph_locations_doc", "doc_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<ParagraphLocation doc={self.doc_id} idx={self.paragraph_index} "
            f"loc={self.location} page={self.page_start} pb={self.has_internal_page_break}>"
        )
