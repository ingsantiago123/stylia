"""
PromptBuilder — Construye prompts parametrizados según perfil editorial.
System prompt estático (cacheable) + user prompt dinámico por párrafo.
Sprint 4: bloques estructurales explícitos (PERFIL, UBICACIÓN, CONTEXTO, TEXTO).
"""

from dataclasses import dataclass, field

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


@dataclass
class ParagraphMeta:
    """Metadata enriquecida de un párrafo corregido — sirve como contexto para el siguiente."""
    paragraph_index: int
    location: str
    paragraph_type: str
    text: str
    ends_abruptly: bool = False
    has_protected_terms: bool = False
    last_correction_categories: list[str] = field(default_factory=list)

    def location_type(self) -> str:
        return self.location.split(":")[0] if self.location else "body"

    def to_context_dict(self) -> dict:
        return {
            "text": self.text,
            "type": self.paragraph_type,
            "ends_abruptly": self.ends_abruptly,
            "location_type": self.location_type(),
            "correction_categories": self.last_correction_categories,
        }


def build_system_prompt() -> str:
    """System prompt estático, cacheable por el proveedor LLM."""
    return SYSTEM_PROMPT


def build_user_prompt(
    text: str,
    profile: dict | None = None,
    context_prev: str | dict | None = None,
    paragraph_index: int | None = None,
    section_summary: str | None = None,
    active_terms: list[str] | None = None,
    paragraph_type: str | None = None,
    next_paragraph_type: str | None = None,
    table_context: dict | None = None,
    has_page_break: bool = False,
    protected_regions_text: str | None = None,
    page_no: int | None = None,
    total_pages: int | None = None,
) -> str:
    """
    User prompt dinámico por párrafo.

    Estructura del prompt (Sprint 4 — bloques explícitos):
      [PERFIL EDITORIAL]
      [UBICACIÓN ESTRUCTURAL]   ← nuevo bloque explícito
      [CONTEXTO PREVIO]
      [TEXTO A CORREGIR]
      [REGIONES PROTEGIDAS]     ← si existen

    Args:
        text: Párrafo a corregir (ya pasó por LanguageTool)
        profile: Dict con campos del perfil editorial (o None para genérico)
        context_prev: Último párrafo corregido. Puede ser str (legacy) o dict con
            {text, type, ends_abruptly, location_type} para contexto enriquecido.
        paragraph_index: Índice del párrafo en el documento
        section_summary: Resumen de la sección actual
        active_terms: Términos activos en la sección actual
        paragraph_type: Tipo de párrafo: narrativo, dialogo, lista, etc.
        next_paragraph_type: Tipo del párrafo siguiente (lookahead para no alterar flujo)
        table_context: Contexto de tabla {header_row, num_cols, col_index} para celdas
        has_page_break: Si el párrafo contiene un salto de página estructural
        protected_regions_text: Texto formateado de regiones protegidas (de protected_regions.py)
        page_no: Número de página del párrafo (1-based, si está disponible)
        total_pages: Total de páginas del documento
    """
    parts = []

    # ═══ BLOQUE 1: PERFIL EDITORIAL ════════════════════════════════════
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

    # ═══ BLOQUE 2: UBICACIÓN ESTRUCTURAL ════════════════════════════════
    ubicacion_lines = []

    # Tipo de párrafo con instrucción editorial
    type_hints = {
        "narrativo": "narrativo — priorizar fluidez y cohesión",
        "dialogo": "diálogo — preservar voz del personaje, solo corregir errores claros",
        "explicacion_tecnica": "texto técnico — preservar terminología, priorizar precisión",
        "lista": "elemento de lista — mantener brevedad y paralelismo",
        "celda_tabla": "celda de tabla — mantener concisión extrema",
        "pie_imagen": "PIE DE FIGURA — preservar numeración, fuente y abreviaturas exactamente",
        "titulo": "TÍTULO — solo corregir ortografía, no reformular",
        "subtitulo": "SUBTÍTULO — solo corregir ortografía, no reformular",
        "cita": "CITA TEXTUAL — no modificar, preservar tal cual",
        "encabezado": "encabezado de página — solo errores ortográficos obvios",
        "footer": "pie de página — solo errores ortográficos obvios",
    }
    if paragraph_type:
        tipo_desc = type_hints.get(paragraph_type, paragraph_type)
        ubicacion_lines.append(f"TIPO: {tipo_desc}")

    # Sección actual
    if section_summary:
        ubicacion_lines.append(f"SECCIÓN: {section_summary[:120]}")
    if active_terms:
        ubicacion_lines.append(f"TÉRMINOS ACTIVOS: {', '.join(active_terms[:12])}")

    # Página
    if page_no and total_pages:
        ubicacion_lines.append(f"PÁGINA: {page_no} de {total_pages}")
    elif page_no:
        ubicacion_lines.append(f"PÁGINA: {page_no}")

    # Advertencias cross-page
    if has_page_break:
        ubicacion_lines.append(
            "⚠ CRUZA SALTO DE PÁGINA — NO añadas ni elimines frases que alteren el punto de corte"
        )

    # Contexto de tabla
    if table_context and paragraph_type == "celda_tabla":
        col_idx = table_context.get("col_index", 0)
        header_row = table_context.get("header_row", [])
        num_cols = table_context.get("num_cols", 1)
        col_header = header_row[col_idx] if col_idx < len(header_row) else ""
        if col_header:
            ubicacion_lines.append(
                f"TABLA: columna '{col_header}' de {num_cols} columnas"
            )
        else:
            ubicacion_lines.append(f"TABLA: {num_cols} columnas")

    # Siguiente párrafo (lookahead)
    if next_paragraph_type:
        next_hints = {
            "titulo": "siguiente es TÍTULO — no añadir conector de cierre",
            "subtitulo": "siguiente es SUBTÍTULO — no añadir transición",
            "lista": "siguiente es LISTA — no añadir elementos de lista al final",
            "celda_tabla": "siguiente es CELDA DE TABLA — contexto cambia abruptamente",
        }
        next_hint = next_hints.get(next_paragraph_type)
        if next_hint:
            ubicacion_lines.append(f"SIGUIENTE: {next_hint}")

    if ubicacion_lines:
        parts.append("\n── UBICACIÓN ESTRUCTURAL ──")
        parts.extend(ubicacion_lines)

    # ═══ BLOQUE 3: CONTEXTO PREVIO ══════════════════════════════════════
    if context_prev:
        if isinstance(context_prev, dict):
            ctx_text = context_prev.get("text", "")
            ctx_type = context_prev.get("type", "")
            ctx_ends_abruptly = context_prev.get("ends_abruptly", False)
            ctx_loc = context_prev.get("location_type", "body")
            ctx_categories = context_prev.get("correction_categories", [])

            ctx_truncated = ctx_text[:350] + "..." if len(ctx_text) > 350 else ctx_text
            type_label = f" [{ctx_type}]" if ctx_type else ""
            abrupt_note = " ⚠ continúa (termina sin punto)" if ctx_ends_abruptly else ""
            loc_note = f" en {ctx_loc}" if ctx_loc not in ("body", "") else ""
            cat_note = f" — cambios: {', '.join(ctx_categories)}" if ctx_categories else ""
            parts.append(
                f"\n── CONTEXTO PREVIO{type_label}{loc_note}{abrupt_note}{cat_note} ──\n{ctx_truncated}"
            )
        else:
            ctx = context_prev[:350] + "..." if len(context_prev) > 350 else context_prev
            parts.append(f"\n── CONTEXTO PREVIO ──\n{ctx}")
    else:
        parts.append("\n── CONTEXTO PREVIO ──\nInicio de documento")

    # ═══ BLOQUE 4: TEXTO A CORREGIR ════════════════════════════════════
    parts.append(f"\n── PÁRRAFO A CORREGIR ──\n{text}")

    # ═══ BLOQUE 5: REGIONES PROTEGIDAS (si existen) ════════════════════
    if protected_regions_text:
        parts.append(f"\n{protected_regions_text}")

    return "\n".join(parts)


