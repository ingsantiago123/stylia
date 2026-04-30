"""
Audit Pass — Pasada 2 (Auditoría Contextual).

Recibe texto original + resultado de Pasada 1 + contexto global del documento.
Detecta destrucciones semánticas introducidas por LanguageTool/LLM y las revierte.
Aplica mejoras de estilo coherentes con la voz del autor.
"""

import logging
from typing import Callable

from app.config import settings
from app.services.prompt_builder import AUDIT_SYSTEM_PROMPT, build_audit_user_prompt
from app.utils.openai_client import openai_client

logger = logging.getLogger(__name__)


def audit_paragraph_with_context(
    original_text: str,
    corrected_pass1: str,
    global_context: dict | None,
    context_window: list[str] | None = None,
    paragraph_type: str | None = None,
    location: str | None = None,
    model_override: str | None = None,
    on_audit_log: Callable[[dict], None] | None = None,
) -> tuple[dict | None, dict]:
    """
    Ejecuta la Pasada 2 de auditoría contextual.

    Args:
        original_text: Texto original antes de cualquier corrección
        corrected_pass1: Texto después de Pasada 1 (LT + LLM mecánico)
        global_context: ADN editorial del documento (DocumentGlobalContext.to_dict())
        context_window: Últimos N párrafos ya auditados
        paragraph_type: Tipo del párrafo
        location: Ubicación en el DOCX (body:N, table:T:R:C:P, etc.)
        model_override: Modelo a usar; por defecto el editorial
        on_audit_log: Callback para persistir el payload RAW de la llamada

    Returns:
        Tupla (audit_result_dict, usage_dict).
        audit_result_dict tiene: final_text, reverted_destructions, style_improvements, confidence, pass1_quality
    """
    empty_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

    # Si Pasada 1 no hizo cambios, no hay nada que auditar —
    # pero el LLM puede hacer mejoras de estilo con contexto global.
    # Solo saltamos si además el perfil no tiene contexto global.
    if corrected_pass1 == original_text and not global_context:
        return None, empty_usage

    user_prompt = build_audit_user_prompt(
        original_text=original_text,
        corrected_pass1=corrected_pass1,
        global_context=global_context,
        context_window=context_window,
        paragraph_type=paragraph_type,
        location=location,
    )

    model = model_override or settings.openai_editorial_model

    data, usage = openai_client.correct_with_profile(
        system_prompt=AUDIT_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        max_length=None,  # La auditoría no limita longitud — recuperar texto original si es largo
        model_override=model,
        max_tokens_override=settings.openai_audit_max_tokens,
        on_audit_log=on_audit_log,
    )

    if data is None:
        logger.warning(
            f"Pasada 2: LLM no respondió para párrafo en {location}. "
            f"Manteniendo resultado de Pasada 1."
        )
        return None, usage

    final_text = data.get("final_text", "")
    if not final_text or not final_text.strip():
        logger.warning(f"Pasada 2: final_text vacío en {location}, usando Pasada 1")
        return None, usage

    reverted = data.get("reverted_destructions", [])
    improvements = data.get("style_improvements", [])
    confidence = data.get("confidence", 0.0)
    pass1_quality = data.get("pass1_quality", "ok")

    if reverted:
        logger.info(
            f"Pasada 2 ({location}): {len(reverted)} destrucciones revertidas — "
            + ", ".join(r.get("original_term", "") for r in reverted)
        )
    if improvements:
        logger.info(f"Pasada 2 ({location}): {len(improvements)} mejoras de estilo")

    return {
        "final_text": final_text,
        "reverted_destructions": reverted,
        "style_improvements": improvements,
        "confidence": confidence,
        "pass1_quality": pass1_quality,
    }, usage


def should_run_pass2(
    route_taken: str,
    pass1_rewrite_ratio: float | None,
    intervention_level: str | None,
    pass1_has_changes: bool,
) -> bool:
    """
    Decide si la Pasada 2 es obligatoria u opcional para este párrafo.

    Criterios (OR lógico — cualquiera activa la Pasada 2):
    - Párrafo con ruta editorial
    - Pasada 1 hizo cambios significativos (rewrite_ratio > umbral)
    - Perfil con intervención ≥ moderada y hay cambios de P1
    """
    if not settings.pass2_enabled:
        return False

    if route_taken == "editorial":
        return True

    threshold = settings.pass2_rewrite_threshold
    if pass1_rewrite_ratio is not None and pass1_rewrite_ratio > threshold:
        return True

    if intervention_level in ("moderada", "agresiva") and pass1_has_changes:
        return True

    return False
