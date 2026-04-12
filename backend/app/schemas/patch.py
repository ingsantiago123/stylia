"""
Schemas para parches / correcciones.
"""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class PatchOperation(BaseModel):
    """Una operación individual de corrección."""
    offset: int
    length: int
    original: str
    replacement: str | None = None
    rule_id: str | None = None
    category: str | None = None
    message: str | None = None


class PatchListItem(BaseModel):
    """Item de lista de parches."""
    id: UUID
    block_id: UUID
    block_no: int | None = None
    version: int
    source: str
    original_text: str
    corrected_text: str
    review_status: str
    overflow_flag: bool = False
    created_at: datetime
    # MVP2 — campos enriquecidos
    category: str | None = None
    severity: str | None = None
    explanation: str | None = None
    confidence: float | None = None
    rewrite_ratio: float | None = None
    pass_number: int | None = None
    model_used: str | None = None
    # Costo de la llamada LLM asociada
    cost_usd: float | None = None
    # Lote 4: ruta del complexity router
    route_taken: str | None = None
    # Lote 5: quality gates
    gate_results: list[dict] | None = None
    review_reason: str | None = None
    # Fase 1: auditoría de revisión humana
    reviewed_at: datetime | None = None
    reviewer_note: str | None = None
    decision_source: str = "system"
    # Edición manual y recorrección
    edited_text: str | None = None
    edited_at: datetime | None = None
    recorrection_count: int = 0

    model_config = {"from_attributes": True}


class PatchDetail(BaseModel):
    """Detalle completo de un parche."""
    id: UUID
    block_id: UUID
    block_no: int | None = None
    version: int
    source: str
    original_text: str
    corrected_text: str
    operations_json: list[dict] = []
    qa_score: float | None = None
    overflow_flag: bool = False
    font_adjusted: bool = False
    review_status: str
    applied: bool = False
    created_at: datetime
    # MVP2 — campos enriquecidos
    category: str | None = None
    severity: str | None = None
    explanation: str | None = None
    confidence: float | None = None
    rewrite_ratio: float | None = None
    pass_number: int | None = None
    model_used: str | None = None
    route_taken: str | None = None
    gate_results: list[dict] | None = None
    review_reason: str | None = None
    # Fase 1: auditoría de revisión humana
    reviewed_at: datetime | None = None
    reviewer_note: str | None = None
    decision_source: str = "system"
    # Edición manual y recorrección
    edited_text: str | None = None
    edited_at: datetime | None = None
    recorrection_count: int = 0

    model_config = {"from_attributes": True}


# =============================================
# Schemas para revisión humana (Human-in-the-Loop)
# =============================================

class PatchReviewAction(BaseModel):
    """Acción de revisión sobre un patch individual."""
    action: Literal["accepted", "rejected"]
    reviewer_note: str | None = Field(None, max_length=500)


class BulkPatchReviewAction(BaseModel):
    """Acción de revisión sobre múltiples patches."""
    patch_ids: list[UUID]
    action: Literal["accepted", "rejected"]
    reviewer_note: str | None = Field(None, max_length=500)


class FinalizeRequest(BaseModel):
    """Solicitud para finalizar revisión y aplicar correcciones."""
    mode: Literal["quick", "strict"] = "quick"
    # quick: finaliza aunque haya pendientes → pendientes se convierten en bulk_finalized
    # strict: requiere 0 pendientes y 0 manual_review para finalizar
    apply_mode: Literal["accepted_only", "accepted_and_auto"] = "accepted_and_auto"


class ManualEditRequest(BaseModel):
    """Edición manual del texto corregido de un patch."""
    edited_text: str = Field(..., min_length=1, max_length=10000)
    reviewer_note: str | None = Field(None, max_length=500)


class RecorrectionRequest(BaseModel):
    """Solicitud de recorrección IA para un patch individual."""
    feedback: str = Field(..., min_length=3, max_length=1000)


class ReviewSummary(BaseModel):
    """Resumen del estado de revisión de un documento."""
    total_patches: int = 0
    auto_accepted: int = 0
    pending: int = 0
    accepted: int = 0
    rejected: int = 0
    manual_review: int = 0
    gate_rejected: int = 0
    bulk_finalized: int = 0
    can_finalize_strict: bool = False
    can_finalize_quick: bool = True
    render_version: int = 1
    # Desglose por severidad
    by_severity: dict[str, int] = {}
    # Desglose por página
    by_page: dict[int, dict[str, int]] = {}
