"""
Modelo Document — Registro de cada documento subido al sistema.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Integer, Text, DateTime, Index
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
        comment="uploaded→converting→extracting→correcting→rendering→completed→failed",
    )
    config_json: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, server_default="{}"
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
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

    __table_args__ = (
        Index("idx_documents_status", "status"),
    )

    def __repr__(self) -> str:
        return f"<Document {self.filename} [{self.status}]>"