def build_global_context_block(global_context: dict | None) -> str:
    """
    Construye el bloque de CONTEXTO GLOBAL DEL DOCUMENTO para insertar en prompts.
    Devuelve cadena vacía si no hay contexto global disponible.
    """
    if not global_context:
        return ""

    lines = ["═══ CONTEXTO GLOBAL DEL DOCUMENTO ═══"]

    summary = global_context.get("global_summary")
    if summary:
        lines.append(f"TEMA PRINCIPAL: {summary[:300]}")

    voice = global_context.get("dominant_voice")
    if voice:
        lines.append(f"VOZ DEL AUTOR: {voice[:150]}")

    register = global_context.get("dominant_register")
    if register:
        lines.append(f"REGISTRO BASE: {register} (no alterar a otro registro)")

    protected = global_context.get("protected_globals_json") or []
    if protected:
        terms = [p.get("term", "") for p in protected if p.get("term")]
        if terms:
            lines.append(f"TÉRMINOS TÉCNICOS PROTEGIDOS GLOBALMENTE: {', '.join(terms)}")

    fp = global_context.get("style_fingerprint_json") or {}
    style_parts = []
    avg_len = fp.get("avg_sentence_length")
    if avg_len:
        style_parts.append(f"oraciones de ~{avg_len} palabras")
    passive = fp.get("passive_voice_ratio")
    if passive is not None:
        style_parts.append(f"{int(passive * 100)}% voz pasiva")
    if style_parts:
        lines.append(f"ESTILO DOMINANTE: {', '.join(style_parts)}")

    lines.append("═══════════════════════════════════════")
    return "\n".join(lines)


