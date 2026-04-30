"""
DocumentGlobalContext — "ADN editorial" del documento.
Se genera en Etapa C.6 (análisis global) y se usa en prompts de Pasada 2.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Integer, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class DocumentGlobalContext(Base):
    __tablename__ = "document_global_context"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    doc_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    # Resumen global del documento (~300 palabras)
    global_summary: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        comment="Resumen global del documento generado por LLM"
    )
    # Descripción de la voz y estilo del autor
    dominant_voice: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        comment="Descripción de la voz dominante del autor (~80 palabras)"
    )
    # Registro dominante: academico_formal, divulgativo, narrativo_literario, etc.
    dominant_register: Mapped[str | None] = mapped_column(
        String(50), nullable=True,
        comment="Registro base del documento"
    )
    # Temas principales con peso semántico
    key_themes_json: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True,
        comment="[{theme, weight}] — temas detectados con peso"
    )
    # Términos técnicos globales que NO deben tocarse
    protected_globals_json: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True,
        comment="[{term, reason}] — términos técnicos protegidos globalmente"
    )
    # Métricas de estilo
    style_fingerprint_json: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True,
        comment="{avg_sentence_length, passive_voice_ratio, uses_dashes, ...}"
    )

    total_paragraphs: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    document: Mapped["Document"] = relationship(  # noqa: F821
        "Document", back_populates="global_context"
    )

    def __repr__(self) -> str:
        return f"<DocumentGlobalContext doc={self.doc_id} register={self.dominant_register}>"
