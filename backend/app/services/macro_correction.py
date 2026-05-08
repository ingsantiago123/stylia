"""
MacroCorrection — Corrección macro por sección (S5).

Pase post-merge que opera SOBRE EL DOCUMENTO COMPLETO una vez terminadas todas
las correcciones micro (LT + LLM por párrafo). Solo activo cuando el perfil
tiene macro_correction_level != "none".

Filosofía:
  - Micro  → por párrafo, independiente, mecánico.
  - Macro  → por sección, holístico, coherencia narrativa y terminológica.

Niveles:
  - "light": mejora cohesión entre párrafos y transiciones de sección.
  - "full":  revisión estructural + coherencia terminológica + fluidez global.
"""

import logging

logger = logging.getLogger(__name__)

# Longitud mínima de texto de sección para enviar al LLM (evita overhead en secciones cortas)
_MIN_SECTION_CHARS = 200
# Máximo de caracteres de texto de sección a enviar al LLM
_MAX_SECTION_CHARS = 6000


MACRO_SYSTEM_PROMPT = """Eres un editor literario experto en español con visión global del texto.
Tu tarea es revisar la coherencia y fluidez de una sección completa de un documento ya corregido a nivel de párrafo.

REGLAS:
1. NO corregir ortografía ni gramática — eso ya fue hecho en el pase micro.
2. Identificar PROBLEMAS DE COHERENCIA: repeticiones semánticas entre párrafos, transiciones abruptas, inconsistencias de registro.
3. Identificar PROBLEMAS TERMINOLÓGICOS: términos usados de forma inconsistente entre párrafos.
4. Proponer CORRECCIONES PUNTUALES (por párrafo) con el texto exacto a reemplazar.
5. NO reescribir párrafos completos si no es necesario.
6. Respetar SIEMPRE la voz del autor y los términos protegidos del perfil.
7. Solo proponer cambios con alta confianza (>0.75).

FORMATO DE RESPUESTA (JSON estricto):
{
  "section_quality": "ok|needs_work|major_issues",
  "coherence_issues": [
    {
      "type": "repeticion|transicion|registro|terminologia",
      "paragraph_index": 0,
      "description": "descripción del problema"
    }
  ],
  "proposed_corrections": [
    {
      "paragraph_index": 0,
      "original_fragment": "texto exacto a reemplazar",
      "corrected_fragment": "texto corregido",
      "category": "cohesion|registro|lexico|terminologia|transicion",
      "explanation": "razón del cambio",
      "confidence": 0.0-1.0
    }
  ],
  "overall_confidence": 0.0-1.0
}

IMPORTANTE: Responde SOLO con el JSON, sin texto adicional."""


def build_macro_correction_prompt(
    section_paragraphs: list[dict],  # [{"paragraph_index": N, "text": "..."}]
    section_summary: str | None,
    global_context: dict | None,
    profile: dict | None,
    level: str = "light",
) -> str:
    """
    Construye el prompt de macro-corrección para una sección.

    Args:
        section_paragraphs: Párrafos de la sección con índice y texto corregido.
        section_summary: Resumen de la sección (de Etapa C).
        global_context: ADN editorial del documento.
        profile: Perfil editorial.
        level: "light" o "full".
    """
    parts = []

    # Contexto global del documento
    if global_context:
        summary = global_context.get("global_summary")
        if summary:
            parts.append(f"DOCUMENTO: {summary[:200]}")
        protected = global_context.get("protected_globals_json") or []
        if protected:
            terms = [p.get("term", "") for p in protected if p.get("term")]
            if terms:
                parts.append(f"TÉRMINOS GLOBALMENTE PROTEGIDOS: {', '.join(terms)}")

    # Perfil editorial
    if profile:
        register = profile.get("register", "neutro")
        intervention = profile.get("intervention_level", "moderada")
        protected_terms = profile.get("protected_terms", [])
        parts.append(f"PERFIL: {register} | Intervención: {intervention}")
        if protected_terms:
            parts.append(f"TÉRMINOS PROTEGIDOS: {', '.join(protected_terms)}")

    # Instrucción de nivel
    level_instruction = {
        "light": "Nivel LIGERO — solo corregir transiciones abruptas y repeticiones semánticas obvias.",
        "full": "Nivel COMPLETO — revisión estructural, coherencia terminológica y fluidez entre párrafos.",
    }.get(level, "Nivel MODERADO.")
    parts.append(f"\nMODO: {level_instruction}")

    # Sección
    if section_summary:
        parts.append(f"\nSECCIÓN: {section_summary[:150]}")

    # Párrafos numerados
    parts.append(f"\n── PÁRRAFOS DE LA SECCIÓN ({len(section_paragraphs)} párrafos) ──")
    for p in section_paragraphs:
        idx = p.get("paragraph_index", 0)
        text = p.get("text", "")
        parts.append(f"\n[{idx}] {text[:500]}")

    parts.append(
        "\n── INSTRUCCIÓN ──\n"
        "Revisa la coherencia y fluidez entre estos párrafos. "
        "Identifica problemas de cohesión, terminología inconsistente o transiciones abruptas. "
        "Propón correcciones puntuales indicando el paragraph_index exacto."
    )

    return "\n".join(parts)


