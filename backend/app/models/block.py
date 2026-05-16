"""
Modelo Block — Bloque de contenido dentro de una página.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Integer, Float, Boolean, Text, DateTime, ForeignKey, UniqueConstraint, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Block(Base):
    __tablename__ = "blocks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    page_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pages.id", ondelete="CASCADE"), nullable=False
    )
    block_no: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Orden dentro de la página"
    )
    block_type: Mapped[str] = mapped_column(
        String(20), nullable=False, comment="'text', 'image', 'table', 'header', 'footer'"
    )
    bbox_x0: Mapped[float] = mapped_column(Float, nullable=False)
    bbox_y0: Mapped[float] = mapped_column(Float, nullable=False)
    bbox_x1: Mapped[float] = mapped_column(Float, nullable=False)
    bbox_y1: Mapped[float] = mapped_column(Float, nullable=False)
    original_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    font_info: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True,
        comment='[{"font": "Arial-BoldMT", "size": 12, "color": "#000000", "flags": 20}]'
    )

    # MVP2 Lote 3: Análisis editorial
    paragraph_type: Mapped[str | None] = mapped_column(
        String(30), nullable=True,
        comment="titulo|subtitulo|narrativo|explicacion_tecnica|dialogo|cita|lista|celda_tabla|encabezado|footer"
    )
    requires_llm: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True,
        comment="Si este bloque necesita corrección LLM"
    )
    section_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("section_summaries.id", ondelete="SET NULL"),
        nullable=True,
    )

    # === Sub-etapa B.5 extraction_docx — Conciencia estructural (Nivel 2/3) ===
    # Todos nullable: retrocompatible con documentos viejos.
    docx_location: Mapped[str | None] = mapped_column(
        String(80), nullable=True,
        comment="Location DOCX nativa (body:N | table:T:R:C:P | header:S:P | footer:S:P)",
    )
    style_name: Mapped[str | None] = mapped_column(String(80), nullable=True)
    style_level: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Listas
    list_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    list_position: Mapped[int | None] = mapped_column(Integer, nullable=True)
    list_total: Mapped[int | None] = mapped_column(Integer, nullable=True)
    list_format_type: Mapped[str | None] = mapped_column(
        String(20), nullable=True,
        comment="bullet|decimal|lowerLetter|upperLetter|lowerRoman|upperRoman|mixed",
    )
    list_level: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Tablas
    table_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    row_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    column_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    row_total: Mapped[int | None] = mapped_column(Integer, nullable=True)
    col_total: Mapped[int | None] = mapped_column(Integer, nullable=True)
    table_cell_role: Mapped[str | None] = mapped_column(
        String(15), nullable=True,
        comment="header|data|total|caption_row",
    )

    # FK opcional al ElementGroup (definido en element_group.py).
    # No declaramos ForeignKey aquí para evitar dependencias circulares al
    # importar el modelo; la integridad referencial se mantiene a nivel app.
    element_group_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    page: Mapped["Page"] = relationship("Page", back_populates="blocks")  # noqa: F821
    patches: Mapped[list["Patch"]] = relationship(  # noqa: F821
        "Patch", back_populates="block", cascade="all, delete-orphan",
        order_by="Patch.version"
    )

    __table_args__ = (
        UniqueConstraint("page_id", "block_no", name="uq_blocks_page_block"),
        Index("idx_blocks_page", "page_id"),
        Index("idx_blocks_list", "list_id"),
        Index("idx_blocks_table", "table_id"),
        Index("idx_blocks_group", "element_group_id"),
        Index("idx_blocks_style", "style_name"),
    )

    def __repr__(self) -> str:
        return f"<Block page={self.page_id} no={self.block_no} type={self.block_type}>"
