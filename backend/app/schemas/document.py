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


class ProgressDetail(BaseModel):
    """Detalle granular del progreso de procesamiento."""
    stage: str | None = None
    stage_label: str | None = None
    stage_current: int | None = None
    stage_total: int | None = None
    message: str | None = None
    eta_seconds: float | None = None
    is_stalled: bool = False
    heartbeat_at: datetime | None = None
    stage_started_at: datetime | None = None


class DocumentListItem(BaseModel):
    """Item de la lista de documentos (dashboard)."""
    id: UUID
    filename: str
    original_format: str
    status: str
    total_pages: int | None = None
    created_at: datetime
    progress: float = Field(default=0.0, ge=0.0, le=1.0, description="0.0 a 1.0")
    progress_detail: ProgressDetail | None = None

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
    progress_detail: ProgressDetail | None = None
    pages_summary: dict = Field(default_factory=dict, description="Resumen de estados de páginas")
    # Token usage & cost
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    llm_cost_usd: float | None = None
    # Processing time tracking
    processing_started_at: datetime | None = None
    processing_completed_at: datetime | None = None
    stage_timings: dict | None = None
    worker_hostname: str | None = None

    model_config = {"from_attributes": True}


class DocumentConfigUpdate(BaseModel):
    """Actualización de configuración de un documento."""
    language: str | None = "es"
    custom_dictionary: list[str] = []
    glossary: dict[str, str] = {}
    perfeccionista: bool = True
    lt_disabled_rules: list[str] = []


# =============================================
# Schemas de costos (LlmUsage)
# =============================================

class CostSummary(BaseModel):
    """Resumen global de costos de todos los documentos."""
    total_cost_usd: float
    total_prompt_tokens: int
    total_completion_tokens: int
    total_tokens: int
    total_documents: int
    total_calls: int
    avg_cost_per_document: float
    avg_cost_per_call: float
    model_breakdown: list[dict]
    pricing: dict


class DocumentCostItem(BaseModel):
    """Fila de costo por documento."""
    doc_id: UUID
    filename: str
    status: str
    total_pages: int | None = None
    total_calls: int
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    total_cost_usd: float
    created_at: datetime


class ParagraphCostItem(BaseModel):
    """Costo individual de una llamada LLM por párrafo."""
    id: UUID
    paragraph_index: int
    location: str
    call_type: str
    model_used: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost_usd: float
    created_at: datetime

    model_config = {"from_attributes": True}


# =============================================
# Schema de corrección paralela por lotes
# =============================================

class CorrectionBatchStatus(BaseModel):
    """Estado de un lote de corrección paralela."""
    batch_index: int
    start_paragraph: int
    end_paragraph: int
    paragraphs_total: int
    paragraphs_corrected: int
    patches_count: int
    status: str  # pending|running|completed|failed
    lt_pass_completed: bool
    llm_pass_completed: bool
    boundary_checked: bool
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error_message: str | None = None

    model_config = {"from_attributes": True}
