"""
PromptBuilder — Construye prompts parametrizados según perfil editorial.
System prompt estático (cacheable) + user prompt dinámico por párrafo.
"""

# Schema de respuesta JSON que el LLM debe retornar
RESPONSE_SCHEMA = """{
  "action": "correct | flag | skip",
  "corrected_text": "texto corregido aquí",
  "changes": [
    {
      "original_fragment": "fragmento exacto original",
      "corrected_fragment": "reemplazo propuesto",
      "category": "redundancia|claridad|registro|cohesion|lexico|estructura|puntuacion|ritmo|muletilla",
      "severity": "critico|importante|sugerencia",
      "explanation": "Razón del cambio en español"
    }
  ],
  "confidence": 0.0-1.0,
  "rewrite_ratio": 0.0-1.0
}"""

# System prompt ESTÁTICO — se reutiliza para todos los párrafos de un documento.
# NO incluir datos dinámicos (ni doc_id, ni timestamps, ni contadores).
SYSTEM_PROMPT = """Eres un corrector de estilo profesional en español. Tu trabajo es mejorar la redacción preservando el significado y la voz del autor.

REGLAS DE CORRECCIÓN:
1. NUNCA cambies el significado del texto
2. Preserva el tono y la voz del autor según el nivel de intervención indicado
3. Los términos protegidos NO se reemplazan por sinónimos
4. Respeta el nivel de intervención: "minima" solo errores claros, "sutil" mejoras conservadoras, "moderada" equilibrio, "agresiva" reescritura significativa
5. Categoriza cada cambio que hagas
6. Si el párrafo no necesita cambios, usa action "skip"
7. Si detectas un problema pero no estás seguro de la corrección, usa action "flag"

CATEGORÍAS DE CAMBIOS:
- redundancia: eliminación de palabras o frases redundantes
- claridad: mejora de la comprensión del texto
- registro: ajuste del nivel de formalidad
- cohesion: mejora de conectores y transiciones
- lexico: precisión en la elección de palabras
- estructura: reordenamiento sintáctico
- puntuacion: corrección de puntuación estilística
- ritmo: mejora del flujo y cadencia
- muletilla: eliminación de muletillas y comodines

SEVERIDADES:
- critico: error que afecta comprensión o cambia significado
- importante: mejora notable en calidad del texto
- sugerencia: mejora menor, opcional

FORMATO DE RESPUESTA (JSON estricto):
""" + RESPONSE_SCHEMA + """

EJEMPLO CORRECTO:
Entrada: "En este sentido, es importante mencionar que la implementación de las metodologías que han sido propuestas podría contribuir a la mejora del rendimiento."
Respuesta: {"action": "correct", "corrected_text": "La implementación de las metodologías propuestas podría mejorar el rendimiento.", "changes": [{"original_fragment": "En este sentido, es importante mencionar que", "corrected_fragment": "", "category": "muletilla", "severity": "importante", "explanation": "Muletilla que no aporta contenido"}, {"original_fragment": "que han sido propuestas", "corrected_fragment": "propuestas", "category": "redundancia", "severity": "sugerencia", "explanation": "Voz pasiva innecesaria"}, {"original_fragment": "contribuir a la mejora del rendimiento", "corrected_fragment": "mejorar el rendimiento", "category": "claridad", "severity": "sugerencia", "explanation": "Expresión más directa sin cambiar significado"}], "confidence": 0.92, "rewrite_ratio": 0.35}

EJEMPLO DE NO CORREGIR:
Entrada (texto técnico con perfil académico): "La disonancia cognitiva se manifiesta cuando el sujeto sostiene dos cogniciones incompatibles."
Respuesta: {"action": "skip", "corrected_text": "", "changes": [], "confidence": 0.95, "rewrite_ratio": 0.0}

IMPORTANTE: Responde SOLO con el JSON, sin texto adicional."""


def build_system_prompt() -> str:
    """System prompt estático, cacheable por el proveedor LLM."""
    return SYSTEM_PROMPT


def build_user_prompt(
    text: str,
    profile: dict | None = None,
    context_prev: str | None = None,
    paragraph_index: int | None = None,
    section_summary: str | None = None,
    active_terms: list[str] | None = None,
    paragraph_type: str | None = None,
) -> str:
    """
    User prompt dinámico por párrafo.

    Args:
        text: Párrafo a corregir (ya pasó por LanguageTool)
        profile: Dict con campos del perfil editorial (o None para genérico)
        context_prev: Último párrafo corregido para continuidad
        paragraph_index: Índice del párrafo en el documento
        section_summary: Resumen de la sección actual (Lote 4)
        active_terms: Términos activos en la sección actual (Lote 4)
        paragraph_type: Tipo de párrafo: narrativo, dialogo, lista, etc. (Lote 4)
    """
    parts = []

    # Perfil codificado (compacto)
    if profile:
        register = profile.get("register", "neutro")
        intervention = profile.get("intervention_level", "moderada")
        audience = profile.get("audience_type", "general")
        expertise = profile.get("audience_expertise", "medio")
        tone = profile.get("tone", "neutro")
        preserve_voice = profile.get("preserve_author_voice", True)
        max_rewrite = profile.get("max_rewrite_ratio", 0.30)
        priorities = profile.get("style_priorities", [])
        protected = profile.get("protected_terms", [])

        parts.append(
            f"PERFIL: {register} | Intervención: {intervention} | "
            f"Audiencia: {audience} ({expertise}) | Tono: {tone}"
        )
        if preserve_voice:
            parts.append("PRESERVAR VOZ DEL AUTOR: sí")
        parts.append(f"MAX REESCRITURA: {int(max_rewrite * 100)}%")
        if priorities:
            parts.append(f"PRIORIDADES: {', '.join(priorities)}")
        if protected:
            parts.append(f"PROTEGER TÉRMINOS: {', '.join(protected)}")
    else:
        parts.append("PERFIL: neutro | Intervención: moderada | Sin perfil específico")

    # Contexto jerárquico de sección (Lote 4)
    if section_summary:
        parts.append(f"\nSECCIÓN ACTUAL: {section_summary}")
    if active_terms:
        parts.append(f"TÉRMINOS ACTIVOS EN SECCIÓN: {', '.join(active_terms[:15])}")
    if paragraph_type:
        type_hints = {
            "narrativo": "Párrafo narrativo — priorizar fluidez y cohesión",
            "dialogo": "Diálogo — preservar voz del personaje, solo corregir errores claros",
            "explicacion_tecnica": "Texto técnico — preservar terminología, priorizar precisión",
            "lista": "Elemento de lista — mantener brevedad y paralelismo",
            "celda_tabla": "Celda de tabla — mantener concisión",
        }
        hint = type_hints.get(paragraph_type, f"Tipo: {paragraph_type}")
        parts.append(f"TIPO DE PÁRRAFO: {hint}")

    # Contexto previo
    if context_prev:
        # Truncar a 200 chars si es muy largo
        ctx = context_prev[:200] + "..." if len(context_prev) > 200 else context_prev
        parts.append(f"\nCONTEXTO PREVIO:\n{ctx}")
    else:
        parts.append("\nCONTEXTO PREVIO: Inicio de documento")

    # Párrafo a corregir
    parts.append(f"\nPÁRRAFO A CORREGIR:\n{text}")

    return "\n".join(parts)