# System prompt para Pasada 2 — Auditoría Contextual
AUDIT_SYSTEM_PROMPT = """Eres un auditor editorial experto en español con visión global del documento.
Tu tarea es revisar una corrección mecánica previa e identificar si introdujo errores semánticos o destruyó términos importantes.

REGLAS DE AUDITORÍA:
1. Compara el ORIGINAL con la CORRECCIÓN MECÁNICA (Pasada 1) para detectar destrucciones
2. Revierte cualquier cambio que haya alterado términos técnicos, nombres propios o el sentido original
3. Usa el CONTEXTO GLOBAL del documento como referencia absoluta de términos protegidos
4. Aplica mejoras de estilo coherentes con la VOZ DEL AUTOR y el REGISTRO BASE
5. Si no hay problemas en la Pasada 1, solo mejora el estilo final
6. Los TÉRMINOS TÉCNICOS PROTEGIDOS GLOBALMENTE nunca deben modificarse

FORMATO DE RESPUESTA (JSON estricto):
{
  "final_text": "texto final auditado",
  "reverted_destructions": [
    {
      "original_term": "tokenización",
      "pass1_changed_to": "colonización",
      "reason": "término técnico protegido",
      "severity": "critico"
    }
  ],
  "style_improvements": [
    {
      "original_fragment": "fragmento original",
      "improved_fragment": "fragmento mejorado",
      "category": "claridad|registro|cohesion|lexico|ritmo",
      "explanation": "razón del cambio"
    }
  ],
  "confidence": 0.0-1.0,
  "pass1_quality": "ok|minor_issues|major_issues"
}

IMPORTANTE: Responde SOLO con el JSON, sin texto adicional."""


def build_audit_user_prompt(
    original_text: str,
    corrected_pass1: str,
    global_context: dict | None,
    context_window: list[str] | None = None,
    paragraph_type: str | None = None,
    location: str | None = None,
) -> str:
    """
    Prompt de Pasada 2 (Auditoría Contextual).
    Recibe el texto original y el resultado de Pasada 1 para detectar destrucciones.
    """
    parts = []

    # Bloque contexto global
    global_block = build_global_context_block(global_context)
    if global_block:
        parts.append(global_block)

    # Contexto previo (últimos párrafos corregidos)
    if context_window:
        ctx_lines = [f"  [{i+1}] {p[:200]}" for i, p in enumerate(context_window[-3:])]
        parts.append("── CONTEXTO PREVIO (párrafos ya auditados) ──\n" + "\n".join(ctx_lines))

    # Tipo de párrafo
    if paragraph_type:
        parts.append(f"TIPO DE PÁRRAFO: {paragraph_type}")
    if location:
        parts.append(f"UBICACIÓN: {location}")

    # Los textos a comparar
    parts.append(f"\n── TEXTO ORIGINAL ──\n{original_text}")
    parts.append(f"\n── CORRECCIÓN MECÁNICA (Pasada 1) ──\n{corrected_pass1}")
    parts.append(
        "\n── INSTRUCCIÓN ──\n"
        "Compara el ORIGINAL con la CORRECCIÓN MECÁNICA. "
        "Identifica destrucciones (términos técnicos modificados, nombres propios alterados, sentido cambiado). "
        "Revierte las destrucciones y aplica mejoras de estilo coherentes con el CONTEXTO GLOBAL. "
        "Devuelve el texto final auditado en el campo 'final_text'."
    )

    return "\n".join(parts)
