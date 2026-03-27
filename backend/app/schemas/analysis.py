"""
Schemas para análisis editorial (Etapa C — MVP2 Lote 3).
"""

from uuid import UUID

from pydantic import BaseModel


class SectionSummaryItem(BaseModel):
    """Resumen de una sección detectada."""
    section_index: int
    section_title: str | None = None
    start_paragraph: int
    end_paragraph: int
    summary_text: str | None = None
    topic: str | None = None
    local_tone: str | None = None
    active_terms: list[str] = []
    transition_from_previous: str | None = None

    model_config = {"from_attributes": True}


class TermRegistryItem(BaseModel):
    """Término del glosario extraído."""
    term: str
    normalized_form: str
    frequency: int
    first_occurrence_paragraph: int
    is_protected: bool = False
    decision: str = "use_as_is"

    model_config = {"from_attributes": True}


class ParagraphClassification(BaseModel):
    """Clasificación de un párrafo DOCX."""
    paragraph_index: int
    location: str
    paragraph_type: str
    requires_llm: bool = True
    text_preview: str = ""


class InferredProfile(BaseModel):
    """Campos del perfil inferidos por la Etapa C."""
    genre: str | None = None
    audience_type: str | None = None
    register: str | None = None
    tone: str | None = None
    spanish_variant: str | None = None
    key_terms: list[str] = []
    suggested_intervention: str | None = None


class AnalysisResult(BaseModel):
    """Resultado completo del análisis editorial de un documento."""
    doc_id: UUID
    status: str = "completed"
    inferred_profile: InferredProfile | None = None
    sections: list[SectionSummaryItem] = []
    terms: list[TermRegistryItem] = []
    paragraph_classifications: list[ParagraphClassification] = []
    stats: dict = {}
