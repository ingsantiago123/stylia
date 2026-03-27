"""
Modelo TermRegistry — Glosario de términos técnicos extraídos del documento.
Etapa C del pipeline (MVP2 Lote 3): análisis editorial.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Integer, Boolean, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class TermRegistry(Base):
    __tablename__ = "term_registry"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    doc_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
    )

    term: Mapped[str] = mapped_column(
        String(200), nullable=False, comment="Término tal como aparece en el texto"
    )
    normalized_form: Mapped[str] = mapped_column(
        String(200), nullable=False, comment="Forma normalizada del término"
    )
    frequency: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, comment="Veces que aparece en el documento"
    )
    first_occurrence_paragraph: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
        comment="Índice del párrafo donde aparece por primera vez"
    )
    is_protected: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False,
        comment="Si el término no debe reemplazarse por sinónimos"
    )
    decision: Mapped[str] = mapped_column(
        String(20), nullable=False, default="use_as_is",
        comment="'use_as_is' | 'normalize_to'"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    document: Mapped["Document"] = relationship(  # noqa: F821
        "Document", back_populates="terms"
    )

    __table_args__ = (
        Index("idx_terms_doc_id", "doc_id"),
        Index("idx_terms_doc_term", "doc_id", "term"),
    )

    def __repr__(self) -> str:
        return f"<TermRegistry doc={self.doc_id} term={self.term} freq={self.frequency}>"
