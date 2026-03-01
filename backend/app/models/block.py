"""
Modelo Block — Bloque de contenido dentro de una página.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Integer, Float, Text, DateTime, ForeignKey, UniqueConstraint, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Block(Base):
    __tablename__ = "blocks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    page_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pages.id", ondelete="CASCADE"), nullable=False
    )
    block_no: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Orden dentro de la página"
    )
    block_type: Mapped[str] = mapped_column(
        String(20), nullable=False, comment="'text', 'image', 'table', 'header', 'footer'"
    )
    bbox_x0: Mapped[float] = mapped_column(Float, nullable=False)
    bbox_y0: Mapped[float] = mapped_column(Float, nullable=False)
    bbox_x1: Mapped[float] = mapped_column(Float, nullable=False)
    bbox_y1: Mapped[float] = mapped_column(Float, nullable=False)
    original_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    font_info: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True,
        comment='[{"font": "Arial-BoldMT", "size": 12, "color": "#000000", "flags": 20}]'
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    page: Mapped["Page"] = relationship("Page", back_populates="blocks")  # noqa: F821
    patches: Mapped[list["Patch"]] = relationship(  # noqa: F821
        "Patch", back_populates="block", cascade="all, delete-orphan",
        order_by="Patch.version"
    )

    __table_args__ = (
        UniqueConstraint("page_id", "block_no", name="uq_blocks_page_block"),
        Index("idx_blocks_page", "page_id"),
    )

    def __repr__(self) -> str:
        return f"<Block page={self.page_id} no={self.block_no} type={self.block_type}>"
