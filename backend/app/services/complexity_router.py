"""
Router de complejidad — Decide la ruta de corrección por párrafo (MVP2 Lote 4).

Tres rutas posibles:
  SKIP:      Solo LanguageTool, no enviar al LLM (ahorro total).
  CHEAP:     Modelo económico (gpt-4o-mini).
  EDITORIAL: Modelo potente (configurable) para casos complejos.
"""

import logging
import re
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class CorrectionRoute(Enum):
    SKIP = "skip"
    CHEAP = "cheap"
    EDITORIAL = "editorial"


@dataclass
class RouteDecision:
    route: CorrectionRoute
    reason: str


# Tipos de párrafo que nunca necesitan LLM
_SKIP_TYPES = {"titulo", "subtitulo", "encabezado", "footer", "vacio"}

# Tipos de párrafo que usan ruta barata
_CHEAP_TYPES = {"celda_tabla", "lista", "pie_imagen"}

# Heurística: oraciones subordinadas anidadas (comas, conjunciones)
_COMPLEX_SYNTAX_PATTERN = re.compile(
    r"(,\s*(que|aunque|mientras|porque|si|cuando|donde|como)\s)", re.IGNORECASE
)


def route_paragraph(
    text: str,
    paragraph_type: str | None = None,
    lt_matches_count: int = 0,
    profile: dict | None = None,
    is_section_transition: bool = False,
    section_position: str | None = None,
) -> RouteDecision:
    """
    Decide qué ruta de corrección toma un párrafo.

    Args:
        text: Texto del párrafo (post-LanguageTool).
        paragraph_type: Tipo del párrafo (de Etapa C).
        lt_matches_count: Correcciones de LanguageTool aplicadas.
        profile: Perfil editorial del documento.
        is_section_transition: Si es el primer párrafo de una nueva sección.
        section_position: "first", "middle", o "last" dentro de su sección.

    Returns:
        RouteDecision con la ruta y la razón.
    """
    stripped = text.strip()
    intervention = (profile or {}).get("intervention_level", "moderada")

    # ── SKIP: tipos que no necesitan LLM ──
    if paragraph_type in _SKIP_TYPES:
        return RouteDecision(CorrectionRoute.SKIP, f"type:{paragraph_type}")

    # SKIP: citas (se preservan tal cual)
    if paragraph_type == "cita":
        return RouteDecision(CorrectionRoute.SKIP, "quote_preserve")

    # SKIP: texto muy corto sin errores LT y sin ser transición
    if len(stripped) < 30 and lt_matches_count == 0 and not is_section_transition:
        return RouteDecision(CorrectionRoute.SKIP, "short_clean")

    # ── EDITORIAL: casos que requieren modelo potente ──

    # Transiciones entre secciones
    if is_section_transition:
        return RouteDecision(CorrectionRoute.EDITORIAL, "section_transition")

    # Primer y último párrafo de sección (encuadre retórico)
    if section_position in ("first", "last") and len(stripped) > 80:
        return RouteDecision(CorrectionRoute.EDITORIAL, f"section_{section_position}")

    # Narrativo largo con sintaxis compleja
    if paragraph_type == "narrativo" and len(stripped) > 300:
        subordinate_count = len(_COMPLEX_SYNTAX_PATTERN.findall(stripped))
        if subordinate_count >= 2:
            return RouteDecision(CorrectionRoute.EDITORIAL, "complex_syntax")

    # Diálogo extenso (preservar voz de personaje requiere más cuidado)
    if paragraph_type == "dialogo" and len(stripped) > 200:
        return RouteDecision(CorrectionRoute.EDITORIAL, "long_dialogue")

    # Intervención agresiva en textos largos → editorial
    if intervention == "agresiva" and len(stripped) > 200:
        return RouteDecision(CorrectionRoute.EDITORIAL, "aggressive_long")

    # ── CHEAP: modelo económico ──

    # Tipos simples
    if paragraph_type in _CHEAP_TYPES:
        return RouteDecision(CorrectionRoute.CHEAP, f"type:{paragraph_type}")

    # Intervención mínima → siempre barato
    if intervention == "minima":
        return RouteDecision(CorrectionRoute.CHEAP, "minimal_intervention")

    # Texto corto limpio
    if lt_matches_count == 0 and len(stripped) < 150:
        return RouteDecision(CorrectionRoute.CHEAP, "short_clean_text")

    # Default → cheap (gpt-4o-mini, igual que el comportamiento actual)
    return RouteDecision(CorrectionRoute.CHEAP, "default")


def compute_section_position(
    paragraph_index: int,
    sections: list[dict],
) -> tuple[str | None, bool, dict | None]:
    """
    Determina la posición de un párrafo dentro de su sección
    y si es una transición de sección.

    Args:
        paragraph_index: Índice global del párrafo.
        sections: Lista de secciones del análisis.

    Returns:
        (section_position, is_section_transition, section_dict)
        - section_position: "first" | "middle" | "last" | None
        - is_section_transition: True si es el primer párrafo de una sección (excepto la primera)
        - section_dict: Dict de la sección a la que pertenece, o None.
    """
    if not sections:
        return None, False, None

    for sec in sections:
        start = sec.get("start_paragraph", 0)
        end = sec.get("end_paragraph", 0)
        if start <= paragraph_index <= end:
            if paragraph_index == start:
                is_transition = sec.get("section_index", 0) > 0
                return "first", is_transition, sec
            elif paragraph_index == end:
                return "last", False, sec
            else:
                return "middle", False, sec

    return None, False, None
