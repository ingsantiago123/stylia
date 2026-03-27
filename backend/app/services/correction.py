"""
Servicio de Corrección (Etapa D).
Pipeline: LanguageTool (ortografía/gramática) → ChatGPT (estilo/claridad).

Para Ruta 1 (DOCX-first): corrige párrafos directamente del DOCX,
no de bloques del PDF, para evitar fragmentación y mayúsculas erróneas.
"""

import json
import logging
import tempfile
from dataclasses import dataclass
from pathlib import Path

import httpx
from docx import Document as DocxDocument

from app.config import settings
from app.utils import minio_client
from app.utils.openai_client import openai_client
from app.services.prompt_builder import build_system_prompt, build_user_prompt
from app.services.complexity_router import (
    route_paragraph, compute_section_position, CorrectionRoute,
)
from app.services.quality_gates import validate_correction as run_quality_gates

logger = logging.getLogger(__name__)


@dataclass
class CorrectionResult:
    """Resultado de corrección de un bloque de texto."""
    original_text: str
    corrected_text: str
    operations: list[dict]
    has_changes: bool
    source: str  # 'languagetool', 'languagetool+chatgpt'


def correct_text_with_languagetool(
    text: str,
    language: str = "es",
    disabled_rules: list[str] | None = None,
) -> CorrectionResult:
    """
    Corrige texto con LanguageTool servidor local.
    Usa la API HTTP directa (más eficiente que la librería Python).
    """
    if not text or not text.strip():
        return CorrectionResult(
            original_text=text,
            corrected_text=text,
            operations=[],
            has_changes=False,
            source="languagetool",
        )

    # Llamar a LanguageTool API
    url = f"{settings.languagetool_url}/v2/check"
    payload = {
        "text": text,
        "language": language,
    }
    if disabled_rules:
        payload["disabledRules"] = ",".join(disabled_rules)

    try:
        response = httpx.post(url, data=payload, timeout=30.0)
        response.raise_for_status()
        result = response.json()
    except httpx.HTTPError as e:
        logger.error(f"Error llamando a LanguageTool: {e}")
        return CorrectionResult(
            original_text=text,
            corrected_text=text,
            operations=[],
            has_changes=False,
            source="languagetool",
        )

    matches = result.get("matches", [])
    if not matches:
        return CorrectionResult(
            original_text=text,
            corrected_text=text,
            operations=[],
            has_changes=False,
            source="languagetool",
        )

    # Aplicar correcciones de atrás hacia adelante (para no alterar offsets)
    operations = []
    corrected = text

    # Ordenar matches por offset descendente para aplicar de atrás hacia adelante
    sorted_matches = sorted(matches, key=lambda m: m["offset"], reverse=True)

    for match in sorted_matches:
        replacements = match.get("replacements", [])
        if not replacements:
            continue

        offset = match["offset"]
        length = match["length"]
        original_fragment = corrected[offset:offset + length]
        replacement = replacements[0]["value"]  # Tomar la primera sugerencia

        # Aplicar reemplazo
        corrected = corrected[:offset] + replacement + corrected[offset + length:]

        operations.append({
            "offset": offset,
            "length": length,
            "original": original_fragment,
            "replacement": replacement,
            "rule_id": match.get("rule", {}).get("id", ""),
            "category": match.get("rule", {}).get("category", {}).get("id", ""),
            "message": match.get("message", ""),
        })

    # Revertir orden para que operations estén en orden natural
    operations.reverse()

    has_changes = corrected != text

    return CorrectionResult(
        original_text=text,
        corrected_text=corrected,
        operations=operations,
        has_changes=has_changes,
        source="languagetool",
    )


