"""
Schemas Pydantic para perfiles editoriales.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class StyleProfileCreate(BaseModel):
    """Crear perfil — desde preset o custom."""
    preset_name: str | None = Field(None, description="Nombre del preset base (ej: 'ensayo', 'infantil_6_8')")
    # Overrides opcionales (se aplican sobre el preset)
    genre: str | None = None
    subgenre: str | None = None
    audience_type: str | None = None
    audience_age_range: str | None = None
    audience_expertise: str | None = None
    register: str | None = None
    tone: str | None = None
    intervention_level: str | None = None
    preserve_author_voice: bool | None = None
    max_rewrite_ratio: float | None = Field(None, ge=0.0, le=1.0)
    max_expansion_ratio: float | None = Field(None, ge=1.0, le=1.5)
    target_inflesz_min: int | None = None
    target_inflesz_max: int | None = None
    style_priorities: list[str] | None = None
    protected_terms: list[str] | None = None
    forbidden_changes: list[str] | None = None
    lt_disabled_rules: list[str] | None = None


class StyleProfileUpdate(BaseModel):
    """Actualizar perfil — todos los campos opcionales."""
    genre: str | None = None
    subgenre: str | None = None
    audience_type: str | None = None
    audience_age_range: str | None = None
    audience_expertise: str | None = None
    register: str | None = None
    tone: str | None = None
    intervention_level: str | None = None
    preserve_author_voice: bool | None = None
    max_rewrite_ratio: float | None = Field(None, ge=0.0, le=1.0)
    max_expansion_ratio: float | None = Field(None, ge=1.0, le=1.5)
    target_inflesz_min: int | None = None
    target_inflesz_max: int | None = None
    style_priorities: list[str] | None = None
    protected_terms: list[str] | None = None
    forbidden_changes: list[str] | None = None
    lt_disabled_rules: list[str] | None = None


class StyleProfileResponse(BaseModel):
    """Perfil completo para respuesta API."""
    id: UUID
    doc_id: UUID
    preset_name: str | None = None
    source: str
    genre: str | None = None
    subgenre: str | None = None
    audience_type: str | None = None
    audience_age_range: str | None = None
    audience_expertise: str = "medio"
    register: str = "neutro"
    tone: str | None = None
    intervention_level: str = "moderada"
    preserve_author_voice: bool = True
    max_rewrite_ratio: float = 0.30
    max_expansion_ratio: float = 1.10
    target_inflesz_min: int | None = None
    target_inflesz_max: int | None = None
    style_priorities: list[str] = []
    protected_terms: list[str] = []
    forbidden_changes: list[str] = []
    lt_disabled_rules: list[str] = []
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PresetListItem(BaseModel):
    """Info de un preset para el selector UI."""
    key: str
    name: str
    description: str
    icon: str
    intervention_level: str
    register: str
