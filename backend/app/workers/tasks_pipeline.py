"""
Tareas Celery para el pipeline MVP 1.
Pipeline completo: ingest → extract → correct → render.
Todo en un solo archivo para MVP. Se dividirá en fases posteriores.
"""

import json
import logging
import re
from datetime import datetime, timezone
from difflib import SequenceMatcher

from sqlalchemy import create_engine, delete, select, update
from sqlalchemy.orm import Session, sessionmaker

from app.workers.celery_app import celery_app
from app.config import settings
from app.models.document import Document
from app.models.page import Page
from app.models.block import Block
from app.models.patch import Patch
from app.models.job import Job
from app.models.style_profile import DocumentProfile
from app.models.llm_usage import LlmUsage

from app.utils import minio_client
from app.services.ingestion import process_ingestion_sync
from app.services.extraction import extract_page_layout_sync
from app.services.analysis import analyze_document_sync
from app.services.correction import correct_page_blocks_sync, correct_docx_sync
from app.services.rendering import render_docx_first_sync
from app.models.section_summary import SectionSummary
from app.models.term_registry import TermRegistry

logger = logging.getLogger(__name__)

# Motor síncrono para Celery (no usa async)
sync_engine = create_engine(settings.database_url_sync, pool_size=5, max_overflow=10)
SyncSession = sessionmaker(bind=sync_engine)


def _update_document_status(db: Session, doc_id: str, status: str, **kwargs) -> None:
    """Helper para actualizar estado del documento."""
    values = {"status": status, "updated_at": datetime.now(timezone.utc)}
    values.update(kwargs)
    db.execute(
        update(Document).where(Document.id == doc_id).values(**values)
    )
    db.commit()


def _update_page_status(db: Session, page_id: str, status: str, **kwargs) -> None:
    """Helper para actualizar estado de una página."""
    values = {"status": status, "updated_at": datetime.now(timezone.utc)}
    values.update(kwargs)
    db.execute(
        update(Page).where(Page.id == page_id).values(**values)
    )
    db.commit()


def _create_job(db: Session, doc_id: str, task_type: str, celery_task_id: str, page_id: str = None) -> Job:
    """Crea un registro de job."""
    job = Job(
        doc_id=doc_id,
        page_id=page_id,
        task_type=task_type,
        celery_task_id=celery_task_id,
        status="running",
        started_at=datetime.now(timezone.utc),
    )
    db.add(job)
    db.commit()
    return job


def _complete_job(db: Session, job: Job, error: str = None) -> None:
    """Marca un job como completado o fallido."""
    job.finished_at = datetime.now(timezone.utc)
    if error:
        job.status = "failed"
        job.error = error
    else:
        job.status = "completed"
    db.commit()