def correct_page_blocks_sync(
    doc_id: str,
    page_no: int,
    blocks: list[dict],
    config: dict,
) -> list[dict]:
    """
    Corrige todos los bloques de texto de una página (extracción PDF).
    Se mantiene para registrar patches en BD y para futuras Rutas 2/3.
    Para Ruta 1 DOCX-first, la corrección real se hace en correct_docx_sync.
    """
    language = config.get("language", "es")
    disabled_rules = config.get("lt_disabled_rules", [])

    patches = []

    for block in blocks:
        if block.get("type") != "text":
            continue

        text = block.get("text", "").strip()
        if not text or len(text) < 3:
            continue

        result = correct_text_with_languagetool(
            text=text,
            language=language,
            disabled_rules=disabled_rules,
        )

        if result.has_changes:
            patch_data = {
                "block_no": block["block_no"],
                "original_text": result.original_text,
                "corrected_text": result.corrected_text,
                "operations": result.operations,
                "source": result.source,
                "bbox": block["bbox"],
            }
            patches.append(patch_data)

            logger.info(
                f"Página {page_no}, bloque {block['block_no']}: "
                f"{len(result.operations)} correcciones LT"
            )

    # Guardar parches como JSON en MinIO
    if patches:
        patch_key = f"pages/{doc_id}/patch/{page_no}_v1.json"
        patch_bytes = json.dumps(patches, ensure_ascii=False, indent=2).encode("utf-8")
        minio_client.upload_file(patch_key, patch_bytes, content_type="application/json")

    logger.info(f"Página {page_no}: {len(patches)} bloques con correcciones")
    return patches


# =====================================================================
# CORRECCIÓN DIRECTA DE DOCX (Ruta 1 — evita fragmentación del PDF)
# =====================================================================

