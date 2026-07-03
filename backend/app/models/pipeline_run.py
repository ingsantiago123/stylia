"""
Modelo PipelineRun — Fase 4 del plan de refactorización (DIAGNOSTICO_STYLIA.md §2.2.3).

Un registro por ejecución del pipeline de un documento, con checkpoints por
etapa. Objetivo: idempotencia y resumibilidad — un reintento de Celery ya no
re-ejecuta (ni re-paga) las etapas completadas; retoma desde el último
checkpoint. También porta el kill-switch de costo por documento.

checkpoint_json = {
    "A":  {"pdf_uri": ..., "total_pages": N, "docx_uri": ...},
    "B":  {"done": true},
    "B5": {"done": true},
    "B6": {"done": true, "aligned": true},
    "C":  {"analysis_key": ..., "profile": {...}, "global_context": {...}},
    "D":  {"patches_key": ..., "dispatched_parallel": bool},
    "persist": {"done": true},
}
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Integer, Float, Text, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class PipelineRun(Base):
    __tablename__ = "pipeline_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    doc_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    run_no: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1,
        comment="Número de ejecución para este documento (1, 2, ...)",
    )
    celery_task_id: Mapped[str | None] = mapped_column(String(155), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="running",
        comment="running | completed | failed | cost_limit",
    )
    current_stage: Mapped[str | None] = mapped_column(
        String(20), nullable=True,
        comment="Última etapa iniciada: A|B|B5|B6|C|D|D5|persist|E_candidate",
    )
    checkpoint_json: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict,
        comment="Etapa → artefactos/resultados; las etapas presentes se saltan al reanudar",
    )
    retries: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cost_usd: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0,
        comment="Costo LLM acumulado del run (actualizado por etapa)",
    )
    cost_limit_usd: Mapped[float | None] = mapped_column(
        Float, nullable=True,
        comment="Kill-switch: si cost_usd supera este tope, el run aborta",
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        Index("idx_pipeline_runs_doc", "doc_id", "run_no"),
        Index("idx_pipeline_runs_status", "doc_id", "status"),
    )

    def __repr__(self) -> str:
        return f"<PipelineRun doc={self.doc_id} run={self.run_no} {self.status}>"
