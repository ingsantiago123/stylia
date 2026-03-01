"""
Schemas para páginas.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class PageListItem(BaseModel):
    """Item de la lista de páginas."""
    id: UUID
    page_no: int
    page_type: str
    render_route: str | None = None
    status: str
    preview_uri: str | None = None
    patches_count: int = 0
    has_corrections: bool = False

    model_config = {"from_attributes": True}


class PageDetail(BaseModel):
    """Detalle de una página con sus bloques y parches."""
    id: UUID
    page_no: int
    page_type: str
    render_route: str | None = None
    status: str
    preview_uri: str | None = None
    layout_uri: str | None = None
    text_uri: str | None = None
    output_uri: str | None = None
    original_text: str | None = None
    corrected_text: str | None = None
    patches_count: int = 0

    model_config = {"from_attributes": True}
