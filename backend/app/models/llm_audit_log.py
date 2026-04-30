"""
LlmAuditLog — Tabla paralela con el payload RAW completo de cada llamada al LLM.
Persiste request + response intactos para auditoría y debugging.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Integer, Text, DateTime, SmallInteger, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class LlmAuditLog(Base):
    __tablename__ = "llm_audit_log"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    doc_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    paragraph_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    location: Mapped[str | None] = mapped_column(
        String(100), nullable=True,
        comment="body:N, table:T:R:C:P, header:S:P, footer:S:P"
    )
    # 1 = Pasada mecánica, 2 = Auditoría contextual, 0 = análisis global C.6
    pass_number: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, default=1,
        comment="0=global_analysis, 1=mechanical_correction, 2=contextual_audit"
    )
    call_purpose: Mapped[str] = mapped_column(
        String(40), nullable=False,
        comment="mechanical_correction | contextual_audit | global_summary"
    )
    model_used: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Payload RAW completo — exactamente como se envió/recibió
    request_payload: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True,
        comment="Solicitud RAW: {model, messages, max_tokens, temperature}"
    )
    response_payload: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True,
        comment="Respuesta RAW: {id, choices, usage, finish_reason}"
    )

    # Métricas
    prompt_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    def __repr__(self) -> str:
        return (
            f"<LlmAuditLog doc={self.doc_id} para={self.paragraph_index} "
            f"pass={self.pass_number} tokens={self.total_tokens}>"
        )