def correct_docx_sync(
    doc_id: str,
    docx_uri: str,
    config: dict,
    profile: dict | None = None,
    analysis_data: dict | None = None,
) -> tuple[list[dict], list[dict]]:
    """
    Corrige un DOCX directamente, párrafo por párrafo.
    Pipeline: Router → LanguageTool → ChatGPT (con contexto jerárquico).

    Args:
        analysis_data: Resultado de Etapa C con sections, paragraph_classifications.

    Retorna tupla (patches, usage_records).
    """
    language = config.get("language", "es")
    disabled_rules = config.get("lt_disabled_rules", [])

    # Si hay perfil, usar sus disabled_rules también
    if profile and profile.get("lt_disabled_rules"):
        disabled_rules = list(set(disabled_rules + profile["lt_disabled_rules"]))

    # Descargar DOCX
    docx_bytes = minio_client.download_file(docx_uri)
    tmpfile = tempfile.mktemp(suffix=".docx")
    with open(tmpfile, "wb") as f:
        f.write(docx_bytes)

    doc = DocxDocument(tmpfile)
    Path(tmpfile).unlink(missing_ok=True)

    patches = []
    corrected_context: list[str] = []
    usage_records: list[dict] = []

    all_paragraphs = _collect_all_paragraphs(doc)
    logger.info(f"Documento {doc_id}: {len(all_paragraphs)} párrafos a corregir")

    # MVP2: Construir system prompt UNA VEZ (cacheable)
    system_prompt = build_system_prompt() if profile else None
    max_expansion = profile.get("max_expansion_ratio", 1.15) if profile else 1.15

    # Lote 4: Preparar datos del análisis para contexto jerárquico
    sections = (analysis_data or {}).get("sections", [])
    para_classifications = {}
    for pc in (analysis_data or {}).get("paragraph_classifications", []):
        para_classifications[pc["paragraph_index"]] = pc

    # Lote 4: Contadores de rutas para logging
    route_counts = {"skip": 0, "cheap": 0, "editorial": 0}

    # Lote 5: Contadores de quality gates
    gate_stats = {"passed": 0, "discarded": 0, "flagged": 0}

    for idx, (para_text, location) in enumerate(all_paragraphs):
        text = para_text.strip()
        if not text or len(text) < 3:
            continue

        # === PASO 1: LanguageTool (ortografía y gramática) ===
        lt_result = correct_text_with_languagetool(
            text=text,
            language=language,
            disabled_rules=disabled_rules,
        )

        post_lt_text = lt_result.corrected_text
        lt_operations = lt_result.operations
        source = "languagetool"

        if lt_operations:
            logger.info(
                f"Párrafo {idx}: LanguageTool → {len(lt_operations)} correcciones"
            )

        # === Lote 4: Contexto jerárquico y routing ===
        classification = para_classifications.get(idx, {})
        paragraph_type = classification.get("paragraph_type")

        section_position, is_section_transition, current_section = \
            compute_section_position(idx, sections)

        section_summary = None
        active_terms = None
        if current_section:
            section_summary = current_section.get("summary_text") or current_section.get("topic")
            active_terms = current_section.get("active_terms", [])

        # Decidir ruta de corrección
        route_decision = route_paragraph(
            text=post_lt_text,
            paragraph_type=paragraph_type,
            lt_matches_count=len(lt_operations),
            profile=profile,
            is_section_transition=is_section_transition,
            section_position=section_position,
        )
        route_counts[route_decision.route.value] += 1

        # === PASO 2: LLM (estilo) — según ruta ===
        max_length = int(len(post_lt_text) * max_expansion)
        llm_changes = []
        llm_confidence = None
        llm_rewrite_ratio = None
        route_taken = route_decision.route.value
        model_used_actual = "languagetool"

        if route_decision.route == CorrectionRoute.SKIP:
            # Solo LanguageTool, no enviar al LLM
            final_text = post_lt_text

        elif profile and system_prompt:
            # MVP2: Prompt parametrizado con perfil + contexto jerárquico
            user_prompt = build_user_prompt(
                text=post_lt_text,
                profile=profile,
                context_prev=corrected_context[-1] if corrected_context else None,
                paragraph_index=idx,
                section_summary=section_summary,
                active_terms=active_terms,
                paragraph_type=paragraph_type,
            )

            # Seleccionar modelo según ruta
            if route_decision.route == CorrectionRoute.EDITORIAL:
                model_override = settings.openai_editorial_model
            else:
                model_override = settings.openai_cheap_model
            model_used_actual = model_override

            llm_response, llm_usage = openai_client.correct_with_profile(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                max_length=max_length,
                model_override=model_override,
            )
            if llm_usage["total_tokens"] > 0:
                _cost = (llm_usage["prompt_tokens"] / 1e6 * settings.openai_pricing_input) + \
                        (llm_usage["completion_tokens"] / 1e6 * settings.openai_pricing_output)
                usage_records.append({
                    "paragraph_index": idx,
                    "location": location,
                    "call_type": f"correction_{route_taken}",
                    "model_used": model_override,
                    **llm_usage,
                    "cost_usd": round(_cost, 8),
                })

            if llm_response and llm_response.get("action") == "correct":
                corrected = llm_response.get("corrected_text", "")
                if corrected and corrected != post_lt_text:
                    final_text = corrected
                    source = "languagetool+chatgpt"
                    llm_changes = llm_response.get("changes", [])
                    llm_confidence = llm_response.get("confidence")
                    llm_rewrite_ratio = llm_response.get("rewrite_ratio")
                    logger.info(
                        f"Párrafo {idx}: LLM ({route_taken}) → "
                        f"{len(llm_changes)} cambios [{route_decision.reason}]"
                    )
                else:
                    final_text = post_lt_text
            else:
                final_text = post_lt_text
        else:
            # MVP1 fallback: prompt genérico
            chatgpt_text, mvp1_usage = openai_client.correct_text_style(
                original_text=post_lt_text,
                context_blocks=corrected_context[-3:],
                max_length_ratio=max_expansion,
            )
            if mvp1_usage["total_tokens"] > 0:
                _cost = (mvp1_usage["prompt_tokens"] / 1e6 * settings.openai_pricing_input) + \
                        (mvp1_usage["completion_tokens"] / 1e6 * settings.openai_pricing_output)
                usage_records.append({
                    "paragraph_index": idx,
                    "location": location,
                    "call_type": "correction_mvp1",
                    "model_used": settings.openai_model,
                    **mvp1_usage,
                    "cost_usd": round(_cost, 8),
                })
            model_used_actual = settings.openai_model
            if chatgpt_text is not None and chatgpt_text != post_lt_text:
                final_text = chatgpt_text
                source = "languagetool+chatgpt"
                logger.info(f"Párrafo {idx}: ChatGPT → estilo mejorado")
            else:
                final_text = post_lt_text

        # === Lote 5: Quality Gates ===
        review_status = "auto_accepted"
        review_reason = None
        gate_results_data = []

        if final_text != text and route_decision.route != CorrectionRoute.SKIP:
            gates = run_quality_gates(
                original=text,
                corrected=final_text,
                profile=profile,
                protected_terms=profile.get("protected_terms", []) if profile else [],
            )
            gate_results_data = [g.to_dict() for g in gates]
            failed_critical = [g for g in gates if not g.passed and g.critical]
            failed_non_critical = [g for g in gates if not g.passed and not g.critical]

            if failed_critical:
                # Gate crítico falló → descartar corrección LLM, mantener solo LT
                reasons = "; ".join(g.message for g in failed_critical)
                logger.warning(
                    f"Párrafo {idx}: gates críticos fallaron → descartando corrección LLM: {reasons}"
                )
                final_text = post_lt_text
                source = "languagetool" if lt_operations else source
                llm_changes = []
                review_status = "gate_rejected"
                review_reason = reasons
                gate_stats["discarded"] += 1
            elif failed_non_critical:
                # Gate no-crítico falló → marcar para revisión
                reasons = "; ".join(g.message for g in failed_non_critical)
                review_status = "manual_review"
                review_reason = reasons
                gate_stats["flagged"] += 1
                logger.info(
                    f"Párrafo {idx}: gates no-críticos fallaron → manual_review: {reasons}"
                )
            else:
                gate_stats["passed"] += 1

        corrected_context.append(final_text)

        # Solo crear parche si hay cambios
        if final_text != text:
            patch_data = {
                "paragraph_index": idx,
                "location": location,
                "original_text": text,
                "corrected_text": final_text,
                "lt_operations": lt_operations,
                "source": source,
                # MVP2: campos enriquecidos
                "changes": llm_changes,
                "confidence": llm_confidence,
                "rewrite_ratio": llm_rewrite_ratio,
                "model_used": model_used_actual if "chatgpt" in source else "languagetool",
                # Lote 4: ruta de corrección
                "route_taken": route_taken,
                # Lote 5: quality gates
                "review_status": review_status,
                "review_reason": review_reason,
                "gate_results": gate_results_data,
            }
            patches.append(patch_data)

    # Guardar parches en MinIO
    if patches:
        patch_key = f"docx/{doc_id}/patches_docx.json"
        patch_bytes = json.dumps(patches, ensure_ascii=False, indent=2).encode("utf-8")
        minio_client.upload_file(patch_key, patch_bytes, content_type="application/json")

    total_tokens = sum(r["total_tokens"] for r in usage_records)
    total_cost = sum(r["cost_usd"] for r in usage_records)
    logger.info(
        f"Documento {doc_id}: {len(patches)} párrafos corregidos "
        f"({sum(1 for p in patches if 'chatgpt' in p['source'])} con GPT), "
        f"tokens: {total_tokens}, costo: ${total_cost:.6f}, "
        f"llamadas: {len(usage_records)}, "
        f"rutas: skip={route_counts['skip']} cheap={route_counts['cheap']} editorial={route_counts['editorial']}, "
        f"gates: ok={gate_stats['passed']} descartados={gate_stats['discarded']} revisión={gate_stats['flagged']}"
    )
    return patches, usage_records


