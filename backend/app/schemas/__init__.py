"""
Schemas Pydantic — Request/Response para la API.
"""

from app.schemas.document import (
    DocumentUploadResponse,
    DocumentDetail,
    DocumentListItem,
    DocumentConfigUpdate,
)
from app.schemas.page import PageDetail, PageListItem
from app.schemas.patch import PatchDetail, PatchListItem

__all__ = [
    "DocumentUploadResponse",
    "DocumentDetail",
    "DocumentListItem",
    "DocumentConfigUpdate",
    "PageDetail",
    "PageListItem",
    "PatchDetail",
    "PatchListItem",
]
