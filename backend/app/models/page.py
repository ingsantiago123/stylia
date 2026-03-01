"""
Modelo Page — Cada página de un documento.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Integer, DateTime, ForeignKey, UniqueConstraint, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Page(Base):
    __tablename__ = "pages"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    doc_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    page_no: Mapped[int] = mapped_column(Integer, nullable=False, comment="1-indexed")
    page_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default="digital",
        comment="'digital', 'scanned', 'mixed', 'unknown'"
    )
    render_route: Mapped[str | None] = mapped_column(
        String(20), nullable=True,
        comment="'docx_first', 'redact_htmlbox', 'image_overlay'"
    )
    layout_uri: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    text_uri: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    preview_uri: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    output_uri: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending",
        comment="pending→extracting→extracted→correcting→corrected→rendering→rendered→failed"
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
    document: Mapped["Document"] = relationship(  # noqa: F821
        "Document", back_populates="pages"
    )
    blocks: Mapped[list["Block"]] = relationship(  # noqa: F821
        "Block", back_populates="page", cascade="all, delete-orphan",
        order_by="Block.block_no"
    )

    __table_args__ = (
        UniqueConstraint("doc_id", "page_no", name="uq_pages_doc_page"),
        Index("idx_pages_doc_status", "doc_id", "status"),
    )

    def __repr__(self) -> str:
        return f"<Page doc={self.doc_id} no={self.page_no} [{self.status}]>"
