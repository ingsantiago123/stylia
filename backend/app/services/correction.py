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
) -> list[dict]:
    """
    Corrige un DOCX directamente, párrafo por párrafo.
    Pipeline: LanguageTool → ChatGPT (con contexto acumulado).

    MVP2: Si profile viene, usa PromptBuilder para prompt parametrizado
    y parsea respuesta estructurada con categorías y explicaciones.

    Retorna lista de parches con campos enriquecidos.
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

    all_paragraphs = _collect_all_paragraphs(doc)
    logger.info(f"Documento {doc_id}: {len(all_paragraphs)} párrafos a corregir")

    # MVP2: Construir system prompt UNA VEZ (cacheable)
    system_prompt = build_system_prompt() if profile else None
    max_expansion = profile.get("max_expansion_ratio", 1.15) if profile else 1.15

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

        # === PASO 2: LLM (estilo) ===
        max_length = int(len(post_lt_text) * max_expansion)
        llm_changes = []
        llm_confidence = None
        llm_rewrite_ratio = None

        if profile and system_prompt:
            # MVP2: Prompt parametrizado con perfil
            user_prompt = build_user_prompt(
                text=post_lt_text,
                profile=profile,
                context_prev=corrected_context[-1] if corrected_context else None,
                paragraph_index=idx,
            )
            llm_response = openai_client.correct_with_profile(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                max_length=max_length,
            )

            if llm_response and llm_response.get("action") == "correct":
                corrected = llm_response.get("corrected_text", "")
                if corrected and corrected != post_lt_text:
                    final_text = corrected
                    source = "languagetool+chatgpt"
                    llm_changes = llm_response.get("changes", [])
                    llm_confidence = llm_response.get("confidence")
                    llm_rewrite_ratio = llm_response.get("rewrite_ratio")
                    logger.info(f"Párrafo {idx}: LLM → {len(llm_changes)} cambios (perfil)")
                else:
                    final_text = post_lt_text
            else:
                final_text = post_lt_text
        else:
            # MVP1 fallback: prompt genérico
            chatgpt_text = openai_client.correct_text_style(
                original_text=post_lt_text,
                context_blocks=corrected_context[-3:],
                max_length_ratio=max_expansion,
            )
            if chatgpt_text is not None and chatgpt_text != post_lt_text:
                final_text = chatgpt_text
                source = "languagetool+chatgpt"
                logger.info(f"Párrafo {idx}: ChatGPT → estilo mejorado")
            else:
                final_text = post_lt_text

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
                "model_used": settings.openai_model if "chatgpt" in source else "languagetool",
            }
            patches.append(patch_data)

    # Guardar parches en MinIO
    if patches:
        patch_key = f"docx/{doc_id}/patches_docx.json"
        patch_bytes = json.dumps(patches, ensure_ascii=False, indent=2).encode("utf-8")
        minio_client.upload_file(patch_key, patch_bytes, content_type="application/json")

    logger.info(
        f"Documento {doc_id}: {len(patches)} párrafos corregidos "
        f"({sum(1 for p in patches if 'chatgpt' in p['source'])} con GPT)"
    )
    return patches


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
