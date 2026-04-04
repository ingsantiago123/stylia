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
from app.schemas.patch import PatchDetail, PatchListItem
from app.schemas.analysis import AnalysisResult, SectionSummaryItem, TermRegistryItem, InferredProfile
from app.models.section_summary import SectionSummary
from app.models.term_registry import TermRegistry
from app.models.correction_batch import CorrectionBatch
from app.schemas.style_profile import (
    StyleProfileCreate, StyleProfileUpdate, StyleProfileResponse, PresetListItem
)
from app.services.ingestion import ingest_document
from app.services.context_accumulator import ContextualCorrectionService, generate_sample_document_flow
from app.workers.tasks_pipeline import process_document_pipeline
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
    db: AsyncSession = Depends(get_db),
):
    """Lista todas las correcciones de un documento."""
    result = await db.execute(
        select(Patch, Block.block_no)
        .join(Block)
        .join(Page)
        .where(Page.doc_id == doc_id)
        .order_by(Page.page_no, Block.block_no)
    )
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
        ))

    return items


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
    db: AsyncSession = Depends(get_db),
):
    """Preview PNG de una página corregida."""
    doc = await _get_doc_or_404(db, doc_id)

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
    db: AsyncSession = Depends(get_db),
):
    """Metadata de anotaciones para overlay hover en el frontend."""
    await _get_doc_or_404(db, doc_id)

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
    "converting":  (0.00, 0.05),
    "extracting":  (0.05, 0.20),
    "analyzing":   (0.20, 0.35),
    "correcting":  (0.35, 0.85),
    "rendering":   (0.85, 0.99),
}

_STAGE_LABELS: dict[str, str] = {
    "converting":  "Conversión",
    "extracting":  "Extracción",
    "analyzing":   "Análisis",
    "correcting":  "Corrección",
    "rendering":   "Renderizado",
}

_HEARTBEAT_STALL_SECONDS = 120  # 2 minutos sin heartbeat → stalled


def _calculate_progress(doc: Document) -> float:
    """Calcula el progreso real del documento (0.0 a 1.0) usando campos granulares."""
    if doc.status == "completed":
        return 1.0
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

    if doc.status in ("uploaded", "completed"):
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