@celery_app.task(bind=True, max_retries=3, name="tasks_pipeline.process_document_pipeline")
def process_document_pipeline(self, doc_id: str):
    """
    Pipeline completo para un documento.
    MVP 1: DOCX → PDF → extraer → corregir → renderizar.
    
    Se ejecuta como una sola tarea Celery por simplicidad en el MVP.
    En fases posteriores se dividirá en tareas encadenadas.
    """
    db = SyncSession()
    job = None

    try:
        # Obtener documento
        doc = db.execute(select(Document).where(Document.id == doc_id)).scalar_one()
        job = _create_job(db, doc_id, "full_pipeline", self.request.id)

        logger.info(f"=== INICIO PIPELINE: {doc.filename} ({doc_id}) ===")

        # =============================================
        # LIMPIEZA: eliminar datos previos (para re-procesamiento)
        # =============================================
        existing_pages = db.execute(
            select(Page).where(Page.doc_id == doc_id)
        ).scalars().all()
        if existing_pages:
            logger.info(f"Limpiando {len(existing_pages)} páginas previas para re-procesamiento...")
            for page in existing_pages:
                db.delete(page)  # CASCADE elimina blocks y patches
            db.commit()

        # Limpiar registros de costos previos
        db.execute(delete(LlmUsage).where(LlmUsage.doc_id == doc_id))
        # Limpiar análisis editorial previo (Lote 3)
        db.execute(delete(SectionSummary).where(SectionSummary.doc_id == doc_id))
        db.execute(delete(TermRegistry).where(TermRegistry.doc_id == doc_id))
        db.commit()

        # =============================================
        # ETAPA A: INGESTA — Convertir DOCX a PDF
        # =============================================
        _update_document_status(db, doc_id, "converting")
        logger.info(f"[Etapa A] Convirtiendo {doc.filename}...")

        ingestion_result = process_ingestion_sync(
            doc_id=str(doc_id),
            source_key=doc.source_uri,
            filename=doc.filename,
            original_format=doc.original_format,
        )

        pdf_uri = ingestion_result["pdf_uri"]
        total_pages = ingestion_result["total_pages"]

        # Actualizar documento
        _update_document_status(
            db, doc_id, "extracting",
            pdf_uri=pdf_uri,
            total_pages=total_pages,
        )

        # Crear registros de páginas
        for page_no in range(1, total_pages + 1):
            page = Page(
                doc_id=doc_id,
                page_no=page_no,
                page_type="digital",
                render_route="docx_first",
                status="pending",
            )
            db.add(page)
        db.commit()

        logger.info(f"[Etapa A] Completada: {total_pages} páginas creadas")

        # =============================================
        # ETAPA B: EXTRACCIÓN — Extraer layout de cada página
        # =============================================
        logger.info(f"[Etapa B] Extrayendo layout de {total_pages} páginas...")

        pages = db.execute(
            select(Page).where(Page.doc_id == doc_id).order_by(Page.page_no)
        ).scalars().all()

        all_page_blocks = {}

        for page in pages:
            _update_page_status(db, page.id, "extracting")

            try:
                extraction_result = extract_page_layout_sync(
                    doc_id=str(doc_id),
                    pdf_uri=pdf_uri,
                    page_no=page.page_no,
                )

                # Actualizar página con URIs
                _update_page_status(
                    db, page.id, "extracted",
                    layout_uri=extraction_result["layout_uri"],
                    text_uri=extraction_result["text_uri"],
                    preview_uri=extraction_result["preview_uri"],
                )

                # Crear registros de bloques
                for block_data in extraction_result["blocks"]:
                    block = Block(
                        page_id=page.id,
                        block_no=block_data["block_no"],
                        block_type=block_data["type"],
                        bbox_x0=block_data["bbox"][0],
                        bbox_y0=block_data["bbox"][1],
                        bbox_x1=block_data["bbox"][2],
                        bbox_y1=block_data["bbox"][3],
                        original_text=block_data.get("text", ""),
                        font_info=(
                            block_data["lines"][0]["spans"][0] 
                            if block_data.get("lines") and block_data["lines"][0].get("spans")
                            else None
                        ),
                    )
                    db.add(block)

                all_page_blocks[page.page_no] = extraction_result["blocks"]

            except Exception as e:
                logger.error(f"Error extrayendo página {page.page_no}: {e}")
                _update_page_status(db, page.id, "failed")

        db.commit()
        logger.info(f"[Etapa B] Completada: layouts extraídos")

        # =============================================
        # ETAPA C: ANÁLISIS EDITORIAL (MVP2 Lote 3)
        # =============================================
        _update_document_status(db, doc_id, "analyzing")
        logger.info(f"[Etapa C] Analizando documento...")

        # Cargar perfil editorial si existe
        profile_row = db.execute(
            select(DocumentProfile).where(DocumentProfile.doc_id == doc_id)
        ).scalar_one_or_none()

        profile_dict = None
        if profile_row:
            profile_dict = {
                "register": profile_row.register,
                "intervention_level": profile_row.intervention_level,
                "audience_type": profile_row.audience_type,
                "audience_expertise": profile_row.audience_expertise,
                "tone": profile_row.tone,
                "preserve_author_voice": profile_row.preserve_author_voice,
                "max_rewrite_ratio": profile_row.max_rewrite_ratio,
                "max_expansion_ratio": profile_row.max_expansion_ratio,
                "style_priorities": profile_row.style_priorities or [],
                "protected_terms": profile_row.protected_terms or [],
                "forbidden_changes": profile_row.forbidden_changes or [],
                "lt_disabled_rules": profile_row.lt_disabled_rules or [],
            }
            logger.info(f"[Etapa C] Perfil editorial: {profile_row.preset_name or 'custom'}")

        analysis_result = analyze_document_sync(
            doc_id=str(doc_id),
            docx_uri=doc.source_uri,
            profile=profile_dict,
        )

        # Guardar secciones en BD
        for sec_data in analysis_result.get("sections", []):
            section = SectionSummary(
                doc_id=doc_id,
                section_index=sec_data["section_index"],
                section_title=sec_data.get("section_title"),
                start_paragraph=sec_data["start_paragraph"],
                end_paragraph=sec_data["end_paragraph"],
                summary_text=sec_data.get("summary_text"),
                topic=sec_data.get("topic"),
                local_tone=sec_data.get("local_tone"),
                active_terms=sec_data.get("active_terms", []),
                transition_from_previous=sec_data.get("transition_from_previous"),
            )
            db.add(section)

        # Guardar términos en BD
        for term_data in analysis_result.get("terms", []):
            term = TermRegistry(
                doc_id=doc_id,
                term=term_data["term"],
                normalized_form=term_data["normalized_form"],
                frequency=term_data["frequency"],
                first_occurrence_paragraph=term_data["first_occurrence_paragraph"],
                is_protected=term_data["is_protected"],
                decision=term_data["decision"],
            )
            db.add(term)

        # Guardar registros de costos del análisis
        for record in analysis_result.get("usage_records", []):
            db.add(LlmUsage(doc_id=doc_id, **record))

        # Actualizar perfil con campos inferidos si hay updates
        profile_updates = analysis_result.get("profile_updates", {})
        if profile_updates and profile_row:
            for key, value in profile_updates.items():
                if hasattr(profile_row, key):
                    setattr(profile_row, key, value)
            logger.info(f"[Etapa C] Perfil actualizado con inferencia: {list(profile_updates.keys())}")

        # Actualizar profile_dict con los nuevos datos (para uso en Etapa D)
        if profile_dict and profile_updates:
            profile_dict.update(profile_updates)

        # Merge términos protegidos del análisis al perfil para Etapa D
        if profile_dict:
            analysis_protected = [
                t["term"] for t in analysis_result.get("terms", []) if t["is_protected"]
            ]
            existing_protected = set(profile_dict.get("protected_terms", []))
            new_terms = [t for t in analysis_protected if t not in existing_protected]
            if new_terms:
                profile_dict["protected_terms"] = list(existing_protected) + new_terms
                logger.info(f"[Etapa C] {len(new_terms)} términos protegidos agregados al perfil")

        # Persistir paragraph_classifications en MinIO para el endpoint /analysis
        classifications = analysis_result.get("paragraph_classifications", [])
        if classifications:
            cls_key = f"analysis/{doc_id}/classifications.json"
            cls_bytes = json.dumps(classifications, ensure_ascii=False).encode("utf-8")
            minio_client.upload_file(cls_key, cls_bytes, content_type="application/json")
            logger.info(f"[Etapa C] {len(classifications)} clasificaciones guardadas en MinIO")

        db.commit()
        logger.info(
            f"[Etapa C] Completada: "
            f"{len(analysis_result.get('sections', []))} secciones, "
            f"{len(analysis_result.get('terms', []))} términos"
        )

        # =============================================
        # ETAPA D: CORRECCIÓN — LanguageTool + ChatGPT
        # =============================================
        _update_document_status(db, doc_id, "correcting")
        logger.info(f"[Etapa D] Corrigiendo texto...")

        config = doc.config_json or {}

        # Recargar páginas después del commit
        pages = db.execute(
            select(Page).where(Page.doc_id == doc_id).order_by(Page.page_no)
        ).scalars().all()

        # Para Ruta 1 (DOCX-first): corregir directamente desde el DOCX
        # Esto evita el bug de fragmentación PDF → mayúsculas aleatorias
        docx_patches = []
        if doc.original_format == "docx":
            # Perfil ya cargado y enriquecido en Etapa C
            if profile_dict:
                logger.info(f"[Etapa D] Usando perfil editorial enriquecido por análisis")

            logger.info("[Etapa D] Ruta 1: corrigiendo párrafos directamente del DOCX...")
            docx_patches, usage_records = correct_docx_sync(
                doc_id=str(doc_id),
                docx_uri=doc.source_uri,
                config=config,
                profile=profile_dict,
                analysis_data=analysis_result,
            )

            # Insertar registros granulares de costos en llm_usage
            for record in usage_records:
                db.add(LlmUsage(doc_id=doc_id, **record))
            db.commit()

            total_prompt = sum(r["prompt_tokens"] for r in usage_records)
            total_completion = sum(r["completion_tokens"] for r in usage_records)
            total_tokens = sum(r["total_tokens"] for r in usage_records)
            total_cost = sum(r["cost_usd"] for r in usage_records)
            logger.info(
                f"[Etapa D] Tokens: {total_tokens} "
                f"(prompt={total_prompt}, completion={total_completion}), "
                f"costo=${total_cost:.6f} USD, "
                f"llamadas: {len(usage_records)}"
            )

            # ── Build block index for text-similarity matching ──
            all_blocks = []  # list of (Block, page_index)
            for pi, page in enumerate(pages):
                page_blocks = db.execute(
                    select(Block)
                    .where(Block.page_id == page.id, Block.block_type == "text")
                    .order_by(Block.block_no)
                ).scalars().all()
                for block in page_blocks:
                    all_blocks.append((block, pi))

            def _normalize_text(text: str) -> str:
                return re.sub(r'\s+', ' ', text.lower().strip())

            def _find_best_block(original_text: str, para_idx: int, total_paras: int):
                if not all_blocks:
                    return None
                norm_patch = _normalize_text(original_text)
                if not norm_patch:
                    # Fallback proporcional por página
                    if total_paras > 0 and pages:
                        est_page = min(int(para_idx / total_paras * len(pages)), len(pages) - 1)
                        for block, pi in all_blocks:
                            if pi == est_page:
                                return block
                    return all_blocks[0][0]

                best_block = None
                best_score = 0.0
                for block, pi in all_blocks:
                    block_text = block.original_text or ""
                    norm_block = _normalize_text(block_text)
                    if not norm_block:
                        continue
                    score = SequenceMatcher(None, norm_patch[:300], norm_block[:300]).ratio()
                    if score > best_score:
                        best_score = score
                        best_block = block

                if best_score < 0.3:
                    # Similitud muy baja → fallback proporcional
                    if total_paras > 0 and pages:
                        est_page = min(int(para_idx / total_paras * len(pages)), len(pages) - 1)
                        for block, pi in all_blocks:
                            if pi == est_page:
                                return block
                    return all_blocks[0][0]
                return best_block

            total_paragraphs = len(docx_patches)

            # Registrar parches en BD (vinculados por similitud textual)
            patch_version = 1
            for patch_data in docx_patches:
                para_idx = patch_data.get("paragraph_index", 0)
                db_block = _find_best_block(
                    patch_data.get("original_text", ""),
                    para_idx,
                    total_paragraphs,
                )
                if db_block:
                    # MVP2: si hay cambios individuales del LLM, crear un patch por cambio
                    llm_changes = patch_data.get("changes", [])
                    route = patch_data.get("route_taken")
                    p_review_status = patch_data.get("review_status", "auto_accepted")
                    p_review_reason = patch_data.get("review_reason")
                    p_gate_results = patch_data.get("gate_results")
                    if llm_changes:
                        for change in llm_changes:
                            patch = Patch(
                                block_id=db_block.id,
                                version=patch_version,
                                source=patch_data["source"],
                                original_text=patch_data["original_text"],
                                corrected_text=patch_data["corrected_text"],
                                operations_json=patch_data.get("lt_operations", []),
                                review_status=p_review_status,
                                review_reason=p_review_reason,
                                gate_results=p_gate_results,
                                applied=False,
                                category=change.get("category"),
                                severity=change.get("severity"),
                                explanation=change.get("explanation"),
                                confidence=patch_data.get("confidence"),
                                rewrite_ratio=patch_data.get("rewrite_ratio"),
                                pass_number=2 if "chatgpt" in patch_data["source"] else 1,
                                model_used=patch_data.get("model_used", "languagetool"),
                                paragraph_index=para_idx,
                                route_taken=route,
                            )
                            db.add(patch)
                            patch_version += 1
                    else:
                        # MVP1 fallback o solo LanguageTool
                        patch = Patch(
                            block_id=db_block.id,
                            version=patch_version,
                            source=patch_data["source"],
                            original_text=patch_data["original_text"],
                            corrected_text=patch_data["corrected_text"],
                            operations_json=patch_data.get("lt_operations", []),
                            review_status=p_review_status,
                            review_reason=p_review_reason,
                            gate_results=p_gate_results,
                            applied=False,
                            confidence=patch_data.get("confidence"),
                            rewrite_ratio=patch_data.get("rewrite_ratio"),
                            pass_number=1,
                            model_used=patch_data.get("model_used", "languagetool"),
                            paragraph_index=para_idx,
                            route_taken=route,
                        )
                        db.add(patch)
                        patch_version += 1

            # Marcar todas las páginas como corregidas
            for page in pages:
                if page.status != "failed":
                    _update_page_status(db, page.id, "corrected")

        db.commit()
        logger.info(f"[Etapa D] Completada: {len(docx_patches)} párrafos corregidos")

        # =============================================
        # ETAPA E: RENDERIZADO — Ruta 1 (DOCX-first)
        # =============================================
        _update_document_status(db, doc_id, "rendering")
        logger.info(f"[Etapa E] Renderizando documento corregido...")

        if docx_patches and doc.original_format == "docx":
            render_result = render_docx_first_sync(
                doc_id=str(doc_id),
                docx_uri=doc.source_uri,
                filename=doc.filename,
                all_patches=docx_patches,
            )

            # Marcar parches como aplicados
            db.execute(
                update(Patch)
                .where(Patch.block_id.in_(
                    select(Block.id).join(Page).where(Page.doc_id == doc_id)
                ))
                .where(Patch.review_status == "auto_accepted")
                .values(applied=True)
            )

            # Actualizar páginas como renderizadas
            for page in pages:
                if page.status != "failed":
                    _update_page_status(db, page.id, "rendered")

            _update_document_status(db, doc_id, "completed")
            logger.info(
                f"[Etapa E] Completada: {render_result.get('changes_count', 0)} correcciones aplicadas"
            )
        else:
            if not docx_patches:
                logger.info("[Etapa E] Sin correcciones que aplicar — documento limpio")
            _update_document_status(db, doc_id, "completed")

        _complete_job(db, job)
        logger.info(f"=== PIPELINE COMPLETADO: {doc.filename} ===")

    except Exception as e:
        logger.exception(f"Error en pipeline: {e}")
        try:
            db.rollback()
        except Exception:
            pass
        if job:
            _complete_job(db, job, error=str(e))
        try:
            _update_document_status(db, doc_id, "failed", error_message=str(e))
        except Exception:
            pass
        self.retry(exc=e, countdown=60)

    finally:
        db.close()
