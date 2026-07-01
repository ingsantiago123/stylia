"""
PromptBuilder — Construye prompts parametrizados según perfil editorial.
System prompt estático (cacheable) + user prompt dinámico por párrafo.
Sprint 4: bloques estructurales explícitos (PERFIL, UBICACIÓN, CONTEXTO, TEXTO).

CONFIGURACIÓN DINÁMICA POR PERFIL (`profile.prompt_blocks`):
  Cada bloque del prompt puede activarse/desactivarse mediante un dict
  opcional en `profile`. Por defecto todos los bloques activos. Ejemplo:
      profile["prompt_blocks"] = {
          "global_context": True,
          "profile_header": True,
          "ubicacion": True,
          "structural_rules": True,
          "context_prev": True,
          "register_constraints": True,
          "idiolect_protections": True,
          "substitution_rules": True,
          "protected_regions": True,
      }

REGLAS POR TIPO ESTRUCTURAL: cada `paragraph_type` declara qué bloques
le aplican (ej: títulos no necesitan contexto previo extenso, celdas de
tabla no necesitan ventana de contexto narrativo). Eso lo decide
`_blocks_for_paragraph_type(ptype)` — no se hardcodean reglas por tipo
en el prompt del LLM, sólo se filtran bloques que no aportan información.
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
- redundancia: eliminación de palabras o frases redundantes. Incluye pleonasmos
  léxicos en los que dos palabras consecutivas comparten el mismo significado,
  perífrasis donde un verbo + sustantivo abstracto repite la idea, y voz pasiva
  innecesaria. Aplica criterio semántico, no listas cerradas.
- claridad: mejora de la comprensión del texto
- registro: ajuste del nivel de formalidad
- cohesion: mejora de conectores y transiciones
- lexico: precisión en la elección de palabras
- estructura: reordenamiento sintáctico
- puntuacion: corrección de puntuación estilística
- ritmo: mejora del flujo y cadencia
- muletilla: eliminación de muletillas y comodines

ADAPTACIÓN POR TIPO ESTRUCTURAL:
Cada párrafo viene con un bloque "CONTEXTO ESTRUCTURAL DEL ELEMENTO" que
indica su rol en el documento (título, subtítulo, ítem de lista, celda de
tabla, cita, pie de figura, nota al pie, diálogo, etc.). DEBES respetar las
"REGLAS PARA ESTE ELEMENTO" listadas en ese bloque por encima de las reglas
generales cuando entren en conflicto, salvo si contradicen REGLAS DE
CORRECCIÓN 1, 2 o 3 (preservación de significado, tono y términos protegidos).

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


# System prompt para MODO GRUPAL (lista/tabla completa en una llamada).
# Fase 5: separado del individual — antes el system prompt de párrafo
# describía dos contratos de respuesta a la vez, ruido para el 95% de
# las llamadas y ambigüedad de formato en modo json_object.
SYSTEM_PROMPT_GROUP = """Eres un corrector de estilo profesional en español. Recibirás un GRUPO de elementos (los ítems de una lista o las celdas de una tabla) para corregir EN CONJUNTO, armonizándolos entre sí.

REGLAS DE CORRECCIÓN:
1. NUNCA cambies el significado del texto
2. Preserva el tono y la voz del autor según el nivel de intervención indicado
3. Los términos protegidos NO se reemplazan por sinónimos
4. Respeta las "REGLAS PARA ESTE ELEMENTO" del bloque estructural del mensaje
5. NO añadas ni elimines elementos; el conteo es inalterable
6. Cada elemento que no necesite cambios se devuelve con action "skip"

CATEGORÍAS DE CAMBIOS: redundancia, claridad, registro, cohesion, lexico,
estructura, puntuacion, ritmo, muletilla.
SEVERIDADES: critico, importante, sugerencia.

FORMATO DE RESPUESTA (JSON estricto):
{
  "items": [
    {"index": N, "action": "correct"|"skip"|"flag", "corrected_text": "...",
     "changes": [{"original_fragment": "...", "corrected_fragment": "...",
                  "category": "...", "severity": "...", "explanation": "..."}],
     "confidence": 0.0-1.0, "rewrite_ratio": 0.0-1.0},
    ...
  ]
}
"index" es EXACTAMENTE el número [N] mostrado junto a cada elemento.

