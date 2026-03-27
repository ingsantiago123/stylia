"""
Modelo LlmUsage — Registro granular de cada llamada LLM (OpenAI).
Cada fila = una llamada a la API por párrafo durante la corrección.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Integer, Float, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class LlmUsage(Base):
    __tablename__ = "llm_usage"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    doc_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    paragraph_index: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Índice del párrafo en el DOCX"
    )
    location: Mapped[str] = mapped_column(
        String(100), nullable=False, comment="body:N, table:T:R:C:P, header:S:P, footer:S:P"
    )
    call_type: Mapped[str] = mapped_column(
        String(30), nullable=False, comment="correction_mvp1 | correction_mvp2"
    )
    model_used: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="gpt-4o-mini, etc."
    )
    prompt_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cost_usd: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0, comment="Costo en USD calculado al insertar"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    document: Mapped["Document"] = relationship("Document", back_populates="llm_usages")  # noqa: F821

    __table_args__ = (
        Index("idx_llm_usage_doc_id", "doc_id"),
        Index("idx_llm_usage_created", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<LlmUsage doc={self.doc_id} para={self.paragraph_index} tokens={self.total_tokens}>"
