"""
Endpoints de documentos — MVP 1 + MVP 2 (Lote 1: perfiles editoriales).
Upload, listado, detalle, descarga de resultados, perfiles editoriales.
"""

import io
import logging
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.config import settings
from app.models.document import Document
from app.models.page import Page
from app.models.block import Block
from app.models.patch import Patch
from app.models.style_profile import DocumentProfile
from app.models.llm_usage import LlmUsage
from app.schemas.document import (
    DocumentUploadResponse, DocumentDetail, DocumentListItem,
    ProgressDetail,
    CostSummary, DocumentCostItem, ParagraphCostItem,
    CorrectionBatchStatus,
)
from app.schemas.page import PageListItem
from app.schemas.patch import (
    PatchDetail, PatchListItem,
    PatchReviewAction, BulkPatchReviewAction,
    FinalizeRequest, ReviewSummary,
    ManualEditRequest, RecorrectionRequest,
)
from app.schemas.analysis import AnalysisResult, SectionSummaryItem, TermRegistryItem, InferredProfile
from app.models.section_summary import SectionSummary
from app.models.term_registry import TermRegistry
from app.models.correction_batch import CorrectionBatch
from app.models.document_global_context import DocumentGlobalContext
from app.models.llm_audit_log import LlmAuditLog
from app.schemas.style_profile import (
    StyleProfileCreate, StyleProfileUpdate, StyleProfileResponse, PresetListItem
)
from app.services.ingestion import ingest_document
from app.services.context_accumulator import ContextualCorrectionService, generate_sample_document_flow
from app.workers.tasks_pipeline import process_document_pipeline, render_approved_patches, recorrect_single_patch, rerender_candidate_preview
from app.utils import minio_client
from app.data.profiles import get_preset, list_presets_ui, PRESETS

logger = logging.getLogger(__name__)

# Instancia del servicio de contexto (en producción sería singleton/DI)
context_service = ContextualCorrectionService()

router = APIRouter(tags=["documents"])


# =============================================
# UPLOAD
# =============================================

@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """
    Sube un documento DOCX y lanza el pipeline de procesamiento.
    """
    # Validar formato
    if not file.filename:
        raise HTTPException(400, "Nombre de archivo requerido")

    filename_lower = file.filename.lower()
    if not filename_lower.endswith(".docx"):
        raise HTTPException(
            400,
            "MVP 1 solo acepta archivos .docx. Soporte PDF en fase posterior."
        )

    # Validar tamaño
    file_data = await file.read()
    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    if len(file_data) > max_bytes:
        raise HTTPException(
            413,
            f"Archivo demasiado grande. Máximo: {settings.max_upload_size_mb} MB"
        )

    # Ingestar documento
    document = await ingest_document(db, file_data, file.filename)
    await db.commit()
    await db.refresh(document)

    logger.info(f"Documento subido: doc={document.id}, filename={document.filename}")

    return DocumentUploadResponse(
        id=document.id,
        filename=document.filename,
        original_format=document.original_format,
        status=document.status,
        message="Documento recibido. Selecciona un perfil editorial para iniciar el procesamiento.",
    )


# =============================================
# PROCESAR (lanza pipeline Celery — separado de upload)
# =============================================

