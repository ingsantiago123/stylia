"""
Schemas para parches / correcciones.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


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

    model_config = {"from_attributes": True}
