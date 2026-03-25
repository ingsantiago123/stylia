"""
Modelo DocumentProfile — Perfil editorial asociado a un documento.
Define cómo se corrige: audiencia, registro, tono, nivel de intervención, etc.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Integer, Float, Boolean, Text, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class DocumentProfile(Base):
    __tablename__ = "document_profiles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    doc_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )

    # Origen del perfil
    preset_name: Mapped[str | None] = mapped_column(
        String(50), nullable=True, comment="Nombre del preset base usado"
    )
    source: Mapped[str] = mapped_column(
        String(20), nullable=False, default="preset",
        comment="'user' | 'preset' | 'inferred'"
    )

    # Clasificación del documento
    genre: Mapped[str | None] = mapped_column(String(50), nullable=True)
    subgenre: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Audiencia
    audience_type: Mapped[str | None] = mapped_column(
        String(50), nullable=True, comment="adultos_no_especialistas, niños_6_8, etc."
    )
    audience_age_range: Mapped[str | None] = mapped_column(String(20), nullable=True)
    audience_expertise: Mapped[str] = mapped_column(
        String(20), nullable=False, default="medio",
        comment="bajo | medio | alto | experto"
    )

    # Estilo y tono
    register: Mapped[str] = mapped_column(
        String(30), nullable=False, default="neutro",
        comment="informal_claro | neutro_claro | neutro | formal_claro | formal_tecnico | persuasivo"
    )
    tone: Mapped[str | None] = mapped_column(
        String(30), nullable=True,
        comment="reflexivo | didactico | narrativo | persuasivo | neutro"
    )
    intervention_level: Mapped[str] = mapped_column(
        String(20), nullable=False, default="moderada",
        comment="minima | sutil | moderada | agresiva"
    )

    # Preservación
    preserve_author_voice: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )

    # Límites numéricos
    max_rewrite_ratio: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.30,
        comment="0.0-1.0 — máximo ratio de reescritura permitido"
    )
    max_expansion_ratio: Mapped[float] = mapped_column(
        Float, nullable=False, default=1.10,
        comment="1.0-1.3 — máxima expansión del texto"
    )

    # INFLESZ objetivos
    target_inflesz_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    target_inflesz_max: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Campos JSONB
    style_priorities: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list,
        comment='["claridad", "fluidez", "cohesion", "precision_lexica"]'
    )
    protected_terms: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list,
        comment="Términos que no deben reemplazarse por sinónimos"
    )
    forbidden_changes: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list,
        comment="Tipos de cambio prohibidos"
    )
    lt_disabled_rules: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list,
        comment="Reglas de LanguageTool deshabilitadas"
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    document: Mapped["Document"] = relationship(  # noqa: F821
        "Document", back_populates="profile"
    )

    __table_args__ = (
        Index("idx_profiles_doc_id", "doc_id"),
    )

    def __repr__(self) -> str:
        return f"<DocumentProfile doc={self.doc_id} preset={self.preset_name}>"
