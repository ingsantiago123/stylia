"""
ElementGroup — Grupos estructurales (listas/tablas) detectados en B.5.

Cada lista o tabla del DOCX se persiste como un ElementGroup; los Block
hijos referencian al grupo vía Block.element_group_id. La corrección
grupal genera N patches con el mismo Patch.group_id.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Integer, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ElementGroup(Base):
    __tablename__ = "element_groups"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    group_type: Mapped[str] = mapped_column(
        String(10), nullable=False,
        comment="'list' | 'table'",
    )
    docx_native_id: Mapped[str | None] = mapped_column(
        String(40), nullable=True,
        comment="numId_3 | table_2 — id derivado del DOCX",
    )
    item_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
        comment="Ítems de la lista o celdas de la tabla",
    )
    metadata_json: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True,
        comment=(
            "Lista: {format_type, level, first_item_pos_tag, parallel_structure_hint, "
            "ending_punct_majority, capitalization_majority}. "
            "Tabla: {num_rows, num_cols, header_row, has_totals_row, column_data_type_hints}"
        ),
    )
    section_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("section_summaries.id", ondelete="SET NULL"),
        nullable=True,
    )
    correction_status: Mapped[str] = mapped_column(
        String(15), nullable=False, default="pending",
        server_default="pending",
        comment="pending | in_progress | completed | partial_failure",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        Index("idx_egroups_document", "document_id"),
        Index("idx_egroups_section", "section_id"),
        Index("idx_egroups_type", "group_type"),
    )

    def __repr__(self) -> str:
        return f"<ElementGroup {self.group_type} {self.docx_native_id} ({self.item_count})>"