def run_macro_pass_sync(
    doc_id: str,
    all_paragraphs: list[tuple],    # [(text, location), ...]
    corrected_texts: dict[int, str],  # {paragraph_index: corrected_text}
    sections: list[dict],
    global_context: dict | None,
    profile: dict | None,
    level: str = "light",
) -> tuple[list[dict], list[dict]]:
    """
    Ejecuta el pase macro sobre el documento completo.

    Agrupa párrafos por sección, envía cada sección al LLM, recopila patches macro.

    Returns:
        (macro_patches, usage_records)
        - macro_patches: lista de dicts con campos para insertar en patches table
        - usage_records: lista de dicts para LlmUsage
    """
    from app.utils.openai_client import call_openai_sync
    from app.config import settings

    macro_patches: list[dict] = []
    usage_records: list[dict] = []

    if not sections:
        # Sin secciones: tratar todo el documento como una sección
        sections = [{"section_index": 0, "section_title": None, "start_paragraph": 0,
                     "end_paragraph": len(all_paragraphs) - 1, "summary_text": None}]

    for sec in sections:
        start = sec.get("start_paragraph", 0)
        end = sec.get("end_paragraph", len(all_paragraphs) - 1)
        summary = sec.get("summary_text") or sec.get("section_title")

        # Recolectar párrafos corregidos de esta sección
        section_paras = []
        for idx in range(start, end + 1):
            text = corrected_texts.get(idx, "")
            if text and len(text.strip()) > 20:
                section_paras.append({"paragraph_index": idx, "text": text})

        if not section_paras:
            continue

        # Calcular longitud total de texto de la sección
        total_text_len = sum(len(p["text"]) for p in section_paras)
        if total_text_len < _MIN_SECTION_CHARS:
            continue

        # Truncar si supera el máximo
        if total_text_len > _MAX_SECTION_CHARS:
            # Tomar solo los primeros y últimos párrafos
            budget = _MAX_SECTION_CHARS
            selected = []
            for p in section_paras:
                if budget <= 0:
                    break
                selected.append(p)
                budget -= len(p["text"])
            section_paras = selected

        # Construir prompt
        user_prompt = build_macro_correction_prompt(
            section_paragraphs=section_paras,
            section_summary=summary,
            global_context=global_context,
            profile=profile,
            level=level,
        )

        try:
            from app.utils.openai_client import openai_client

            data, usage = openai_client.correct_with_profile(
                system_prompt=MACRO_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                model_override=settings.openai_editorial_model,
                max_tokens_override=settings.openai_editorial_max_tokens,
            )

            if data is None:
                continue

            prompt_tokens = usage.get("prompt_tokens", 0)
            completion_tokens = usage.get("completion_tokens", 0)
            model_used = settings.openai_editorial_model

            cost_usd = (
                (prompt_tokens / 1e6) * settings.openai_pricing_input
                + (completion_tokens / 1e6) * settings.openai_pricing_output
            )

            usage_records.append({
                "doc_id": doc_id,
                "paragraph_index": start,
                "call_type": "macro_correction",
                "model_used": model_used,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "cost_usd": cost_usd,
            })

            proposed = data.get("proposed_corrections") or []

            for correction in proposed:
                para_idx = correction.get("paragraph_index")
                orig_fragment = correction.get("original_fragment", "")
                corr_fragment = correction.get("corrected_fragment", "")
                confidence = float(correction.get("confidence", 0.0))
                category = correction.get("category", "cohesion")
                explanation = correction.get("explanation", "")

                # Solo aceptar correcciones con alta confianza y fragmento no vacío
                if confidence < 0.75 or not orig_fragment or para_idx is None:
                    continue

                # Verificar que el fragmento existe en el texto corregido
                original_text = corrected_texts.get(para_idx, "")
                if orig_fragment not in original_text:
                    logger.debug(
                        f"[macro] Fragmento no encontrado en párrafo {para_idx}: '{orig_fragment[:40]}'"
                    )
                    continue

                # Aplicar la corrección al texto
                new_text = original_text.replace(orig_fragment, corr_fragment, 1)
                if new_text == original_text:
                    continue

                location = all_paragraphs[para_idx][1] if para_idx < len(all_paragraphs) else f"body:{para_idx}"

                macro_patches.append({
                    "paragraph_index": para_idx,
                    "location": location,
                    "original_text": original_text,
                    "corrected_text": new_text,
                    "correction_phase": "llm_macro",
                    "source": "chatgpt_macro",
                    "model_used": model_used,
                    "category": category,
                    "explanation": explanation,
                    "confidence": confidence,
                    "severity": "sugerencia",
                    "pass_number": 3,
                    "rewrite_ratio": abs(len(new_text) - len(original_text)) / max(len(original_text), 1),
                    "gate_results": [],
                    "review_status": "pending",
                })

                # Actualizar texto corregido para siguientes correcciones del mismo doc
                corrected_texts[para_idx] = new_text

        except Exception as e:
            logger.error(f"[macro] Error en sección {sec.get('section_index', '?')}: {e}")

    logger.info(
        f"[macro] doc={doc_id} nivel={level} "
        f"secciones={len(sections)} patches_macro={len(macro_patches)}"
    )
    return macro_patches, usage_records
