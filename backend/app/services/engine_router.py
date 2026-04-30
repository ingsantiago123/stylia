"""
Engine Router — Orquestador dual LanguageTool / LLM.

Define reglas explícitas de qué motor actúa sobre qué tipo de contenido,
previniendo colisiones entre LanguageTool y el LLM.

Reglas generales:
  - LT:  ortografía y gramática básica (sin contexto semántico)
  - LLM: estilo, cohesión, registro, claridad, muletillas
  - Ambos respetan las regiones protegidas (no las tocan)
  - LT no corre sobre citas textuales completas ni títulos externos
"""

import re
import logging
from dataclasses import dataclass, field

from app.services.protected_regions import (
    ProtectedRegion,
    detect_protected_regions,
    modification_touches_protected,
)

logger = logging.getLogger(__name__)

# Reglas de LT que afectan estilo (no deben competir con el LLM)
_LT_STYLE_RULES_TO_DISABLE = [
    "WHITESPACE_RULE",
    "COMMA_PARENTHESIS_WHITESPACE",
    "EN_QUOTES",
    # Reglas estilísticas que el LLM maneja mejor:
    "REDUNDANCY",
    "STYLE",
    "COLLOQUIALISM",
    "CLICHE",
]


@dataclass
class EngineDecision:
    """Resultado de la evaluación del orquestador para un párrafo."""
    apply_lt: bool = True
    apply_llm: bool = True
    lt_disabled_rules: list[str] = field(default_factory=list)
    protected_regions: list[ProtectedRegion] = field(default_factory=list)
    skip_reason: str | None = None

    def should_skip_entirely(self) -> bool:
        return not self.apply_lt and not self.apply_llm


def decide_engines(
    text: str,
    paragraph_type: str | None = None,
    profile: dict | None = None,
    term_registry: list | None = None,
    base_disabled_rules: list[str] | None = None,
) -> EngineDecision:
    """
    Decide qué motores de corrección aplican y con qué restricciones.

    Args:
        text: Texto a evaluar.
        paragraph_type: Tipo del párrafo (titulo, celda_tabla, cita, etc.).
        profile: Perfil editorial con protected_terms.
        term_registry: Glosario de términos (con is_protected).
        base_disabled_rules: Reglas ya desactivadas en la configuración base.

    Returns:
        EngineDecision con instrucciones para LT y LLM.
    """
    decision = EngineDecision(
        lt_disabled_rules=list(base_disabled_rules or []) + _LT_STYLE_RULES_TO_DISABLE,
    )

    # Detectar regiones protegidas siempre
    decision.protected_regions = detect_protected_regions(
        text=text, profile=profile, term_registry=term_registry,
    )

    # Citas textuales: ni LT ni LLM modifican el contenido
    if paragraph_type == "cita":
        decision.apply_lt = False
        decision.apply_llm = False
        decision.skip_reason = "cita_textual"
        return decision

    # Títulos: solo corrección ortográfica (LT), sin reformulación (sin LLM)
    if paragraph_type in ("titulo", "subtitulo"):
        decision.apply_llm = False
        # Para títulos, LT puede corregir ortografía pero no gramática contextual
        decision.lt_disabled_rules.extend([
            "SENTENCE_WHITESPACE",
            "UPPERCASE_SENTENCE_START",
        ])
        return decision

    # Encabezados y pies de página: solo LT básico
    if paragraph_type in ("encabezado", "footer"):
        decision.apply_llm = False
        return decision

    # Para todos los demás tipos: ambos motores activos con reglas filtradas
    return decision


def revert_lt_changes_in_protected_regions(
    original_text: str,
    lt_corrected: str,
    protected_regions: list[ProtectedRegion],
) -> tuple[str, list[dict]]:
    """
    Revierte cambios de LanguageTool que afecten regiones protegidas.

    Estrategia: para cada región protegida, si LT modificó el texto dentro
    de ese rango, restaurar el fragmento original.

    Returns:
        (texto_revertido, lista_de_reversiones)
    """
    if not protected_regions or original_text == lt_corrected:
        return lt_corrected, []

    reverted_changes: list[dict] = []
    result = lt_corrected

    # Trabajar de atrás hacia adelante para no desplazar offsets
    for region in reversed(protected_regions):
        orig_fragment = original_text[region.start:region.end]

        # Buscar si LT modificó algo en esa zona
        # Usamos búsqueda de subcadena insensible a mayúsculas
        if orig_fragment.lower() not in result.lower():
            # La región fue alterada — intentar restaurar
            # Buscar texto cercano para localizar la posición en lt_corrected
            context_before = original_text[max(0, region.start - 10):region.start]
            pos = result.find(context_before)
            if pos != -1:
                insert_at = pos + len(context_before)
                # Encontrar el final del fragmento alterado
                context_after = original_text[region.end:min(len(original_text), region.end + 10)]
                end_pos = result.find(context_after, insert_at)
                if end_pos != -1:
                    old_fragment = result[insert_at:end_pos]
                    result = result[:insert_at] + orig_fragment + result[end_pos:]
                    reverted_changes.append({
                        "region_start": region.start,
                        "region_end": region.end,
                        "reason": region.reason,
                        "lt_had": old_fragment,
                        "restored": orig_fragment,
                    })
                    logger.debug(
                        f"Revertida corrección LT en región protegida ({region.reason}): "
                        f"'{old_fragment}' → '{orig_fragment}'"
                    )

    return result, reverted_changes


def build_lt_audit(
    original: str,
    lt_corrected: str,
    lt_operations: list[dict],
    reverted: list[dict],
) -> dict:
    """Construye el registro de auditoría de LanguageTool para el patch."""
    return {
        "original": original,
        "corrected": lt_corrected,
        "operations": lt_operations,
        "reverted_protected": reverted,
        "net_changes": len(lt_operations) - len(reverted),
    }
