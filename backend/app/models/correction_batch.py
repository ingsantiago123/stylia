"""
Modelo CorrectionBatch — Tracking de lotes de corrección paralela (Stage D).
Cada fila representa un lote de párrafos procesados en paralelo por un Celery task.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Integer, Text, Boolean, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class CorrectionBatch(Base):
    __tablename__ = "correction_batches"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    doc_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    batch_index: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="0-based batch index"
    )
    start_paragraph: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Primer índice de párrafo del lote (global DOCX)"
    )
    end_paragraph: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Último índice de párrafo del lote (global DOCX, inclusive)"
    )
    paragraphs_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    paragraphs_corrected: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    patches_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending",
        comment="pending|running|completed|failed"
    )
    celery_task_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    context_seed: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        comment="Seed inicial: texto post-LT del último párrafo del batch anterior (aprox.)"
    )
    last_corrected_text: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        comment="Texto del último párrafo corregido (real) — usado como seed del batch siguiente"
    )
    lt_pass_completed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    llm_pass_completed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    boundary_checked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    __table_args__ = (
        UniqueConstraint("doc_id", "batch_index", name="uq_correction_batches_doc_batch"),
    )

    def __repr__(self) -> str:
        return (
            f"<CorrectionBatch doc={self.doc_id} batch={self.batch_index} "
            f"[{self.status}] {self.start_paragraph}-{self.end_paragraph}>"
        )
