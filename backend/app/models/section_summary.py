"""
Modelo SectionSummary — Resumen por sección detectada en el documento.
Etapa C del pipeline (MVP2 Lote 3): análisis editorial.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Integer, Text, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class SectionSummary(Base):
    __tablename__ = "section_summaries"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    doc_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
    )

    section_index: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Orden de la sección en el documento"
    )
    section_title: Mapped[str | None] = mapped_column(
        String(500), nullable=True, comment="Título del heading si existe"
    )
    start_paragraph: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Índice del primer párrafo"
    )
    end_paragraph: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Índice del último párrafo"
    )
    summary_text: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="Resumen ~50 palabras generado por LLM"
    )
    topic: Mapped[str | None] = mapped_column(
        String(200), nullable=True, comment="Tema principal de la sección"
    )
    local_tone: Mapped[str | None] = mapped_column(
        String(30), nullable=True, comment="Tono local de la sección"
    )
    active_terms: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list,
        comment="Términos técnicos activos en esta sección"
    )
    transition_from_previous: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="Cómo conecta con la sección anterior"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    document: Mapped["Document"] = relationship(  # noqa: F821
        "Document", back_populates="sections"
    )

    __table_args__ = (
        Index("idx_sections_doc_id", "doc_id"),
        Index("idx_sections_doc_order", "doc_id", "section_index"),
    )

    def __repr__(self) -> str:
        return f"<SectionSummary doc={self.doc_id} idx={self.section_index} title={self.section_title}>"
