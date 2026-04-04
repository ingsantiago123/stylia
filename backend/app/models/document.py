"""
Modelo Document — Registro de cada documento subido al sistema.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Integer, Float, Text, DateTime, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    original_format: Mapped[str] = mapped_column(
        String(10), nullable=False, comment="'pdf' o 'docx'"
    )
    source_uri: Mapped[str] = mapped_column(
        String(1024), nullable=False, comment="Ruta en MinIO: source/{id}/{filename}"
    )
    pdf_uri: Mapped[str | None] = mapped_column(
        String(1024), nullable=True, comment="Ruta en MinIO del PDF convertido"
    )
    docx_uri: Mapped[str | None] = mapped_column(
        String(1024), nullable=True, comment="Ruta si el original era DOCX"
    )
    total_pages: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="uploaded",
        comment="uploaded→converting→extracting→analyzing→correcting→rendering→completed→failed",
    )
    config_json: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, server_default="{}"
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Granular progress tracking
    progress_stage: Mapped[str | None] = mapped_column(
        String(30), nullable=True, comment="Etapa actual: converting, extracting, etc."
    )
    progress_stage_current: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="Ítems procesados en la etapa actual"
    )
    progress_stage_total: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="Total de ítems en la etapa actual"
    )
    progress_message: Mapped[str | None] = mapped_column(
        String(200), nullable=True, comment="Mensaje legible del progreso actual"
    )
    heartbeat_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="Último heartbeat del worker"
    )
    stage_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="Inicio de la etapa actual"
    )
    # Token usage & cost tracking (MVP2)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    llm_cost_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Processing time tracking
    processing_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="Inicio real del pipeline (Stage A)"
    )
    processing_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="Fin del pipeline (completed o failed)"
    )
    stage_timings: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True, comment="Duración de cada etapa en segundos: {A, B, C, D, E}"
    )
    worker_hostname: Mapped[str | None] = mapped_column(
        String(200), nullable=True, comment="Hostname del worker Celery que procesó el doc"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    pages: Mapped[list["Page"]] = relationship(  # noqa: F821
        "Page", back_populates="document", cascade="all, delete-orphan",
        order_by="Page.page_no"
    )
    jobs: Mapped[list["Job"]] = relationship(  # noqa: F821
        "Job", back_populates="document", cascade="all, delete-orphan"
    )
    profile: Mapped["DocumentProfile | None"] = relationship(  # noqa: F821
        "DocumentProfile", back_populates="document", uselist=False,
        cascade="all, delete-orphan"
    )
    llm_usages: Mapped[list["LlmUsage"]] = relationship(  # noqa: F821
        "LlmUsage", back_populates="document", cascade="all, delete-orphan"
    )
    sections: Mapped[list["SectionSummary"]] = relationship(  # noqa: F821
        "SectionSummary", back_populates="document", cascade="all, delete-orphan",
        order_by="SectionSummary.section_index"
    )
    terms: Mapped[list["TermRegistry"]] = relationship(  # noqa: F821
        "TermRegistry", back_populates="document", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_documents_status", "status"),
    )

    def __repr__(self) -> str:
        return f"<Document {self.filename} [{self.status}]>"
