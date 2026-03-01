"""
Schemas para documentos.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class DocumentUploadResponse(BaseModel):
    """Respuesta al subir un documento."""
    id: UUID
    filename: str
    original_format: str
    status: str
    message: str = "Documento recibido, procesamiento iniciado."


class DocumentListItem(BaseModel):
    """Item de la lista de documentos (dashboard)."""
    id: UUID
    filename: str
    original_format: str
    status: str
    total_pages: int | None = None
    created_at: datetime
    progress: float = Field(default=0.0, ge=0.0, le=1.0, description="0.0 a 1.0")

    model_config = {"from_attributes": True}


class DocumentDetail(BaseModel):
    """Detalle completo de un documento."""
    id: UUID
    filename: str
    original_format: str
    status: str
    total_pages: int | None = None
    config_json: dict = {}
    error_message: str | None = None
    source_uri: str
    pdf_uri: str | None = None
    docx_uri: str | None = None
    created_at: datetime
    updated_at: datetime
    progress: float = Field(default=0.0, ge=0.0, le=1.0)
    pages_summary: dict = Field(default_factory=dict, description="Resumen de estados de páginas")

    model_config = {"from_attributes": True}


class DocumentConfigUpdate(BaseModel):
    """Actualización de configuración de un documento."""
    language: str | None = "es"
    custom_dictionary: list[str] = []
    glossary: dict[str, str] = {}
    perfeccionista: bool = True
    lt_disabled_rules: list[str] = []