IMPORTANTE: Responde SOLO con el JSON, sin texto adicional."""


def build_system_prompt(mode: str = "individual") -> str:
    """System prompt estático, cacheable por el proveedor LLM.

    Args:
        mode: "individual" (párrafo a párrafo) | "group" (lista/tabla completa).
    """
    if mode == "group":
        return SYSTEM_PROMPT_GROUP
    return SYSTEM_PROMPT


# ────────────────────────────────────────────────────────────────────────
# Fase 5: filtro de relevancia para términos protegidos.
# Antes la lista completa (perfil + n-gramas de Etapa C + globales C.6,
# potencialmente cientos) se inyectaba en CADA prompt. Ahora solo se emiten
# los términos que de verdad aparecen en el texto a corregir, con tope.
# ────────────────────────────────────────────────────────────────────────

def _relevant_protected_terms(
    protected: list, text: str | None, cap: int | None = None
) -> list[str]:
    """Términos protegidos que aparecen en `text` (case-insensitive), con tope.

    Si no hay texto de referencia, devuelve los primeros `cap` (mejor algo
    que la lista entera).
    """
    if not protected:
        return []
    if cap is None:
        try:
            from app.config import settings as _settings
            cap = _settings.prompt_protected_terms_cap
        except Exception:
            cap = 20
    terms = [str(t) for t in protected if t]
    if not text:
        return terms[:cap]
    low = text.lower()
    relevant = [t for t in terms if t.lower() in low]
    return relevant[:cap]


# ────────────────────────────────────────────────────────────────────────
# Mapa de bloques aplicables por tipo estructural.
#
# Cada paragraph_type declara EL CONJUNTO DE BLOQUES que tiene sentido
# enviarle al LLM. Es una decisión de SEÑAL/RUIDO: un título no se beneficia
# de la ventana narrativa previa, una cita no debe ver substitution_rules
# (no se corrige), etc. El usuario puede sobreescribir por perfil con
# `profile["prompt_blocks"]`.
# ────────────────────────────────────────────────────────────────────────

# Conjunto universal de bloques disponibles
_ALL_BLOCKS = frozenset({
    "global_context",
    "profile_header",
    "ubicacion",
    "structural_rules",
    "context_prev",
    "substitution_rules",
    "register_constraints",
    "idiolect_protections",
    "protected_regions",
})

# Filtros por tipo: lo que SÍ es relevante. Si un tipo no está en el mapa,
# se permiten TODOS los bloques (default permisivo). Esto NO inyecta reglas
# extra al prompt, solo evita enviar bloques irrelevantes que añaden ruido.
_BLOCKS_BY_TYPE: dict[str, frozenset[str]] = {
    "titulo": frozenset({
        "global_context", "profile_header", "ubicacion",
        "structural_rules", "register_constraints",
    }),
    "subtitulo": frozenset({
        "global_context", "profile_header", "ubicacion",
        "structural_rules", "register_constraints",
    }),
    "encabezado": frozenset({
        "profile_header", "ubicacion", "structural_rules",
    }),
    "footer": frozenset({
        "profile_header", "ubicacion", "structural_rules",
    }),
    "cita": frozenset({
        "global_context", "profile_header", "ubicacion",
        "structural_rules", "protected_regions",
    }),
    "pie_imagen": frozenset({
        "global_context", "profile_header", "ubicacion",
        "structural_rules", "protected_regions",
    }),
    "nota_pie": frozenset({
        "global_context", "profile_header", "ubicacion",
        "structural_rules", "protected_regions",
    }),
    "celda_tabla": frozenset({
        "global_context", "profile_header", "ubicacion",
        "structural_rules", "register_constraints", "protected_regions",
    }),
    "celda_tabla_header": frozenset({
        "profile_header", "ubicacion", "structural_rules",
    }),
    "celda_tabla_total": frozenset({
        "profile_header", "ubicacion", "structural_rules",
    }),
    "lista": frozenset({
        "global_context", "profile_header", "ubicacion",
        "structural_rules", "register_constraints",
        "idiolect_protections", "substitution_rules",
    }),
    "narrativo": _ALL_BLOCKS,
    "dialogo": _ALL_BLOCKS,
    "explicacion_tecnica": _ALL_BLOCKS,
}


def _blocks_for_paragraph_type(ptype: str | None) -> frozenset[str]:
    """Devuelve el set de bloques aplicables a un tipo. None = todos."""
    if not ptype:
        return _ALL_BLOCKS
    return _BLOCKS_BY_TYPE.get(ptype, _ALL_BLOCKS)


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
    global_context: dict | None = None,
    substitution_patches: list[dict] | None = None,
    block_meta: dict | None = None,
) -> str:
    """
    User prompt dinámico por párrafo.

    Estructura del prompt (Sprint 4 — bloques explícitos):
      [CONTEXTO GLOBAL]         ← S1: inyectado en Pasada 1 (antes solo en Pasada 2)
      [PERFIL EDITORIAL]
      [UBICACIÓN ESTRUCTURAL]
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
        global_context: ADN editorial del documento (DocumentGlobalContext). S1: ahora
            también se inyecta en Pasada 1 para que el LLM vea los términos globales.
    """
    parts = []

    # Configuración de bloques activos (todos por defecto)
    flags = (profile or {}).get("prompt_blocks") or {}

    def _enabled(name: str) -> bool:
        v = flags.get(name)
        return True if v is None else bool(v)

    # Qué bloques aplican a este tipo estructural (filtro adicional sobre flags)
    applicable = _blocks_for_paragraph_type(paragraph_type)

    def _emit(name: str) -> bool:
        return _enabled(name) and (name in applicable)

    # ═══ BLOQUE 0: CONTEXTO GLOBAL DEL DOCUMENTO ═══════════════════════
    if global_context and _emit("global_context"):
        global_block = build_global_context_block(global_context)
        if global_block:
            parts.append(global_block)

    # ═══ BLOQUE 1: PERFIL EDITORIAL ════════════════════════════════════
    # 100% data-driven: solo emite líneas para campos no nulos. Sin defaults
    # decorativos ("neutro", "moderada", "claridad, fluidez, ..."). El LLM
    # ve solo lo que el editor explicitó en el perfil.
    if profile and _emit("profile_header"):
        header_kv: list[tuple[str, str]] = []
        for key, label in (
            ("register", "registro"),
            ("intervention_level", "intervención"),
            ("audience_type", "audiencia"),
            ("audience_expertise", "experticia"),
            ("tone", "tono"),
            ("genre", "género"),
            ("subgenre", "subgénero"),
        ):
            v = profile.get(key)
            if v:
                header_kv.append((label, str(v)))
        if header_kv:
            parts.append("PERFIL: " + " | ".join(f"{k}={v}" for k, v in header_kv))

        if profile.get("preserve_author_voice") is True:
            parts.append("PRESERVAR VOZ DEL AUTOR: sí")
        elif profile.get("preserve_author_voice") is False:
            parts.append("PRESERVAR VOZ DEL AUTOR: no (reescritura libre)")

        max_rewrite = profile.get("max_rewrite_ratio")
        if isinstance(max_rewrite, (int, float)):
            parts.append(f"MAX REESCRITURA: {int(float(max_rewrite) * 100)}%")

        priorities = profile.get("style_priorities") or []
        if priorities:
            parts.append(f"PRIORIDADES: {', '.join(str(p) for p in priorities)}")

        # Fase 5: solo términos que aparecen en ESTE párrafo (con tope)
        protected = _relevant_protected_terms(
            profile.get("protected_terms") or [], text
        )
        if protected:
            parts.append(f"PROTEGER TÉRMINOS: {', '.join(protected)}")

    # ═══ BLOQUE 2: UBICACIÓN ESTRUCTURAL ════════════════════════════════
    # Solo metadatos OBJETIVOS (tipo, sección, página, vecinos). Las
    # *instrucciones* editoriales por tipo no se duplican aquí: van en el
    # BLOQUE 2.5 (CONTEXTO ESTRUCTURAL DEL ELEMENTO).
    if _emit("ubicacion"):
        ubicacion_lines: list[str] = []

        if paragraph_type:
            ubicacion_lines.append(f"TIPO: {paragraph_type}")

        if section_summary:
            ubicacion_lines.append(f"SECCIÓN: {section_summary[:160]}")
        if active_terms:
            ubicacion_lines.append(f"TÉRMINOS ACTIVOS: {', '.join(active_terms[:12])}")

        if page_no and total_pages:
            ubicacion_lines.append(f"PÁGINA: {page_no} de {total_pages}")
        elif page_no:
            ubicacion_lines.append(f"PÁGINA: {page_no}")

        if has_page_break:
            ubicacion_lines.append(
                "CRUZA SALTO DE PÁGINA: no alterar el punto de corte de oraciones"
            )

        if table_context and paragraph_type and paragraph_type.startswith("celda_tabla"):
            col_idx = table_context.get("col_index", 0)
            header_row = table_context.get("header_row", []) or []
            num_cols = table_context.get("num_cols", 1)
            col_header = header_row[col_idx] if isinstance(col_idx, int) and col_idx < len(header_row) else ""
            if col_header:
                ubicacion_lines.append(
                    f"TABLA: columna '{col_header}' de {num_cols} columnas"
                )
            else:
                ubicacion_lines.append(f"TABLA: {num_cols} columnas")

        if next_paragraph_type:
            ubicacion_lines.append(f"SIGUIENTE: {next_paragraph_type}")

        if ubicacion_lines:
            parts.append("\n── UBICACIÓN ESTRUCTURAL ──")
            parts.extend(ubicacion_lines)

    # ═══ BLOQUE 2.5: CONTEXTO ESTRUCTURAL DEL ELEMENTO ═══════════════════
    # Reglas duras por tipo. Solo se emite si el tipo lo admite y la flag
    # `structural_rules` está activa. Usa `block_meta` (poblado por B.5
    # con style_*/list_*/table_*) si está disponible; en fallback construye
    # un meta vacío para que el builder solo emita reglas universales.
    if paragraph_type and _emit("structural_rules"):
        if block_meta:
            effective_block_meta = dict(block_meta)
            effective_block_meta.setdefault("paragraph_type", paragraph_type)
        else:
            effective_block_meta = {
                "paragraph_type": paragraph_type,
                "style_name": None, "style_level": None,
                "list_id": None, "list_position": None, "list_total": None,
                "list_format_type": None, "list_level": None,
                "table_id": None, "row_index": None, "column_index": None,
                "row_total": None, "col_total": None, "table_cell_role": None,
            }
        neighbors_meta: dict = {}
        if table_context and paragraph_type.startswith("celda_tabla"):
            header_row = table_context.get("header_row", []) or []
            col_idx = table_context.get("col_index", 0)
            num_cols = table_context.get("num_cols")
            if num_cols is not None:
                effective_block_meta.setdefault("col_total", num_cols)
            if isinstance(col_idx, int):
                effective_block_meta.setdefault("column_index", col_idx)
                if 0 <= col_idx < len(header_row):
                    neighbors_meta["column_header"] = header_row[col_idx]
        if next_paragraph_type:
            neighbors_meta["next_type"] = next_paragraph_type
        struct_block = build_structural_block(effective_block_meta, neighbors_meta)
        if struct_block:
            parts.append("\n" + struct_block)

    # ═══ BLOQUE 3: CONTEXTO PREVIO ══════════════════════════════════════
    # Solo se emite si el tipo lo aprovecha (los títulos, citas, celdas de
    # tabla y notas al pie no necesitan ventana narrativa, etc.) y la flag
    # context_prev está activa.
    if _emit("context_prev"):
        if context_prev:
            if isinstance(context_prev, list):
                ctx_lines = []
                for i, cp in enumerate(context_prev):
                    if isinstance(cp, dict):
                        cp_text = cp.get("text", "")
                        cp_type = cp.get("type", "")
                        label = f"[{cp_type}] " if cp_type else ""
                    else:
                        cp_text = str(cp)
                        label = ""
                    truncated = cp_text[:200] + "…" if len(cp_text) > 200 else cp_text
                    ctx_lines.append(f"  [{i+1}] {label}{truncated}")
                parts.append(
                    f"\n── CONTEXTO PREVIO ({len(context_prev)} párrafos) ──\n"
                    + "\n".join(ctx_lines)
                )
            elif isinstance(context_prev, dict):
                ctx_text = context_prev.get("text", "")
                ctx_type = context_prev.get("type", "")
                ctx_ends_abruptly = context_prev.get("ends_abruptly", False)
                ctx_loc = context_prev.get("location_type", "body")
                ctx_categories = context_prev.get("correction_categories", [])
                ctx_truncated = ctx_text[:350] + "..." if len(ctx_text) > 350 else ctx_text
                type_label = f" [{ctx_type}]" if ctx_type else ""
                abrupt_note = " (termina sin punto)" if ctx_ends_abruptly else ""
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

    # ═══ BLOQUE 4: REGLAS DEL USUARIO YA APLICADAS ══════════════════════
    if substitution_patches and _emit("substitution_rules"):
        from app.services.substitution_engine import build_substitutions_prompt_block
        subs_block = build_substitutions_prompt_block(substitution_patches)
        if subs_block:
            parts.append(f"\n{subs_block}")

    # ═══ BLOQUE 5: RESTRICCIONES DE REGISTRO ════════════════════════════
    if profile and _emit("register_constraints"):
        register_constraints: list[str] = profile.get("register_constraints") or []
        if register_constraints:
            rc_lines = ["── RESTRICCIONES DE REGISTRO ──"]
            rc_labels = {
                "lenguaje_inclusivo": "usa formas inclusivas; cuando una sustitución ya esté aplicada, mantenla",
                "sin_anglicismos": "prefiere términos en español (ej: \"correo\" no \"email\")",
                "tuteo_exclusivo": "nunca usar \"usted\"",
                "sin_imperativo": "evita el modo imperativo; usa infinitivo o construcciones impersonales",
                "voseo_rioplatense": "usa formas de voseo rioplatense (vos/tenés/podés)",
            }
            for constraint in register_constraints:
                label = rc_labels.get(constraint, constraint)
                rc_lines.append(f"- {constraint}: {label}")
            parts.append("\n" + "\n".join(rc_lines))

    # ═══ BLOQUE 6: IDIOLECTOS PROTEGIDOS ════════════════════════════════
    if profile and _emit("idiolect_protections"):
        idiolect_protections: list[dict] = profile.get("idiolect_protections") or []
        active_idiolects = [ip for ip in idiolect_protections if ip.get("enabled", True)]
        if active_idiolects:
            id_lines = ["── IDIOLECTOS PROTEGIDOS ──"]
            for idiolect in active_idiolects:
                scope = idiolect.get("scope", "")
                desc = idiolect.get("description", "")
                examples = idiolect.get("examples", [])
                ex_str = f' (ej: {", ".join(repr(e) for e in examples[:3])})' if examples else ""
                id_lines.append(f"- {scope}: {desc}{ex_str}")
            id_lines.append("Si detectas estos patrones, NO los corrijas aunque parezcan incorrectos.")
            parts.append("\n" + "\n".join(id_lines))

    # ═══ BLOQUE 7: TEXTO A CORREGIR ════════════════════════════════════
    parts.append(f"\n── PÁRRAFO A CORREGIR ──\n{text}")

    # ═══ BLOQUE 8: REGIONES PROTEGIDAS (si existen) ════════════════════
    if protected_regions_text and _emit("protected_regions"):
        parts.append(f"\n{protected_regions_text}")

    return "\n".join(parts)


# =====================================================================
# BLOQUE 2.5 — CONTEXTO ESTRUCTURAL DEL ELEMENTO (Nivel 1)
# =====================================================================
# Por cada paragraph_type, una función builder devuelve un bloque literal
# "═══ ELEMENTO: ... ═══" con metadatos del elemento + "REGLAS PARA ESTE
# ELEMENTO". El LLM debe respetarlas por encima de las reglas generales.
# Si no hay metadatos suficientes, las líneas con placeholders vacíos se
# omiten silenciosamente.

_SEP_OPEN = "═══ ELEMENTO: "
_SEP_CLOSE = "═══════════════════════════════════════════"


def _truncate(text: str | None, n: int = 120) -> str:
    if not text:
        return ""
    s = str(text).strip()
    return (s[: n - 1] + "…") if len(s) > n else s


def _optional_line(label: str, value) -> str | None:
    """Devuelve 'LABEL: value' si value no es vacío, si no None."""
    if value is None:
        return None
    if isinstance(value, str) and not value.strip():
        return None
    if isinstance(value, (list, tuple)) and not value:
        return None
    return f"{label}: {value}"


def _build_titulo(block: dict, neighbors: dict) -> str:
    lines: list[str] = []
    level = block.get("style_level") or 1
    lines.append(f"{_SEP_OPEN}TÍTULO (nivel {level}) ═══")
    style_name = block.get("style_name")
    if style_name:
        lines.append(f"ESTILO DOCX: {style_name}")
    section_title = neighbors.get("section_title")
    total_sections = neighbors.get("total_sections")
    if section_title and total_sections:
        lines.append(f'POSICIÓN: encabeza la sección "{_truncate(section_title, 80)}" (de {total_sections})')
    elif section_title:
        lines.append(f'POSICIÓN: encabeza la sección "{_truncate(section_title, 80)}"')
    sibling_titles = neighbors.get("sibling_titles") or []
    if sibling_titles:
        truncated = ", ".join(_truncate(t, 50) for t in sibling_titles[:5])
        lines.append(f"TÍTULOS HERMANOS: {truncated}")
    lines.append("")
    lines.append("REGLAS PARA ESTE ELEMENTO:")
    lines.append("- NO añadir punto final ni dos puntos.")
    lines.append("- NO reformular: solo ortografía, tildes y mayúsculas iniciales.")
    lines.append("- NO convertir a oración completa si el original es nominal.")
    lines.append("- Mantener exactamente la estructura sintáctica (nominal/verbal).")
    lines.append('- Si rewrite_ratio > 0.10, usa action="skip".')
    lines.append(_SEP_CLOSE)
    return "\n".join(lines)


def _build_subtitulo(block: dict, neighbors: dict) -> str:
    lines: list[str] = []
    level = block.get("style_level") or 2
    lines.append(f"{_SEP_OPEN}SUBTÍTULO (nivel {level}) ═══")
    style_name = block.get("style_name")
    if style_name:
        lines.append(f"ESTILO DOCX: {style_name}")
    parent_title = neighbors.get("parent_title")
    if parent_title:
        lines.append(f'BAJO TÍTULO PRINCIPAL: "{_truncate(parent_title, 80)}"')
    section_title = neighbors.get("section_title")
    if section_title:
        lines.append(f'SECCIÓN: "{_truncate(section_title, 80)}"')
    sibling_titles = neighbors.get("sibling_titles") or []
    if sibling_titles:
        truncated = ", ".join(_truncate(t, 50) for t in sibling_titles[:5])
        lines.append(f"SUBTÍTULOS HERMANOS: {truncated}")
    lines.append("")
    lines.append("REGLAS PARA ESTE ELEMENTO:")
    lines.append("- NO añadir punto final ni dos puntos.")
    lines.append("- NO reformular: solo ortografía, tildes y mayúsculas iniciales.")
    lines.append("- NO convertir a oración completa si el original es nominal.")
    lines.append("- Mantener exactamente la estructura sintáctica del título padre.")
    lines.append('- Si rewrite_ratio > 0.10, usa action="skip".')
    lines.append(_SEP_CLOSE)
    return "\n".join(lines)


def _build_narrativo(block: dict, neighbors: dict) -> str:
    lines: list[str] = []
    lines.append(f"{_SEP_OPEN}PÁRRAFO NARRATIVO ═══")
    position = neighbors.get("section_position")
    section_total = neighbors.get("section_total")
    if position and section_total:
        lines.append(f"POSICIÓN EN SECCIÓN: {position} de {section_total}")
    elif position:
        lines.append(f"POSICIÓN EN SECCIÓN: {position}")
    char_count = block.get("char_count")
    word_count = block.get("word_count")
    sentence_count = block.get("sentence_count")
    if any(x is not None for x in (char_count, word_count, sentence_count)):
        parts_ = []
        if char_count is not None:
            parts_.append(f"{char_count} car")
        if word_count is not None:
            parts_.append(f"{word_count} pal")
        if sentence_count is not None:
            parts_.append(f"{sentence_count} oraciones")
        lines.append(f"LONGITUD: {', '.join(parts_)}")
    prev_t = neighbors.get("prev_type")
    next_t = neighbors.get("next_type")
    if prev_t or next_t:
        lines.append(f"VECINOS: anterior={prev_t or '—'}, siguiente={next_t or '—'}")
    avg_sent = neighbors.get("avg_sentence_length")
    lines.append("")
    lines.append("REGLAS PARA ESTE ELEMENTO:")
    lines.append("- Priorizar fluidez, cohesión y eliminación de redundancias semánticas.")
    lines.append("- Si es apertura/cierre de sección, cuidar la transición.")
    lines.append("- Mantener la voz del autor.")
    if avg_sent:
        lines.append(f"- Evitar fragmentar oraciones si el doc promedia {avg_sent} pal/oración.")
    else:
        lines.append("- Evitar fragmentar oraciones manteniendo el ritmo del documento.")
    lines.append(_SEP_CLOSE)
    return "\n".join(lines)


def _build_lista_item(block: dict, neighbors: dict) -> str:
    """ÍTEM DE LISTA — modo individual."""
    lines: list[str] = []
    lines.append(f"{_SEP_OPEN}ÍTEM DE LISTA ═══")
    list_id = block.get("list_id") or "—"
    fmt = block.get("list_format_type") or "—"
    level = block.get("list_level") if block.get("list_level") is not None else "—"
    lines.append(f"LISTA: {list_id} | FORMATO: {fmt} | NIVEL: {level}")
    pos = block.get("list_position")
    total = block.get("list_total")
    if pos is not None and total is not None:
        lines.append(f"POSICIÓN: ítem {pos} de {total}")
    first_item = neighbors.get("first_item_text")
    last_item = neighbors.get("last_item_text")
    if first_item:
        lines.append(f'PRIMER ÍTEM (referencia): "{_truncate(first_item, 120)}"')
    if last_item:
        lines.append(f'ÚLTIMO ÍTEM (referencia): "{_truncate(last_item, 120)}"')
    cap = neighbors.get("capitalization_majority")
    end_punct = neighbors.get("ending_punct_majority")
    parallel = neighbors.get("parallel_structure_hint")
    if any([cap, end_punct, parallel]):
        lines.append("PATRÓN DETECTADO:")
        if cap:
            lines.append(f"  - Inicio mayoritario: {cap}")
        if end_punct:
            lines.append(f"  - Cierre mayoritario: {end_punct}")
        if parallel:
            lines.append(f"  - Estructura: {parallel}")
    lines.append("")
    lines.append("REGLAS PARA ESTE ELEMENTO:")
    lines.append("- Preservar el formato detectado (capitalización inicial, puntuación final).")
    lines.append("- Mantener paralelismo gramatical con los hermanos.")
    # Fase 0: política unificada con el prompt grupal manual — el prefijo
    # escrito por el autor se preserva EXACTAMENTE (antes este prompt pedía
    # "estandarizar" la numeración mientras el grupal lo prohibía).
    lines.append("- Si la numeración o viñeta forma parte del texto del ítem, consérvala EXACTAMENTE como está escrita (no cambies '2)' a '2.' ni similares).")
    lines.append("- Si la numeración ya la gestiona el formato del documento y no está en el texto, no la añadas.")
    lines.append("- Brevedad: NO añadir conectores ni transiciones de párrafo.")
    lines.append(_SEP_CLOSE)
    return "\n".join(lines)


def _build_celda_tabla(block: dict, neighbors: dict) -> str:
    lines: list[str] = []
    role = block.get("table_cell_role") or neighbors.get("table_cell_role") or "data"
    lines.append(f"{_SEP_OPEN}CELDA DE TABLA ═══")
    table_id = block.get("table_id") or "—"
    rows = block.get("row_total")
    cols = block.get("col_total")
    if rows is not None and cols is not None:
        lines.append(f"TABLA: {table_id} | DIMENSIÓN: {rows} × {cols}")
    else:
        lines.append(f"TABLA: {table_id}")
    r = block.get("row_index")
    c = block.get("column_index")
    if r is not None and c is not None:
        lines.append(f"POSICIÓN: fila {r}, columna {c}")
    lines.append(f"ROL: {role}  (header|data|total)")
    header = neighbors.get("column_header")
    if header:
        lines.append(f'ENCABEZADO COLUMNA: "{_truncate(header, 80)}"')
    siblings = neighbors.get("sibling_cells") or []
    if siblings:
        sample = ", ".join(f'"{_truncate(s, 40)}"' for s in siblings[:5])
        lines.append(f"OTRAS CELDAS COLUMNA (muestra): {sample}")
    dt_hint = neighbors.get("column_data_type_hint")
    if dt_hint:
        lines.append(f"TIPO DATO COLUMNA: {dt_hint}")
    lines.append("")
    lines.append("REGLAS PARA ESTE ELEMENTO:")
    lines.append("- Concisión extrema. NO añadidos retóricos.")
    lines.append("- Preservar uniformidad con la columna: capitalización inicial, puntuación")
    lines.append("  final, formato numérico/fecha.")
    lines.append("- NO convertir números, fechas, símbolos monetarios ni porcentajes.")
    if role == "header":
        lines.append("- Header: nominal, sin punto final.")
    elif role == "total":
        lines.append("- Totales: NO modificar valores numéricos.")
    lines.append(_SEP_CLOSE)
    return "\n".join(lines)


def _build_cita(block: dict, neighbors: dict) -> str:
    lines = [
        f"{_SEP_OPEN}CITA TEXTUAL ═══",
        "",
        "REGLAS PARA ESTE ELEMENTO:",
        "- NO modificar el contenido de la cita.",
        "- Solo corregir errores OCR/mojibake evidentes (p. ej. caracteres rotos).",
        "- NO actualizar ortografía histórica ni regularizar registro.",
        "- NO reescribir, NO añadir/quitar comillas, NO modificar puntuación.",
        '- Default: action="skip" salvo error OCR claro.',
        _SEP_CLOSE,
    ]
    return "\n".join(lines)


def _build_pie_imagen(block: dict, neighbors: dict) -> str:
    lines = [
        f"{_SEP_OPEN}PIE DE FIGURA / TABLA ═══",
        "",
        "REGLAS PARA ESTE ELEMENTO:",
        "- Preservar EXACTAMENTE la etiqueta numerada inicial (\"Figura N.\", \"Tabla N.\", \"Gráfico N.\", \"Cuadro N.\").",
        "- Mantener referencias bibliográficas, fuentes y abreviaturas tal cual.",
        "- Solo corregir ortografía, tildes y errores tipográficos obvios.",
        "- NO reformular ni añadir información.",
        "- NO añadir punto final si el original no lo tiene.",
        _SEP_CLOSE,
    ]
    return "\n".join(lines)


def _build_nota_pie(block: dict, neighbors: dict) -> str:
    lines = [
        f"{_SEP_OPEN}NOTA AL PIE ═══",
        "",
        "REGLAS PARA ESTE ELEMENTO:",
        "- Preservar referencias bibliográficas tal cual (autor, año, página, ed.).",
        "- Mantener abreviaturas académicas (cf., ibid., op. cit., etc.).",
        "- Solo corregir ortografía y puntuación evidente.",
        "- NO expandir abreviaturas ni reformular.",
        _SEP_CLOSE,
    ]
    return "\n".join(lines)


def _build_encabezado(block: dict, neighbors: dict) -> str:
    lines = [
        f"{_SEP_OPEN}ENCABEZADO DE PÁGINA ═══",
        "",
        "REGLAS PARA ESTE ELEMENTO:",
        "- Solo errores ortográficos obvios.",
        '- Si rewrite_ratio > 0.05, usa action="skip".',
        "- NO añadir contenido ni reformular.",
        _SEP_CLOSE,
    ]
    return "\n".join(lines)


def _build_footer(block: dict, neighbors: dict) -> str:
    lines = [
        f"{_SEP_OPEN}PIE DE PÁGINA / FOOTER ═══",
        "",
        "REGLAS PARA ESTE ELEMENTO:",
        "- Solo errores ortográficos obvios.",
        '- Si rewrite_ratio > 0.05, usa action="skip".',
        "- NO añadir contenido ni reformular.",
        _SEP_CLOSE,
    ]
    return "\n".join(lines)


def _build_dialogo(block: dict, neighbors: dict) -> str:
    lines = [
        f"{_SEP_OPEN}DIÁLOGO ═══",
        "",
        "REGLAS PARA ESTE ELEMENTO:",
        "- Preservar voz, coloquialismos y regionalismos del personaje.",
        "- Mantener marcas de oralidad intencionales (apócopes, muletillas, repeticiones).",
        "- Corregir SOLO acotaciones del narrador y errores ortográficos no expresivos.",
        "- NO normalizar registro hacia un español estándar.",
        _SEP_CLOSE,
    ]
    return "\n".join(lines)


def _build_explicacion_tecnica(block: dict, neighbors: dict) -> str:
    lines = [
        f"{_SEP_OPEN}EXPLICACIÓN TÉCNICA ═══",
        "",
        "REGLAS PARA ESTE ELEMENTO:",
        "- Precisión > fluidez. NO sustituir términos técnicos por sinónimos coloquiales.",
        "- Preservar fórmulas, símbolos, unidades y notación matemática.",
        "- NO simplificar definiciones ni reordenar conceptos clave.",
        "- Conservar conectores lógicos (por tanto, así, en consecuencia, etc.).",
        _SEP_CLOSE,
    ]
    return "\n".join(lines)


def _build_default(block: dict, neighbors: dict) -> str:
    ptype = block.get("paragraph_type") or "elemento"
    lines = [
        f"{_SEP_OPEN}{ptype.upper()} ═══",
        "",
        "REGLAS PARA ESTE ELEMENTO:",
        "- Aplicar reglas generales de corrección manteniendo registro y voz.",
        _SEP_CLOSE,
    ]
    return "\n".join(lines)


_STRUCTURAL_BUILDERS = {
    "titulo": _build_titulo,
    "subtitulo": _build_subtitulo,
    "narrativo": _build_narrativo,
    "lista": _build_lista_item,
    "celda_tabla": _build_celda_tabla,
    "celda_tabla_header": _build_celda_tabla,
    "celda_tabla_total": _build_celda_tabla,
    "cita": _build_cita,
    "pie_imagen": _build_pie_imagen,
    "nota_pie": _build_nota_pie,
    "encabezado": _build_encabezado,
    "footer": _build_footer,
    "dialogo": _build_dialogo,
    "explicacion_tecnica": _build_explicacion_tecnica,
}


def build_structural_block(
    block_meta: dict | None,
    neighbors: dict | None = None,
) -> str:
    """Construye el BLOQUE 2.5 "CONTEXTO ESTRUCTURAL DEL ELEMENTO" para el
    user prompt. Recibe metadatos del Block (paragraph_type + atributos
    estructurales si están disponibles) y un dict de vecinos/contexto.

    Devuelve cadena vacía si no hay paragraph_type para resolver builder.
    Es genérico: si los campos estructurales no existen (Nivel 1, antes de
    B.5), igual produce las "REGLAS PARA ESTE ELEMENTO" por tipo, que es lo
    realmente crítico para que el LLM se comporte.
    """
    if not block_meta:
        return ""
    ptype = block_meta.get("paragraph_type")
    if not ptype:
        return ""
    builder = _STRUCTURAL_BUILDERS.get(ptype, _build_default)
    return builder(block_meta, neighbors or {})


def _build_profile_prelude(
    profile: dict | None,
    global_context: dict | None,
    paragraph_type: str | None = None,
    text_sample: str | None = None,
) -> str:
    """Construye un prelude reutilizable con perfil + contexto global +
    restricciones de registro + idiolectos. Comparte la lógica de
    build_user_prompt para que los prompts GRUPALES también vean toda
    la información del perfil editorial.

    Honra `profile["prompt_blocks"]` y filtra por tipo estructural.
    """
    flags = (profile or {}).get("prompt_blocks") or {}
    applicable = _blocks_for_paragraph_type(paragraph_type)

    def emit(name: str) -> bool:
        v = flags.get(name)
        on = True if v is None else bool(v)
        return on and (name in applicable)

    parts: list[str] = []

    if global_context and emit("global_context"):
        gb = build_global_context_block(global_context)
        if gb:
            parts.append(gb)

    if profile and emit("profile_header"):
        header_kv: list[tuple[str, str]] = []
        for key, label in (
            ("register", "registro"),
            ("intervention_level", "intervención"),
            ("audience_type", "audiencia"),
            ("audience_expertise", "experticia"),
            ("tone", "tono"),
            ("genre", "género"),
            ("subgenre", "subgénero"),
        ):
            v = profile.get(key)
            if v:
                header_kv.append((label, str(v)))
        if header_kv:
            parts.append("PERFIL: " + " | ".join(f"{k}={v}" for k, v in header_kv))
        if profile.get("preserve_author_voice") is True:
            parts.append("PRESERVAR VOZ DEL AUTOR: sí")
        max_rewrite = profile.get("max_rewrite_ratio")
        if isinstance(max_rewrite, (int, float)):
            parts.append(f"MAX REESCRITURA: {int(float(max_rewrite) * 100)}%")
        priorities = profile.get("style_priorities") or []
        if priorities:
            parts.append(f"PRIORIDADES: {', '.join(str(p) for p in priorities)}")
        # Fase 5: solo términos presentes en el texto del grupo (con tope)
        protected = _relevant_protected_terms(
            profile.get("protected_terms") or [], text_sample
        )
        if protected:
            parts.append(f"PROTEGER TÉRMINOS: {', '.join(protected)}")

    if profile and emit("register_constraints"):
        rc: list[str] = profile.get("register_constraints") or []
        if rc:
            parts.append("RESTRICCIONES DE REGISTRO: " + ", ".join(rc))

    if profile and emit("idiolect_protections"):
        idis = [
            ip for ip in (profile.get("idiolect_protections") or [])
            if ip.get("enabled", True)
        ]
        if idis:
            lines = ["IDIOLECTOS PROTEGIDOS (no corregir aunque parezcan errores):"]
            for it in idis:
                lines.append(f"- {it.get('scope','')}: {it.get('description','')}")
            parts.append("\n".join(lines))

    return "\n".join(parts)


def build_group_user_prompt_list(
    items: list[str],
    list_metadata: dict | None = None,
    neighbors: dict | None = None,
    profile: dict | None = None,
    global_context: dict | None = None,
) -> str:
    """Construye el BLOQUE 2.5 en modo grupal LISTA COMPLETA.
    Una sola llamada al LLM con N ítems. La respuesta esperada es
    {"items": [{"index": 0, ...}, ...]}.

    `list_metadata["detection"]`:
      - "native" (default): la viñeta/numeración la gestiona el DOCX, los
        ítems vienen SIN prefijo y deben devolverse SIN prefijo.
      - "manual": el usuario tipeó la numeración como parte del texto
        ("1. ", "2) ", "- "); los prefijos vienen DENTRO del texto y deben
        UNIFICARSE al formato más frecuente (el LLM mantiene/normaliza el
        prefijo dentro del texto corregido).
    """
    list_metadata = list_metadata or {}
    neighbors = neighbors or {}
    list_id = list_metadata.get("list_id") or "—"
    fmt = list_metadata.get("list_format_type") or "—"
    level = list_metadata.get("list_level") if list_metadata.get("list_level") is not None else "—"
    detection = list_metadata.get("detection") or "native"
    n = len(items)
    cap = neighbors.get("capitalization_majority")
    end_punct = neighbors.get("ending_punct_majority")
    parallel = neighbors.get("parallel_structure_hint")
    preceding = neighbors.get("preceding_paragraph")
    following = neighbors.get("following_paragraph")

    lines: list[str] = []
    prelude = _build_profile_prelude(
        profile, global_context, paragraph_type="lista",
        text_sample="\n".join(items),
    )
    if prelude:
        lines.append(prelude)
        lines.append("")

    lines.extend([
        f"{_SEP_OPEN}LISTA COMPLETA (modo grupal) ═══",
        f"LISTA: {list_id} | FORMATO: {fmt} | NIVEL: {level} | DETECCIÓN: {detection}",
        f"N ÍTEMS: {n}",
    ])
    if any([cap, end_punct, parallel]):
        lines.append("PATRÓN DETECTADO:")
        if cap:
            lines.append(f"  - Inicio: {cap}")
        if end_punct:
            lines.append(f"  - Cierre: {end_punct}")
        if parallel:
            lines.append(f"  - Estructura: {parallel}")
    if preceding:
        lines.append(f'CONTEXTO PREVIO A LA LISTA: "{_truncate(preceding, 200)}"')
    if following:
        lines.append(f'CONTEXTO POSTERIOR: "{_truncate(following, 200)}"')

    rules_base = [
        "- Corrige los ítems UNO A UNO devolviendo un array \"items\" con \"index\" 0..N-1.",
        "- Cada ítem se evalúa individualmente, pero las correcciones deben ARMONIZARLOS:",
        "  todos terminan con la misma puntuación, comienzan con el mismo tipo de palabra",
        "  (sustantivo/verbo) y respetan la capitalización mayoritaria.",
        "- Si un ítem rompe el paralelismo, alinéalo a la mayoría (no al revés).",
        "- NO añadas ni elimines ítems; el conteo es inalterable.",
        '- Si un ítem no necesita cambios, inclúyelo con action="skip".',
    ]
    if detection == "manual":
        rules_specific = [
            "- LISTA MANUAL: la numeración o viñeta forma parte del TEXTO del ítem (ej: '1. Informe', '2) Base').",
            "  Los ítems llegan CON su prefijo y DEBES DEVOLVERLOS CON EL MISMO PREFIJO SIN ALTERARLO.",
            "- NO cambies '2)' a '2.' ni '1.' a '1)' ni ningún otro formato de prefijo.",
            "  El prefijo de cada ítem llega tal como el usuario lo escribió: respétalo.",
            "- Solo corrige el CONTENIDO después del prefijo (ortografía, gramática, puntuación, redacción).",
        ]
    else:
        rules_specific = [
            "- LISTA NATIVA: la viñeta/numeración la gestiona el DOCX. Escribe SOLO el texto del ítem,",
            "  SIN prefijos '1.', '2)', '-' al inicio.",
        ]

    lines.extend([
        "",
        "REGLAS PARA ESTE ELEMENTO:",
        *rules_base,
        *rules_specific,
        "",
        "ÍTEMS:",
    ])
    for i, txt in enumerate(items):
        lines.append(f'[{i}] "{txt}"')
    lines.extend([
        "",
        "FORMATO DE RESPUESTA (grupo):",
        '{',
        '  "items": [',
        '    {"index": 0, "action": "correct"|"skip"|"flag", "corrected_text": "...",',
        '     "changes": [...], "confidence": 0.0-1.0, "rewrite_ratio": 0.0-1.0},',
        '    ...',
        '  ]',
        '}',
        _SEP_CLOSE,
    ])
    return "\n".join(lines)


def build_group_user_prompt_table(
    cells: list[dict],
    table_metadata: dict | None = None,
    neighbors: dict | None = None,
    profile: dict | None = None,
    global_context: dict | None = None,
) -> str:
    """Construye el BLOQUE 2.5 en modo grupal TABLA COMPLETA.
    Cada celda es {row, col, text, role}. index = row * col_total + col.
    """
    table_metadata = table_metadata or {}
    neighbors = neighbors or {}
    table_id = table_metadata.get("table_id") or "—"
    rows = table_metadata.get("num_rows") or 0
    cols = table_metadata.get("num_cols") or 0
    headers = table_metadata.get("column_headers") or []
    data_hints = table_metadata.get("column_data_type_hints") or []

    lines: list[str] = []
    prelude = _build_profile_prelude(
        profile, global_context, paragraph_type="celda_tabla",
        text_sample="\n".join((c.get("text") or "") for c in cells),
    )
    if prelude:
        lines.append(prelude)
        lines.append("")

    lines.extend([
        f"{_SEP_OPEN}TABLA COMPLETA (modo grupal) ═══",
        f"TABLA: {table_id}",
        f"DIMENSIÓN: {rows} × {cols}",
    ])
    if headers:
        lines.append("ENCABEZADOS DE COLUMNA: " + ", ".join(f'"{_truncate(h, 40)}"' for h in headers))
    if data_hints:
        lines.append("TIPOS DE DATO POR COLUMNA: " + ", ".join(str(d) for d in data_hints))
    # H2 (Fase 0): el "index" es el número [N] mostrado junto a cada celda
    # (posición secuencial), NO una fórmula fila*cols+col. La fórmula anterior
    # se desalineaba con el orden de enumeración del parser ante celdas
    # vacías, multipárrafo o particiones, aplicando correcciones a celdas
    # equivocadas o descartándolas por fuera de rango.
    lines.extend([
        "",
        "REGLAS PARA ESTE ELEMENTO:",
        "- Corrige las celdas devolviendo un array \"items\" donde \"index\" es EXACTAMENTE",
        "  el número [N] mostrado junto a cada celda (no lo calcules de otra forma).",
        "- Preserva uniformidad de columna: capitalización inicial y puntuación final consistentes.",
        "- NO conviertas números, fechas, monedas, ni símbolos.",
        "- NO modifiques valores en filas de totales.",
        "- Para headers: nominal, sin punto final.",
        '- Si una celda no necesita cambios, devuélvela con action="skip".',
        "- NO añadas ni elimines filas/columnas; el conteo es inalterable.",
        "",
        "CELDAS:",
    ])
    for i, cell in enumerate(cells):
        role = cell.get("role") or "data"
        txt = cell.get("text") or ""
        lines.append(f'[{i}] (r={cell.get("row")}, c={cell.get("col")}, rol={role}) "{txt}"')
    lines.extend([
        "",
        "FORMATO DE RESPUESTA (grupo):",
        '{',
        '  "items": [',
        '    {"index": N, "action": "correct"|"skip"|"flag", "corrected_text": "...",',
        '     "changes": [...], "confidence": 0.0-1.0, "rewrite_ratio": 0.0-1.0},',
        '    ...',
        '  ]',
        '}',
        _SEP_CLOSE,
    ])
    return "\n".join(lines)


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
7. Las REGLAS DEL USUARIO (substitution_rules, entity_normalizations) ya fueron aplicadas
   en una fase previa. NO las reviertas — son decisiones del editor humano.
8. Los IDIOLECTOS PROTEGIDOS deben preservarse exactamente como están, incluso si parecen
   no estándar. Forman parte de la voz autoral o de personajes.
9. Las RESTRICCIONES DE REGISTRO son obligatorias. Si la Pasada 1 introdujo un anglicismo
   y register_constraints incluye "sin_anglicismos", revierte ese cambio.

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
