"""
Modelo Patch — Correcciones propuestas por LanguageTool o LLM.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Integer, Float, Text, Boolean, DateTime, ForeignKey, UniqueConstraint, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Patch(Base):
    __tablename__ = "patches"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    block_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("blocks.id", ondelete="CASCADE"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    source: Mapped[str] = mapped_column(
        String(20), nullable=False, comment="'languagetool', 'llm', 'manual'"
    )
    original_text: Mapped[str] = mapped_column(Text, nullable=False)
    corrected_text: Mapped[str] = mapped_column(Text, nullable=False)
    operations_json: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=list, comment="Lista de operaciones"
    )
    qa_score: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="0.0 a 1.0"
    )
    overflow_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    font_adjusted: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False,
        comment="Si se redujo fuente para caber"
    )
    review_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="auto_accepted",
        comment="auto_accepted, pending, accepted, rejected, manual_review, gate_rejected, bulk_finalized"
    )
    applied: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # MVP2 — campos enriquecidos
    category: Mapped[str | None] = mapped_column(
        String(30), nullable=True,
        comment="coherencia|cohesion|lexico|registro|claridad|redundancia|estructura|puntuacion|ritmo|muletilla"
    )
    severity: Mapped[str | None] = mapped_column(
        String(15), nullable=True,
        comment="critico|importante|sugerencia"
    )
    explanation: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        comment="Razón del cambio en español"
    )
    confidence: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="0.0 a 1.0 — confianza del modelo"
    )
    rewrite_ratio: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="0.0 a 1.0 — ratio de reescritura"
    )
    pass_number: Mapped[int | None] = mapped_column(
        Integer, nullable=True,
        comment="1=LanguageTool, 2=léxica, 3=estilística"
    )
    model_used: Mapped[str | None] = mapped_column(
        String(50), nullable=True,
        comment="gpt-4o-mini, claude-sonnet-4-5, languagetool"
    )
    paragraph_index: Mapped[int | None] = mapped_column(
        Integer, nullable=True,
        comment="Índice del párrafo en el DOCX, para vincular con llm_usage"
    )
    route_taken: Mapped[str | None] = mapped_column(
        String(15), nullable=True,
        comment="skip|cheap|editorial — ruta del complexity router (Lote 4)"
    )
    # Lote 5: Quality Gates
    gate_results: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True,
        comment="Lista de resultados de quality gates [{gate_name, passed, value, threshold, message}]"
    )
    review_reason: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        comment="Razón del review_status (gates fallidos)"
    )
    # Fase 1 MVP2-FIX: Auditoría de revisión humana
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
        comment="Cuándo se revisó (aceptó/rechazó) este patch"
    )
    reviewer_note: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        comment="Nota del revisor humano"
    )
    decision_source: Mapped[str] = mapped_column(
        String(30), nullable=False, default="system",
        server_default="system",
        comment="system | human | bulk_finalize | manual_edit | ai_recorrection"
    )
    # Edición manual del texto corregido
    edited_text: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        comment="Texto editado manualmente por el usuario (reemplaza corrected_text en render)"
    )
    edited_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
        comment="Cuándo se editó manualmente"
    )
    # Recorrección IA
    recorrection_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0",
        comment="Veces que se ha recorregido este patch con IA"
    )
    recorrection_note: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        comment="Último feedback del usuario para recorrección IA"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    block: Mapped["Block"] = relationship("Block", back_populates="patches")  # noqa: F821

    __table_args__ = (
        UniqueConstraint("block_id", "version", name="uq_patches_block_version"),
        Index("idx_patches_review", "review_status"),
    )

    def __repr__(self) -> str:
        return f"<Patch block={self.block_id} v{self.version} [{self.review_status}]>"