@router.post("/documents/{doc_id}/process")
async def process_document(
    doc_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Lanza el pipeline de procesamiento para un documento ya subido.
    Requiere que el documento esté en status 'uploaded'.
    """
    doc = await _get_doc_or_404(db, doc_id)

    allowed_statuses = ("uploaded", "failed", "completed")
    if doc.status not in allowed_statuses:
        raise HTTPException(
            400,
            f"Solo se puede procesar un documento en status {allowed_statuses}. Status actual: {doc.status}"
        )

    # Reset status para reprocesamiento
    if doc.status != "uploaded":
        doc.status = "uploaded"
        doc.error_message = None
        await db.commit()

    # Inicializar contexto de corrección
    document_info = {
        "filename": doc.filename,
        "format": doc.original_format,
        "status": doc.status,
    }
    context_service.init_document_context(str(doc.id), document_info)

    # Lanzar pipeline
    task = process_document_pipeline.delay(str(doc.id))
    logger.info(f"Pipeline lanzado: doc={doc.id}, task={task.id}")

    return {"message": "Procesamiento iniciado", "task_id": task.id}


# =============================================
# PERFILES EDITORIALES
# =============================================

@router.get("/presets", response_model=list[PresetListItem])
async def list_available_presets():
    """Lista los 10 perfiles editoriales predeterminados."""
    return list_presets_ui()


@router.post("/documents/{doc_id}/profile", response_model=StyleProfileResponse)
async def create_profile(
    doc_id: UUID,
    body: StyleProfileCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    Crea el perfil editorial de un documento.
    Si preset_name viene, carga valores del preset y aplica overrides.
    Si no viene preset, crea perfil con defaults + overrides.
    """
    doc = await _get_doc_or_404(db, doc_id)

    # Verificar que no tenga perfil ya
    existing = await db.execute(
        select(DocumentProfile).where(DocumentProfile.doc_id == doc_id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(400, "El documento ya tiene un perfil. Usa PUT para actualizar.")

    # Base: preset o defaults
    if body.preset_name and body.preset_name in PRESETS:
        base = get_preset(body.preset_name)
        source = "preset"
    else:
        base = {
            "genre": None,
            "subgenre": None,
            "audience_type": None,
            "audience_age_range": None,
            "audience_expertise": "medio",
            "register": "neutro",
            "tone": "neutro",
            "intervention_level": "moderada",
            "preserve_author_voice": True,
            "max_rewrite_ratio": 0.30,
            "max_expansion_ratio": 1.10,
            "target_inflesz_min": None,
            "target_inflesz_max": None,
            "style_priorities": ["claridad", "fluidez", "cohesion", "precision_lexica"],
            "protected_terms": [],
            "forbidden_changes": [],
            "lt_disabled_rules": [],
        }
        source = "user" if not body.preset_name else "user"

    # Aplicar overrides del body
    overrides = body.model_dump(exclude_unset=True, exclude={"preset_name"})
    for key, value in overrides.items():
        if value is not None:
            base[key] = value

    profile = DocumentProfile(
        doc_id=doc_id,
        preset_name=body.preset_name,
        source=source,
        **base,
    )
    db.add(profile)
    await db.commit()
    await db.refresh(profile)

    logger.info(f"Perfil creado: doc={doc_id}, preset={body.preset_name}, source={source}")
    return profile


@router.get("/documents/{doc_id}/profile", response_model=StyleProfileResponse)
async def get_profile(
    doc_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Lee el perfil editorial de un documento."""
    await _get_doc_or_404(db, doc_id)

    result = await db.execute(
        select(DocumentProfile).where(DocumentProfile.doc_id == doc_id)
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(404, "El documento no tiene perfil editorial configurado.")
    return profile


@router.put("/documents/{doc_id}/profile", response_model=StyleProfileResponse)
async def update_profile(
    doc_id: UUID,
    body: StyleProfileUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Actualiza el perfil editorial de un documento."""
    await _get_doc_or_404(db, doc_id)

    result = await db.execute(
        select(DocumentProfile).where(DocumentProfile.doc_id == doc_id)
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(404, "El documento no tiene perfil. Usa POST para crear uno.")

    updates = body.model_dump(exclude_unset=True)
    for key, value in updates.items():
        if value is not None:
            setattr(profile, key, value)

    profile.source = "user"  # Si el usuario modifica, la fuente es "user"
    await db.commit()
    await db.refresh(profile)

    logger.info(f"Perfil actualizado: doc={doc_id}")
    return profile


# =============================================
# LISTADO (Dashboard)
# =============================================

@router.get("/documents", response_model=list[DocumentListItem])
async def list_documents(
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    """Lista todos los documentos (dashboard)."""
    result = await db.execute(
        select(Document)
        .order_by(Document.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    documents = result.scalars().all()

    items = []
    for doc in documents:
        progress = _calculate_progress(doc)
        items.append(DocumentListItem(
            id=doc.id,
            filename=doc.filename,
            original_format=doc.original_format,
            status=doc.status,
            total_pages=doc.total_pages,
            created_at=doc.created_at,
            progress=progress,
            progress_detail=_build_progress_detail(doc),
        ))

    return items


# =============================================
# DETALLE
# =============================================

@router.get("/documents/{doc_id}", response_model=DocumentDetail)
async def get_document(
    doc_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Obtiene detalle completo de un documento."""
    result = await db.execute(
        select(Document).where(Document.id == doc_id)
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(404, "Documento no encontrado")

    progress = _calculate_progress(doc)
    progress_detail = _build_progress_detail(doc)
    pages_summary = await _get_pages_summary(db, doc_id)

    # Agregar costos desde llm_usage (con fallback a columnas viejas)
    cost_row = await db.execute(
        select(
            func.coalesce(func.sum(LlmUsage.prompt_tokens), 0),
            func.coalesce(func.sum(LlmUsage.completion_tokens), 0),
            func.coalesce(func.sum(LlmUsage.total_tokens), 0),
            func.coalesce(func.sum(LlmUsage.cost_usd), 0.0),
        ).where(LlmUsage.doc_id == doc_id)
    )
    prompt_t, completion_t, total_t, cost_usd = cost_row.one()
    # Fallback: docs procesados antes del cambio tienen datos en columnas viejas
    if int(total_t) == 0 and doc.total_tokens and doc.total_tokens > 0:
        prompt_t = doc.prompt_tokens or 0
        completion_t = doc.completion_tokens or 0
        total_t = doc.total_tokens or 0
        cost_usd = doc.llm_cost_usd or 0.0

    return DocumentDetail(
        id=doc.id,
        filename=doc.filename,
        original_format=doc.original_format,
        status=doc.status,
        total_pages=doc.total_pages,
        config_json=doc.config_json or {},
        error_message=doc.error_message,
        source_uri=doc.source_uri,
        pdf_uri=doc.pdf_uri,
        docx_uri=doc.docx_uri,
        created_at=doc.created_at,
        updated_at=doc.updated_at,
        progress=progress,
        progress_detail=progress_detail,
        pages_summary=pages_summary,
        prompt_tokens=int(prompt_t),
        completion_tokens=int(completion_t),
        total_tokens=int(total_t),
        llm_cost_usd=float(cost_usd),
    )


# =============================================
# PÁGINAS
# =============================================

@router.get("/documents/{doc_id}/pages", response_model=list[PageListItem])
async def list_pages(
    doc_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Lista las páginas de un documento con su estado."""
    result = await db.execute(
        select(Page).where(Page.doc_id == doc_id).order_by(Page.page_no)
    )
    pages = result.scalars().all()

    items = []
    for page in pages:
        # Contar parches de esta página
        patches_count = await db.scalar(
            select(func.count(Patch.id))
            .join(Block)
            .where(Block.page_id == page.id)
        )
        items.append(PageListItem(
            id=page.id,
            page_no=page.page_no,
            page_type=page.page_type,
            render_route=page.render_route,
            status=page.status,
            preview_uri=page.preview_uri,
            patches_count=patches_count or 0,
            has_corrections=(patches_count or 0) > 0,
        ))

    return items


# =============================================
# PARCHES / CORRECCIONES
# =============================================

@router.get("/documents/{doc_id}/corrections", response_model=list[PatchListItem])
async def list_corrections(
    doc_id: UUID,
    review_status: str | None = None,
    page_no: int | None = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Lista correcciones de un documento con filtros opcionales.
    """
    query = (
        select(Patch, Block.block_no)
        .join(Block)
        .join(Page)
        .where(Page.doc_id == doc_id)
    )
    if review_status:
        query = query.where(Patch.review_status == review_status)
    if page_no is not None:
        query = query.where(Page.page_no == page_no)
    query = query.order_by(Page.page_no, Block.block_no)
    result = await db.execute(query)
    rows = result.all()

    # Obtener costos por paragraph_index para vincular a cada patch
    usage_result = await db.execute(
        select(LlmUsage.paragraph_index, LlmUsage.cost_usd)
        .where(LlmUsage.doc_id == doc_id)
    )
    cost_by_paragraph: dict[int, float] = {
        row.paragraph_index: row.cost_usd for row in usage_result.all()
    }

    items = []
    for patch, block_no in rows:
        patch_cost = cost_by_paragraph.get(patch.paragraph_index) if patch.paragraph_index is not None else None
        items.append(PatchListItem(
            id=patch.id,
            block_id=patch.block_id,
            block_no=block_no,
            version=patch.version,
            source=patch.source,
            original_text=patch.original_text,
            corrected_text=patch.corrected_text,
            review_status=patch.review_status,
            overflow_flag=patch.overflow_flag,
            created_at=patch.created_at,
            # MVP2 — campos enriquecidos
            category=patch.category,
            severity=patch.severity,
            explanation=patch.explanation,
            confidence=patch.confidence,
            rewrite_ratio=patch.rewrite_ratio,
            pass_number=patch.pass_number,
            model_used=patch.model_used,
            cost_usd=patch_cost,
            route_taken=patch.route_taken,
            gate_results=patch.gate_results,
            review_reason=patch.review_reason,
            reviewed_at=patch.reviewed_at,
            reviewer_note=patch.reviewer_note,
            decision_source=patch.decision_source,
            edited_text=patch.edited_text if hasattr(patch, 'edited_text') else None,
            edited_at=patch.edited_at if hasattr(patch, 'edited_at') else None,
            recorrection_count=patch.recorrection_count if hasattr(patch, 'recorrection_count') else 0,
        ))

    return items


# =============================================
# REVISIÓN HUMANA (Human-in-the-Loop)
# =============================================

@router.get("/documents/{doc_id}/review-summary", response_model=ReviewSummary)
async def get_review_summary(
    doc_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Resumen del estado de revisión de correcciones de un documento."""
    doc = await _get_doc_or_404(db, doc_id)

    # Conteo por review_status
    result = await db.execute(
        select(Patch.review_status, func.count(Patch.id))
        .join(Block)
        .join(Page)
        .where(Page.doc_id == doc_id)
        .group_by(Patch.review_status)
    )
    counts = {status: count for status, count in result.all()}

    total = sum(counts.values())
    pending = counts.get("pending", 0)
    manual_review = counts.get("manual_review", 0)

    # Desglose por severidad
    sev_result = await db.execute(
        select(Patch.severity, func.count(Patch.id))
        .join(Block).join(Page)
        .where(Page.doc_id == doc_id, Patch.severity.isnot(None))
        .group_by(Patch.severity)
    )
    by_severity = {sev: cnt for sev, cnt in sev_result.all()}

    # Desglose por página (pendientes y manual_review por página)
    page_result = await db.execute(
        select(Page.page_no, Patch.review_status, func.count(Patch.id))
        .select_from(Patch).join(Block).join(Page)
        .where(Page.doc_id == doc_id)
        .group_by(Page.page_no, Patch.review_status)
    )
    by_page: dict[int, dict[str, int]] = {}
    for page_no, status, cnt in page_result.all():
        by_page.setdefault(page_no, {})[status] = cnt

    return ReviewSummary(
        total_patches=total,
        auto_accepted=counts.get("auto_accepted", 0),
        pending=pending,
        accepted=counts.get("accepted", 0),
        rejected=counts.get("rejected", 0),
        manual_review=manual_review,
        gate_rejected=counts.get("gate_rejected", 0),
        bulk_finalized=counts.get("bulk_finalized", 0),
        can_finalize_strict=(pending == 0 and manual_review == 0),
        can_finalize_quick=(total > 0),
        render_version=doc.render_version if hasattr(doc, 'render_version') else 1,
        by_severity=by_severity,
        by_page=by_page,
    )


@router.get("/documents/{doc_id}/corrections/{patch_id}", response_model=PatchListItem)
async def get_single_correction(
    doc_id: UUID,
    patch_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Obtiene un patch individual (para polling post-recorrección)."""
    result = await db.execute(
        select(Patch, Block.block_no)
        .join(Block, Patch.block_id == Block.id)
        .join(Page, Block.page_id == Page.id)
        .where(Page.doc_id == doc_id, Patch.id == patch_id)
    )
    row = result.first()
    if not row:
        raise HTTPException(404, "Corrección no encontrada")
    patch, block_no = row

    # Costo
    patch_cost = None
    if patch.paragraph_index is not None:
        cost_result = await db.execute(
            select(LlmUsage.cost_usd)
            .where(LlmUsage.doc_id == doc_id, LlmUsage.paragraph_index == patch.paragraph_index)
        )
        cost_row = cost_result.scalar()
        patch_cost = cost_row

    return PatchListItem(
        id=patch.id,
        block_id=patch.block_id,
        block_no=block_no,
        version=patch.version,
        source=patch.source,
        original_text=patch.original_text,
        corrected_text=patch.corrected_text,
        review_status=patch.review_status,
        overflow_flag=patch.overflow_flag,
        created_at=patch.created_at,
        category=patch.category,
        severity=patch.severity,
        explanation=patch.explanation,
        confidence=patch.confidence,
        rewrite_ratio=patch.rewrite_ratio,
        pass_number=patch.pass_number,
        model_used=patch.model_used,
        cost_usd=patch_cost,
        route_taken=patch.route_taken,
        gate_results=patch.gate_results,
        review_reason=patch.review_reason,
        reviewed_at=patch.reviewed_at,
        reviewer_note=patch.reviewer_note,
        decision_source=patch.decision_source,
        edited_text=patch.edited_text if hasattr(patch, 'edited_text') else None,
        edited_at=patch.edited_at if hasattr(patch, 'edited_at') else None,
        recorrection_count=patch.recorrection_count if hasattr(patch, 'recorrection_count') else 0,
    )


@router.patch("/documents/{doc_id}/corrections/{patch_id}")
async def review_correction(
    doc_id: UUID,
    patch_id: UUID,
    body: PatchReviewAction,
    db: AsyncSession = Depends(get_db),
):
    """Acepta o rechaza una corrección individual."""
    doc = await _get_doc_or_404(db, doc_id)

    if doc.status not in ("pending_review", "candidate_ready", "completed"):
        raise HTTPException(
            400,
            f"Solo se pueden revisar correcciones en status 'candidate_ready', 'pending_review' o 'completed'. "
            f"Status actual: {doc.status}"
        )

    # Verificar que el patch pertenece al documento
    result = await db.execute(
        select(Patch)
        .join(Block)
        .join(Page)
        .where(Page.doc_id == doc_id, Patch.id == patch_id)
    )
    patch = result.scalar_one_or_none()
    if not patch:
        raise HTTPException(404, "Corrección no encontrada en este documento")

    from datetime import datetime, timezone
    patch.review_status = body.action
    patch.reviewed_at = datetime.now(timezone.utc)
    patch.reviewer_note = body.reviewer_note
    patch.decision_source = "human"

    await db.commit()
    logger.info(f"Patch {patch_id} → {body.action} (doc={doc_id})")
    return {"message": f"Corrección {body.action}", "patch_id": str(patch_id)}


@router.post("/documents/{doc_id}/corrections/bulk-action")
async def bulk_review_corrections(
    doc_id: UUID,
    body: BulkPatchReviewAction,
    db: AsyncSession = Depends(get_db),
):
    """Acepta o rechaza múltiples correcciones a la vez."""
    doc = await _get_doc_or_404(db, doc_id)

    if doc.status not in ("pending_review", "candidate_ready", "completed"):
        raise HTTPException(
            400,
            f"Solo se pueden revisar correcciones en status 'candidate_ready', 'pending_review' o 'completed'. "
            f"Status actual: {doc.status}"
        )

    if not body.patch_ids:
        raise HTTPException(400, "Lista de patch_ids vacía")

    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)

    # Verificar que todos los patches pertenecen al documento
    result = await db.execute(
        select(Patch)
        .join(Block)
        .join(Page)
        .where(Page.doc_id == doc_id, Patch.id.in_(body.patch_ids))
    )
    patches = result.scalars().all()

    if len(patches) != len(body.patch_ids):
        found_ids = {str(p.id) for p in patches}
        missing = [str(pid) for pid in body.patch_ids if str(pid) not in found_ids]
        raise HTTPException(404, f"Correcciones no encontradas: {missing[:5]}")

    for patch in patches:
        patch.review_status = body.action
        patch.reviewed_at = now
        patch.reviewer_note = body.reviewer_note
        patch.decision_source = "human"

    await db.commit()
    logger.info(f"Bulk {body.action}: {len(patches)} patches (doc={doc_id})")
    return {
        "message": f"{len(patches)} correcciones {body.action}",
        "count": len(patches),
    }


@router.post("/documents/{doc_id}/finalize")
async def finalize_document(
    doc_id: UUID,
    body: FinalizeRequest = FinalizeRequest(),
    db: AsyncSession = Depends(get_db),
):
    """
    Finaliza la revisión y lanza el renderizado.
    mode=quick: pendientes → bulk_finalized (se aplican). No bloquea.
    mode=strict: requiere 0 pendientes y 0 manual_review.
    """
    doc = await _get_doc_or_404(db, doc_id)

    if doc.status not in ("pending_review", "candidate_ready"):
        raise HTTPException(
            400,
            f"Solo se puede finalizar un documento en status 'candidate_ready' o 'pending_review'. "
            f"Status actual: {doc.status}"
        )

    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)

    if body.mode == "strict":
        # Verificar que no haya pendientes ni manual_review
        result = await db.execute(
            select(func.count(Patch.id))
            .join(Block).join(Page)
            .where(
                Page.doc_id == doc_id,
                Patch.review_status.in_(("pending", "manual_review")),
            )
        )
        unresolved = result.scalar() or 0
        if unresolved > 0:
            raise HTTPException(
                400,
                f"Modo estricto: quedan {unresolved} correcciones sin resolver (pendientes o en revisión manual). "
                "Resuélvelas antes de finalizar o usa modo rápido."
            )
    else:
        # Modo quick: convertir pendientes y manual_review en bulk_finalized
        result = await db.execute(
            select(Patch)
            .join(Block).join(Page)
            .where(
                Page.doc_id == doc_id,
                Patch.review_status.in_(("pending", "manual_review")),
            )
        )
        pending_patches = result.scalars().all()
        for patch in pending_patches:
            patch.review_status = "bulk_finalized"
            patch.reviewed_at = now
            patch.decision_source = "bulk_finalize"
        if pending_patches:
            await db.commit()
            logger.info(f"Finalize quick: {len(pending_patches)} patches → bulk_finalized (doc={doc_id})")

    # Lanzar tarea Celery de renderizado
    task = render_approved_patches.delay(str(doc.id), body.apply_mode)
    logger.info(f"Renderizado lanzado: doc={doc.id}, mode={body.mode}, apply={body.apply_mode}, task={task.id}")

    return {
        "message": "Renderizado iniciado",
        "task_id": task.id,
        "apply_mode": body.apply_mode,
        "finalize_mode": body.mode,
    }


@router.post("/documents/{doc_id}/reopen")
async def reopen_document(
    doc_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Reabre un documento completado para continuar revisando correcciones.
    Vuelve a candidate_ready para permitir edición, recorrección y re-renderizado.
    """
    doc = await _get_doc_or_404(db, doc_id)

    if doc.status != "completed":
        raise HTTPException(
            400,
            f"Solo se pueden reabrir documentos completados. Status actual: {doc.status}"
        )

    doc.status = "candidate_ready"
    doc.processing_completed_at = None
    await db.commit()

    logger.info(f"Documento {doc_id} reabierto → candidate_ready (render_version={doc.render_version})")
    return {
        "message": "Documento reabierto para revisión",
        "status": "candidate_ready",
        "render_version": doc.render_version if hasattr(doc, 'render_version') else 1,
    }


@router.post("/documents/{doc_id}/rerender-preview")
async def rerender_preview(
    doc_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Re-renderiza el preview candidato usando el estado actual de patches (con edited_text).
    Lanza una tarea Celery en background. Retorna task_id para polling de estado.
    """
    doc = await _get_doc_or_404(db, doc_id)
    if doc.status not in ("candidate_ready", "pending_review", "completed"):
        raise HTTPException(
            400,
            f"No se puede re-renderizar en status '{doc.status}'. "
            "Requiere candidate_ready, pending_review o completed."
        )
    task = rerender_candidate_preview.delay(str(doc_id))
    logger.info(f"Re-render preview iniciado: doc={doc_id}, task={task.id}")
    return {"task_id": task.id, "message": "Re-render de preview iniciado"}


@router.get("/tasks/{task_id}/status")
async def get_task_status(task_id: str):
    """Verifica el estado de un task Celery (para polling de re-render)."""
    from app.workers.celery_app import celery_app as _celery_app
    result = _celery_app.AsyncResult(task_id)
    return {
        "task_id": task_id,
        "status": result.state,   # PENDING | STARTED | SUCCESS | FAILURE | RETRY
        "ready": result.ready(),
    }


@router.patch("/documents/{doc_id}/corrections/{patch_id}/edit")
async def manual_edit_correction(
    doc_id: UUID,
    patch_id: UUID,
    body: ManualEditRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Edita manualmente el texto corregido de un patch.
    El edited_text reemplaza corrected_text en el próximo render.
    """
    doc = await _get_doc_or_404(db, doc_id)

    if doc.status not in ("pending_review", "candidate_ready", "completed"):
        raise HTTPException(400, f"No se puede editar en status {doc.status}")

    result = await db.execute(
        select(Patch).join(Block).join(Page)
        .where(Page.doc_id == doc_id, Patch.id == patch_id)
    )
    patch = result.scalar_one_or_none()
    if not patch:
        raise HTTPException(404, "Corrección no encontrada en este documento")

    # Validar longitud vs original (máx 200% del original)
    if len(body.edited_text) > len(patch.original_text) * 2 + 100:
        raise HTTPException(400, "Texto editado excesivamente largo respecto al original")

    from datetime import datetime, timezone
    patch.edited_text = body.edited_text
    patch.edited_at = datetime.now(timezone.utc)
    patch.review_status = "accepted"
    patch.decision_source = "manual_edit"
    patch.reviewer_note = body.reviewer_note

    await db.commit()
    logger.info(f"Patch {patch_id} editado manualmente (doc={doc_id})")
    return {"message": "Corrección editada", "patch_id": str(patch_id)}


@router.post("/documents/{doc_id}/corrections/{patch_id}/recorrect")
async def recorrect_patch(
    doc_id: UUID,
    patch_id: UUID,
    body: RecorrectionRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Solicita recorrección IA de un patch individual con feedback del usuario.
    Límite: 3 recorrecciones por patch, 20 por documento por hora.
    """
    doc = await _get_doc_or_404(db, doc_id)

    if doc.status not in ("pending_review", "candidate_ready", "completed"):
        raise HTTPException(400, f"No se puede recorregir en status {doc.status}")

    result = await db.execute(
        select(Patch).join(Block).join(Page)
        .where(Page.doc_id == doc_id, Patch.id == patch_id)
    )
    patch = result.scalar_one_or_none()
    if not patch:
        raise HTTPException(404, "Corrección no encontrada en este documento")

    # Anti-abuso: límite por patch
    MAX_RECORRECTIONS_PER_PATCH = 3
    current_count = patch.recorrection_count if hasattr(patch, 'recorrection_count') else 0
    if current_count >= MAX_RECORRECTIONS_PER_PATCH:
        raise HTTPException(
            429,
            f"Límite de recorrecciones alcanzado ({MAX_RECORRECTIONS_PER_PATCH} por corrección)"
        )

    # Anti-abuso: límite por documento por hora
    from datetime import datetime, timezone, timedelta
    one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
    doc_recorrections = await db.execute(
        select(func.sum(Patch.recorrection_count))
        .join(Block).join(Page)
        .where(Page.doc_id == doc_id)
    )
    total_doc_recorrections = doc_recorrections.scalar() or 0
    MAX_RECORRECTIONS_PER_DOC_HOUR = 20
    if total_doc_recorrections >= MAX_RECORRECTIONS_PER_DOC_HOUR:
        raise HTTPException(
            429,
            f"Límite de recorrecciones por documento alcanzado ({MAX_RECORRECTIONS_PER_DOC_HOUR}/hora)"
        )

    # Lanzar recorrección como tarea Celery
    from app.workers.tasks_pipeline import recorrect_single_patch
    task = recorrect_single_patch.delay(
        str(doc.id), str(patch_id), body.feedback
    )

    logger.info(f"Recorrección solicitada: patch={patch_id}, doc={doc_id}, task={task.id}")
    return {
        "message": "Recorrección iniciada",
        "task_id": task.id,
        "patch_id": str(patch_id),
        "recorrection_count": current_count + 1,
    }


# =============================================
# PREVIEW de página
# =============================================

@router.get("/documents/{doc_id}/pages/{page_no}/preview")
async def get_page_preview(
    doc_id: UUID,
    page_no: int,
    db: AsyncSession = Depends(get_db),
):
    """Obtiene la imagen preview de una página (streaming directo)."""
    result = await db.execute(
        select(Page).where(Page.doc_id == doc_id, Page.page_no == page_no)
    )
    page = result.scalar_one_or_none()
    if not page or not page.preview_uri:
        raise HTTPException(404, "Preview no disponible")

    file_data = minio_client.download_file(page.preview_uri)
    return StreamingResponse(
        io.BytesIO(file_data),
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=3600"},
    )


@router.get("/documents/{doc_id}/pages/{page_no}/preview-corrected")
async def get_corrected_page_preview(
    doc_id: UUID,
    page_no: int,
    mode: str = "final",
    db: AsyncSession = Depends(get_db),
):
    """Preview PNG de una página corregida. mode=candidate para vista candidata."""
    doc = await _get_doc_or_404(db, doc_id)

    if mode == "candidate":
        preview_key = f"pages/{doc_id}/preview_candidate/{page_no}.png"
    else:
        preview_key = f"pages/{doc_id}/preview_corrected/{page_no}.png"

    if not minio_client.file_exists(preview_key):
        raise HTTPException(404, "Preview corregido no disponible")

    file_data = minio_client.download_file(preview_key)
    return StreamingResponse(
        io.BytesIO(file_data),
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=3600"},
    )


@router.get("/documents/{doc_id}/pages/{page_no}/annotations")
async def get_page_annotations(
    doc_id: UUID,
    page_no: int,
    mode: str = "final",
    db: AsyncSession = Depends(get_db),
):
    """Metadata de anotaciones para overlay hover. mode=candidate para vista candidata."""
    await _get_doc_or_404(db, doc_id)

    if mode == "candidate":
        annot_key = f"pages/{doc_id}/annotations_candidate/{page_no}.json"
    else:
        annot_key = f"pages/{doc_id}/annotations/{page_no}.json"

    if not minio_client.file_exists(annot_key):
        return {"annotations": []}

    file_data = minio_client.download_file(annot_key)
    import json
    return json.loads(file_data.decode("utf-8"))


# =============================================
# DESCARGA
# =============================================

@router.get("/documents/{doc_id}/download/pdf")
async def download_corrected_pdf(
    doc_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Descarga el PDF corregido (streaming directo)."""
    doc = await _get_doc_or_404(db, doc_id)

    if doc.status != "completed":
        raise HTTPException(400, f"Documento aún no completado. Estado: {doc.status}")

    stem = Path(doc.filename).stem
    pdf_key = f"final/{doc_id}/{stem}_corrected.pdf"

    if not minio_client.file_exists(pdf_key):
        if doc.pdf_uri and minio_client.file_exists(doc.pdf_uri):
            pdf_key = doc.pdf_uri
        else:
            raise HTTPException(404, "PDF no encontrado")

    file_data = minio_client.download_file(pdf_key)
    filename = f"{stem}_corrected.pdf"
    return StreamingResponse(
        io.BytesIO(file_data),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/documents/{doc_id}/download/docx")
async def download_corrected_docx(
    doc_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Descarga el DOCX corregido (streaming directo)."""
    doc = await _get_doc_or_404(db, doc_id)

    if doc.status != "completed":
        raise HTTPException(400, f"Documento aún no completado. Estado: {doc.status}")

    stem = Path(doc.filename).stem
    docx_key = f"docx/{doc_id}/{stem}_corrected.docx"

    if not minio_client.file_exists(docx_key):
        raise HTTPException(404, "DOCX corregido no encontrado")

    file_data = minio_client.download_file(docx_key)
    filename = f"{stem}_corrected.docx"
    return StreamingResponse(
        io.BytesIO(file_data),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# =============================================
# ELIMINAR
# =============================================

@router.delete("/documents/{doc_id}")
async def delete_document(
    doc_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Elimina un documento y todos sus artefactos."""
    doc = await _get_doc_or_404(db, doc_id)
    await db.delete(doc)
    await db.commit()

    # TODO: limpiar archivos de MinIO en background
    logger.info(f"Documento {doc_id} eliminado")
    return {"message": "Documento eliminado"}


# =============================================
# COSTOS (LlmUsage)
# =============================================

@router.get("/costs/summary")
async def get_cost_summary(db: AsyncSession = Depends(get_db)):
    """Resumen global de costos de todos los documentos."""
    result = await db.execute(
        select(
            func.count(LlmUsage.id),
            func.coalesce(func.sum(LlmUsage.prompt_tokens), 0),
            func.coalesce(func.sum(LlmUsage.completion_tokens), 0),
            func.coalesce(func.sum(LlmUsage.total_tokens), 0),
            func.coalesce(func.sum(LlmUsage.cost_usd), 0.0),
            func.count(func.distinct(LlmUsage.doc_id)),
        )
    )
    total_calls, prompt_t, completion_t, total_t, total_cost, total_docs = result.one()

    # Breakdown por modelo
    model_result = await db.execute(
        select(
            LlmUsage.model_used,
            func.count(LlmUsage.id),
            func.coalesce(func.sum(LlmUsage.total_tokens), 0),
            func.coalesce(func.sum(LlmUsage.cost_usd), 0.0),
        ).group_by(LlmUsage.model_used)
    )
    model_breakdown = [
        {"model": m, "calls": c, "tokens": int(t), "cost": float(co)}
        for m, c, t, co in model_result.all()
    ]

    return {
        "total_cost_usd": float(total_cost),
        "total_prompt_tokens": int(prompt_t),
        "total_completion_tokens": int(completion_t),
        "total_tokens": int(total_t),
        "total_documents": int(total_docs),
        "total_calls": int(total_calls),
        "avg_cost_per_document": float(total_cost) / max(int(total_docs), 1),
        "avg_cost_per_call": float(total_cost) / max(int(total_calls), 1),
        "model_breakdown": model_breakdown,
        "pricing": {
            "model": settings.openai_model,
            "input_per_1m": settings.openai_pricing_input,
            "output_per_1m": settings.openai_pricing_output,
        },
    }


@router.get("/costs/documents")
async def get_cost_documents(
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    """Costo desglosado por documento."""
    usage_sub = (
        select(
            LlmUsage.doc_id,
            func.count(LlmUsage.id).label("total_calls"),
            func.sum(LlmUsage.prompt_tokens).label("prompt_tokens"),
            func.sum(LlmUsage.completion_tokens).label("completion_tokens"),
            func.sum(LlmUsage.total_tokens).label("total_tokens"),
            func.sum(LlmUsage.cost_usd).label("total_cost_usd"),
        )
        .group_by(LlmUsage.doc_id)
        .subquery()
    )

    result = await db.execute(
        select(
            Document.id,
            Document.filename,
            Document.status,
            Document.total_pages,
            Document.created_at,
            usage_sub.c.total_calls,
            usage_sub.c.prompt_tokens,
            usage_sub.c.completion_tokens,
            usage_sub.c.total_tokens,
            usage_sub.c.total_cost_usd,
        )
        .join(usage_sub, Document.id == usage_sub.c.doc_id)
        .order_by(Document.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    rows = result.all()

    return [
        {
            "doc_id": str(r.id),
            "filename": r.filename,
            "status": r.status,
            "total_pages": r.total_pages,
            "total_calls": r.total_calls,
            "prompt_tokens": int(r.prompt_tokens),
            "completion_tokens": int(r.completion_tokens),
            "total_tokens": int(r.total_tokens),
            "total_cost_usd": float(r.total_cost_usd),
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]


@router.get("/documents/{doc_id}/costs")
async def get_document_costs(
    doc_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Desglose de costos por párrafo de un documento."""
    await _get_doc_or_404(db, doc_id)

    result = await db.execute(
        select(LlmUsage)
        .where(LlmUsage.doc_id == doc_id)
        .order_by(LlmUsage.paragraph_index)
    )
    records = result.scalars().all()
    return [ParagraphCostItem.model_validate(r) for r in records]


# =============================================
# PLAN V4: AUDITORÍA LLM
# =============================================

@router.get("/documents/{doc_id}/llm-audit")
async def get_llm_audit(
    doc_id: UUID,
    pass_number: int | None = None,
    call_purpose: str | None = None,
    has_error: bool | None = None,
    skip: int = 0,
    limit: int = 200,
    db: AsyncSession = Depends(get_db),
):
    """Lista de llamadas LLM del documento con filtros opcionales."""
    await _get_doc_or_404(db, doc_id)
    query = select(LlmAuditLog).where(LlmAuditLog.doc_id == doc_id)
    if pass_number is not None:
        query = query.where(LlmAuditLog.pass_number == pass_number)
    if call_purpose:
        query = query.where(LlmAuditLog.call_purpose == call_purpose)
    if has_error is True:
        query = query.where(LlmAuditLog.error_text.isnot(None))
    elif has_error is False:
        query = query.where(LlmAuditLog.error_text.is_(None))
    query = query.order_by(LlmAuditLog.paragraph_index, LlmAuditLog.pass_number).offset(skip).limit(limit)
    result = await db.execute(query)
    rows = result.scalars().all()

    # Stats globales
    stats_result = await db.execute(
        select(LlmAuditLog).where(LlmAuditLog.doc_id == doc_id)
    )
    all_rows = stats_result.scalars().all()
    p2_rows = [r for r in all_rows if r.pass_number == 2]
    reversions = 0
    for r in p2_rows:
        resp = r.response_payload or {}
        choices = resp.get("choices", [])
        if choices:
            content = choices[0].get("message", {}).get("content", "")
            if isinstance(content, str) and "reverted_destructions" in content:
                try:
                    import json as _j
                    parsed = _j.loads(content)
                    reversions += len(parsed.get("reverted_destructions", []))
                except Exception:
                    pass

    return {
        "doc_id": str(doc_id),
        "stats": {
            "total_calls": len(all_rows),
            "pass1_calls": sum(1 for r in all_rows if r.pass_number == 1),
            "pass2_calls": len(p2_rows),
            "paragraphs_with_audit": len(set(r.paragraph_index for r in all_rows if r.paragraph_index is not None)),
            "total_reversions_detected": reversions,
            "errors": sum(1 for r in all_rows if r.error_text),
        },
        "entries": [
            {
                "id": str(r.id),
                "paragraph_index": r.paragraph_index,
                "location": r.location,
                "pass_number": r.pass_number,
                "call_purpose": r.call_purpose,
                "model_used": r.model_used,
                "prompt_tokens": r.prompt_tokens,
                "completion_tokens": r.completion_tokens,
                "total_tokens": r.total_tokens,
                "latency_ms": r.latency_ms,
                "has_error": bool(r.error_text),
                "error_text": r.error_text,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ],
    }


@router.get("/documents/{doc_id}/llm-audit/{paragraph_index}")
async def get_llm_audit_paragraph(
    doc_id: UUID,
    paragraph_index: int,
    db: AsyncSession = Depends(get_db),
):
    """Detalle de todas las llamadas LLM para un párrafo (request + response RAW)."""
    await _get_doc_or_404(db, doc_id)
    result = await db.execute(
        select(LlmAuditLog)
        .where(LlmAuditLog.doc_id == doc_id, LlmAuditLog.paragraph_index == paragraph_index)
        .order_by(LlmAuditLog.pass_number)
    )
    rows = result.scalars().all()
    if not rows:
        raise HTTPException(404, f"Sin datos de auditoría para párrafo {paragraph_index}")

    return {
        "doc_id": str(doc_id),
        "paragraph_index": paragraph_index,
        "calls": [
            {
                "id": str(r.id),
                "pass_number": r.pass_number,
                "call_purpose": r.call_purpose,
                "model_used": r.model_used,
                "prompt_tokens": r.prompt_tokens,
                "completion_tokens": r.completion_tokens,
                "total_tokens": r.total_tokens,
                "latency_ms": r.latency_ms,
                "request_payload": r.request_payload,
                "response_payload": r.response_payload,
                "error_text": r.error_text,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ],
    }


@router.get("/documents/{doc_id}/llm-audit/diff/{paragraph_index}")
async def get_llm_audit_diff(
    doc_id: UUID,
    paragraph_index: int,
    db: AsyncSession = Depends(get_db),
):
    """Comparativa estructurada: original / Pasada 1 / Pasada 2 con prompts de ambas pasadas."""
    await _get_doc_or_404(db, doc_id)

    # Obtener patch del párrafo
    patch_result = await db.execute(
        select(Patch)
        .join(Block)
        .join(Page)
        .where(Page.doc_id == doc_id, Patch.paragraph_index == paragraph_index)
        .order_by(Patch.created_at.desc())
        .limit(1)
    )
    patch = patch_result.scalar_one_or_none()

    # Obtener audit logs del párrafo
    audit_result = await db.execute(
        select(LlmAuditLog)
        .where(LlmAuditLog.doc_id == doc_id, LlmAuditLog.paragraph_index == paragraph_index)
        .order_by(LlmAuditLog.pass_number)
    )
    audit_rows = audit_result.scalars().all()

    pass1_log = next((r for r in audit_rows if r.pass_number == 1), None)
    pass2_log = next((r for r in audit_rows if r.pass_number == 2), None)

    return {
        "doc_id": str(doc_id),
        "paragraph_index": paragraph_index,
        "original_text": patch.original_text if patch else None,
        "corrected_pass1_text": patch.corrected_pass1_text if patch else None,
        "corrected_final_text": patch.corrected_text if patch else None,
        "has_pass2": pass2_log is not None,
        "pass2_audit": patch.pass2_audit_json if patch else None,
        "pass1": {
            "request_payload": pass1_log.request_payload if pass1_log else None,
            "response_payload": pass1_log.response_payload if pass1_log else None,
            "tokens": pass1_log.total_tokens if pass1_log else None,
            "latency_ms": pass1_log.latency_ms if pass1_log else None,
            "model_used": pass1_log.model_used if pass1_log else None,
        } if pass1_log else None,
        "pass2": {
            "request_payload": pass2_log.request_payload if pass2_log else None,
            "response_payload": pass2_log.response_payload if pass2_log else None,
            "tokens": pass2_log.total_tokens if pass2_log else None,
            "latency_ms": pass2_log.latency_ms if pass2_log else None,
            "model_used": pass2_log.model_used if pass2_log else None,
        } if pass2_log else None,
    }


@router.get("/documents/{doc_id}/global-context")
async def get_document_global_context(
    doc_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Retorna el contexto global (ADN editorial) generado por C.6."""
    await _get_doc_or_404(db, doc_id)
    result = await db.execute(
        select(DocumentGlobalContext).where(DocumentGlobalContext.doc_id == doc_id)
    )
    gc = result.scalar_one_or_none()
    if not gc:
        raise HTTPException(404, "Contexto global no disponible para este documento")
    return {
        "doc_id": str(doc_id),
        "global_summary": gc.global_summary,
        "dominant_voice": gc.dominant_voice,
        "dominant_register": gc.dominant_register,
        "key_themes": gc.key_themes_json or [],
        "protected_globals": gc.protected_globals_json or [],
        "style_fingerprint": gc.style_fingerprint_json or {},
        "total_paragraphs": gc.total_paragraphs,
        "created_at": gc.created_at.isoformat() if gc.created_at else None,
    }


# =============================================
# HELPERS
# =============================================

async def _get_doc_or_404(db: AsyncSession, doc_id: UUID) -> Document:
    result = await db.execute(select(Document).where(Document.id == doc_id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(404, "Documento no encontrado")
    return doc


# Pesos de cada etapa en el progreso global (suman 1.0)
_STAGE_WEIGHTS: dict[str, tuple[float, float]] = {
    "converting":           (0.00, 0.05),
    "extracting":           (0.05, 0.20),
    "analyzing":            (0.20, 0.35),
    "correcting":           (0.35, 0.75),
    "candidate_rendering":  (0.75, 0.85),
    "candidate_ready":      (0.85, 0.85),  # Pausa — revisión visual compare-first
    "pending_review":       (0.85, 0.85),  # Legacy — backward compat
    "finalizing":           (0.85, 0.99),
    "rendering":            (0.85, 0.99),  # Legacy — backward compat
}

_STAGE_LABELS: dict[str, str] = {
    "converting":           "Conversión",
    "extracting":           "Extracción",
    "analyzing":            "Análisis",
    "correcting":           "Corrección",
    "candidate_rendering":  "Renderizando candidato",
    "candidate_ready":      "Listo para revisión",
    "pending_review":       "Revisión pendiente",
    "finalizing":           "Finalizando",
    "rendering":            "Renderizado",
}

_HEARTBEAT_STALL_SECONDS = 120  # 2 minutos sin heartbeat → stalled


def _calculate_progress(doc: Document) -> float:
    """Calcula el progreso real del documento (0.0 a 1.0) usando campos granulares."""
    if doc.status == "completed":
        return 1.0
    if doc.status in ("pending_review", "candidate_ready"):
        return 0.85  # Waiting for human review
    if doc.status in ("uploaded", "failed"):
        return 0.0

    weights = _STAGE_WEIGHTS.get(doc.status)
    if not weights:
        return 0.0

    base, end = weights
    stage_fraction = 0.0
    if (
        doc.progress_stage_total
        and doc.progress_stage_total > 0
        and doc.progress_stage_current is not None
    ):
        stage_fraction = min(doc.progress_stage_current / doc.progress_stage_total, 1.0)

    return base + (end - base) * stage_fraction


def _build_progress_detail(doc: Document) -> ProgressDetail | None:
    """Construye el detalle de progreso con ETA y detección de stall."""
    from datetime import datetime, timezone

    if doc.status in ("uploaded", "completed", "pending_review", "candidate_ready"):
        return None

    is_stalled = False
    if doc.heartbeat_at:
        elapsed = (datetime.now(timezone.utc) - doc.heartbeat_at).total_seconds()
        if elapsed > _HEARTBEAT_STALL_SECONDS:
            is_stalled = True

    # Calcular ETA basado en velocidad de procesamiento de la etapa
    eta_seconds = None
    if (
        doc.stage_started_at
        and doc.progress_stage_current
        and doc.progress_stage_total
        and doc.progress_stage_current > 0
        and not is_stalled
    ):
        elapsed = (datetime.now(timezone.utc) - doc.stage_started_at).total_seconds()
        remaining_items = doc.progress_stage_total - doc.progress_stage_current
        rate = doc.progress_stage_current / elapsed if elapsed > 0 else 0
        if rate > 0:
            eta_seconds = round(remaining_items / rate, 1)

    return ProgressDetail(
        stage=doc.progress_stage or doc.status,
        stage_label=_STAGE_LABELS.get(doc.progress_stage or doc.status),
        stage_current=doc.progress_stage_current,
        stage_total=doc.progress_stage_total,
        message=doc.progress_message,
        eta_seconds=eta_seconds,
        is_stalled=is_stalled,
        heartbeat_at=doc.heartbeat_at,
        stage_started_at=doc.stage_started_at,
    )


async def _get_pages_summary(db: AsyncSession, doc_id: UUID) -> dict:
    """Resumen de estados de páginas."""
    result = await db.execute(
        select(Page.status, func.count(Page.id))
        .where(Page.doc_id == doc_id)
        .group_by(Page.status)
    )
    return {status: count for status, count in result.all()}


# =============================================
# ANÁLISIS EDITORIAL (MVP2 Lote 3)
# =============================================

@router.get("/documents/{doc_id}/analysis", response_model=AnalysisResult)
async def get_document_analysis(doc_id: UUID, db: AsyncSession = Depends(get_db)):
    """Retorna el resultado del análisis editorial (Etapa C) de un documento."""
    await _get_doc_or_404(db, doc_id)  # Validates document exists

    # Obtener secciones
    sections_result = await db.execute(
        select(SectionSummary)
        .where(SectionSummary.doc_id == doc_id)
        .order_by(SectionSummary.section_index)
    )
    sections = sections_result.scalars().all()

    # Obtener términos
    terms_result = await db.execute(
        select(TermRegistry)
        .where(TermRegistry.doc_id == doc_id)
        .order_by(TermRegistry.frequency.desc())
    )
    terms = terms_result.scalars().all()

    # Obtener perfil inferido (del DocumentProfile si existe)
    profile_result = await db.execute(
        select(DocumentProfile).where(DocumentProfile.doc_id == doc_id)
    )
    profile_row = profile_result.scalar_one_or_none()

    inferred = None
    if profile_row:
        inferred = InferredProfile(
            genre=profile_row.genre,
            audience_type=profile_row.audience_type,
            register=profile_row.register,
            tone=profile_row.tone,
            key_terms=[t.term for t in terms if t.is_protected],
        )

    # Stats
    has_analysis = len(sections) > 0 or len(terms) > 0
    stats = {
        "sections_detected": len(sections),
        "terms_extracted": len(terms),
        "terms_protected": sum(1 for t in terms if t.is_protected),
        "has_analysis": has_analysis,
    }

    # Recuperar paragraph_classifications de MinIO (persistidas en Etapa C)
    paragraph_classifications = []
    cls_key = f"analysis/{doc_id}/classifications.json"
    try:
        if minio_client.file_exists(cls_key):
            import json
            cls_data = minio_client.download_file(cls_key)
            paragraph_classifications = json.loads(cls_data.decode("utf-8"))
    except Exception as e:
        logger.warning(f"No se pudieron leer clasificaciones de MinIO: {e}")

    return AnalysisResult(
        doc_id=doc_id,
        status="completed" if has_analysis else "pending",
        inferred_profile=inferred,
        sections=[SectionSummaryItem.model_validate(s) for s in sections],
        terms=[TermRegistryItem.model_validate(t) for t in terms],
        paragraph_classifications=paragraph_classifications,
        stats=stats,
    )


@router.get("/documents/{doc_id}/correction-flow")
async def get_correction_flow(doc_id: str, db: AsyncSession = Depends(get_db)):
    """
    Flujo de corrección de un documento.
    - Para doc_id="demo": devuelve datos simulados de ejemplo.
    - Para un UUID real: lee los parches reales de la BD.
    """
    if doc_id == "demo":
        service, sample_doc_id, requests = generate_sample_document_flow()
        summary = service.get_context_summary(sample_doc_id)
        return {
            "document_id": doc_id,
            "flow_type": "simulation",
            "summary": summary,
            "requests": [
                {
                    "step": i + 1,
                    "type": req.request_type,
                    "block_no": req.block_current.block_no,
                    "original_text": req.block_current.original_text,
                    "context_blocks_count": len(req.context_blocks),
                    "context_preview": [
                        {
                            "block_no": cb.block_no,
                            "corrected_text": cb.corrected_text[:100] + "..." if len(cb.corrected_text) > 100 else cb.corrected_text
                        }
                        for cb in req.context_blocks
                    ],
                    "prompt": req.prompt,
                    "timestamp": req.timestamp.isoformat(),
                }
                for i, req in enumerate(requests)
            ]
        }

    # Documento real — leer parches de la BD
    try:
        doc_uuid = UUID(doc_id)
    except ValueError:
        raise HTTPException(400, "ID de documento inválido")

    doc_result = await db.execute(select(Document).where(Document.id == doc_uuid))
    doc = doc_result.scalar_one_or_none()
    if not doc:
        raise HTTPException(404, "Documento no encontrado")

    # Obtener todos los parches del documento ordenados por creación
    patches_result = await db.execute(
        select(Patch)
        .join(Block, Patch.block_id == Block.id)
        .join(Page, Block.page_id == Page.id)
        .where(Page.doc_id == doc_uuid)
        .order_by(Patch.created_at)
    )
    patches = patches_result.scalars().all()

    if not patches:
        return {
            "document_id": doc_id,
            "flow_type": "real",
            "summary": {
                "total_blocks": 0,
                "total_requests": 0,
                "languagetool_requests": 0,
                "chatgpt_requests": 0,
                "total_cost_usd": 0.0,
            },
            "requests": [],
        }

    lt_count = sum(1 for p in patches if p.source == "languagetool")
    gpt_count = sum(1 for p in patches if "chatgpt" in p.source)

    # Obtener costos por paragraph_index
    cost_result = await db.execute(
        select(LlmUsage)
        .where(LlmUsage.doc_id == doc_uuid)
        .order_by(LlmUsage.paragraph_index)
    )
    cost_records = cost_result.scalars().all()
    cost_by_para: dict[int, LlmUsage] = {r.paragraph_index: r for r in cost_records}

    # Reconstruir el flujo con contexto acumulado
    corrected_context: list[str] = []
    requests_list = []

    for i, patch in enumerate(patches):
        para_cost = cost_by_para.get(patch.paragraph_index) if patch.paragraph_index is not None else None

        # Paso LanguageTool
        if patch.operations_json:
            requests_list.append({
                "step": len(requests_list) + 1,
                "type": "languagetool",
                "block_no": i,
                "original_text": patch.original_text,
                "context_blocks_count": 0,
                "prompt": f"LanguageTool: {len(patch.operations_json)} correcciones aplicadas",
                "timestamp": patch.created_at.isoformat(),
            })

        # Paso ChatGPT (si el source lo indica)
        if "chatgpt" in patch.source:
            ctx_preview = [
                {"block_no": j, "corrected_text": t[:100] + "..." if len(t) > 100 else t}
                for j, t in enumerate(corrected_context[-3:])
            ]
            step_data = {
                "step": len(requests_list) + 1,
                "type": "chatgpt_style",
                "block_no": i,
                "original_text": patch.original_text,
                "corrected_text": patch.corrected_text,
                "context_blocks_count": len(corrected_context),
                "context_preview": ctx_preview,
                "prompt": f"Mejora de estilo con contexto de {len(corrected_context)} párrafos previos",
                "timestamp": patch.created_at.isoformat(),
            }
            if para_cost:
                step_data["prompt_tokens"] = para_cost.prompt_tokens
                step_data["completion_tokens"] = para_cost.completion_tokens
                step_data["total_tokens"] = para_cost.total_tokens
                step_data["cost_usd"] = para_cost.cost_usd
            requests_list.append(step_data)

        corrected_context.append(patch.corrected_text)

    total_cost = sum(r.cost_usd for r in cost_records)

    return {
        "document_id": doc_id,
        "flow_type": "real",
        "summary": {
            "total_blocks": len(patches),
            "total_requests": len(requests_list),
            "languagetool_requests": lt_count,
            "chatgpt_requests": gpt_count,
            "total_cost_usd": round(total_cost, 6),
        },
        "requests": requests_list,
    }


@router.get("/documents/{doc_id}/correction-batches", response_model=list[CorrectionBatchStatus])
async def get_correction_batches(doc_id: UUID, db: AsyncSession = Depends(get_db)):
    """
    Estado de cada lote de corrección paralela.
    Usado por el frontend durante status='correcting' cuando parallel_correction_enabled=True.
    Retorna lista vacía si el documento no usa corrección paralela.
    """
    await _get_doc_or_404(db, doc_id)
    result = await db.execute(
        select(CorrectionBatch)
        .where(CorrectionBatch.doc_id == doc_id)
        .order_by(CorrectionBatch.batch_index)
    )
    batches = result.scalars().all()
    return [CorrectionBatchStatus.model_validate(b) for b in batches]


# =============================================
# SPRINT 6: STRUCTURAL MAP + HEALTH CHECKS
# =============================================

@router.get("/documents/{doc_id}/structural-map")
async def get_structural_map(doc_id: UUID, db: AsyncSession = Depends(get_db)):
    """
    Mapa canónico paragraph_index → página/posición para un documento.
    Retorna todos los registros de paragraph_locations ordenados por índice.
    """
    from app.models.paragraph_location import ParagraphLocation
    await _get_doc_or_404(db, doc_id)
    result = await db.execute(
        select(ParagraphLocation)
        .where(ParagraphLocation.doc_id == doc_id)
        .order_by(ParagraphLocation.paragraph_index)
    )
    locations = result.scalars().all()
    return [
        {
            "paragraph_index": loc.paragraph_index,
            "location": loc.location,
            "page_start": loc.page_start,
            "page_end": loc.page_end,
            "position_in_page": loc.position_in_page,
            "has_internal_page_break": loc.has_internal_page_break,
            "is_continuation_from_prev_page": loc.is_continuation_from_prev_page,
            "paragraph_type": loc.paragraph_type,
        }
        for loc in locations
    ]


@router.get("/documents/{doc_id}/cross-page-paragraphs")
async def get_cross_page_paragraphs(doc_id: UUID, db: AsyncSession = Depends(get_db)):
    """Lista párrafos que cruzan páginas (tienen salto de página interno)."""
    from app.models.paragraph_location import ParagraphLocation
    await _get_doc_or_404(db, doc_id)
    result = await db.execute(
        select(ParagraphLocation)
        .where(
            ParagraphLocation.doc_id == doc_id,
            ParagraphLocation.has_internal_page_break == True,  # noqa: E712
        )
        .order_by(ParagraphLocation.paragraph_index)
    )
    locations = result.scalars().all()
    return [
        {
            "paragraph_index": loc.paragraph_index,
            "location": loc.location,
            "page_start": loc.page_start,
            "page_end": loc.page_end,
            "paragraph_type": loc.paragraph_type,
        }
        for loc in locations
    ]


@router.get("/health/llm")
async def health_llm():
    """
    Test de conectividad con el proveedor LLM (OpenAI).
    Retorna modelo configurado, estado y latencia aproximada.
    """
    import time
    import httpx
    model = settings.openai_model
    t0 = time.time()
    status = "ok"
    error = None
    latency_ms = None

    if not settings.openai_api_key or settings.openai_api_key == "dummy":
        status = "simulation_mode"
        latency_ms = 0
    else:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    "https://api.openai.com/v1/models",
                    headers={"Authorization": f"Bearer {settings.openai_api_key}"},
                )
                latency_ms = round((time.time() - t0) * 1000)
                if resp.status_code == 200:
                    status = "ok"
                else:
                    status = "error"
                    error = f"HTTP {resp.status_code}"
        except Exception as e:
            status = "unreachable"
            error = str(e)
            latency_ms = round((time.time() - t0) * 1000)

    return {
        "status": status,
        "model": model,
        "cheap_model": settings.openai_cheap_model,
        "editorial_model": settings.openai_editorial_model,
        "latency_ms": latency_ms,
        "error": error,
    }


@router.get("/health/languagetool")
async def health_languagetool():
    """
    Test de conectividad con LanguageTool.
    Retorna estado y latencia aproximada.
    """
    import time
    import httpx
    t0 = time.time()
    status = "ok"
    error = None
    latency_ms = None
    version = None

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{settings.languagetool_url}/v2/languages")
            latency_ms = round((time.time() - t0) * 1000)
            if resp.status_code == 200:
                status = "ok"
                data = resp.json()
                version = f"{len(data)} idiomas disponibles" if isinstance(data, list) else "ok"
            else:
                status = "error"
                error = f"HTTP {resp.status_code}"
    except Exception as e:
        status = "unreachable"
        error = str(e)
        latency_ms = round((time.time() - t0) * 1000)

    return {
        "status": status,
        "url": settings.languagetool_url,
        "latency_ms": latency_ms,
        "version": version,
        "error": error,
    }