def _collect_all_paragraphs(doc: DocxDocument) -> list[tuple[str, str]]:
    """
    Recolecta todos los párrafos del documento con su ubicación.
    Retorna lista de (texto, ubicación) donde ubicación es:
    - 'body:N' para párrafos del cuerpo
    - 'table:T:R:C:P' para párrafos en tablas
    - 'header:S:P' / 'footer:S:P' para encabezados/pies
    """
    paragraphs = []

    # Cuerpo principal
    for i, para in enumerate(doc.paragraphs):
        paragraphs.append((para.text, f"body:{i}"))

    # Tablas
    for t_idx, table in enumerate(doc.tables):
        for r_idx, row in enumerate(table.rows):
            for c_idx, cell in enumerate(row.cells):
                for p_idx, para in enumerate(cell.paragraphs):
                    paragraphs.append((para.text, f"table:{t_idx}:{r_idx}:{c_idx}:{p_idx}"))

    # Headers y footers
    for s_idx, section in enumerate(doc.sections):
        for hf_type, hf in [("header", section.header), ("footer", section.footer)]:
            if hf is None:
                continue
            for p_idx, para in enumerate(hf.paragraphs):
                paragraphs.append((para.text, f"{hf_type}:{s_idx}:{p_idx}"))

    return paragraphs
