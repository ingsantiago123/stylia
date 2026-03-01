"""
Endpoints de documentos — MVP 1.
Upload, listado, detalle, descarga de resultados.
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
from app.schemas.document import DocumentUploadResponse, DocumentDetail, DocumentListItem
from app.schemas.page import PageListItem
from app.schemas.patch import PatchDetail, PatchListItem
from app.services.ingestion import ingest_document
from app.services.context_accumulator import ContextualCorrectionService, generate_sample_document_flow
from app.workers.tasks_pipeline import process_document_pipeline
from app.utils import minio_client

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

    # Inicializar contexto de corrección
    document_info = {
        "filename": document.filename,
        "format": document.original_format,
        "status": document.status
    }
    context_service.init_document_context(str(document.id), document_info)

    # Lanzar pipeline de procesamiento en Celery
    task = process_document_pipeline.delay(str(document.id))

    logger.info(f"Pipeline lanzado: doc={document.id}, task={task.id}")

    return DocumentUploadResponse(
        id=document.id,
        filename=document.filename,
        original_format=document.original_format,
        status=document.status,
        message="Documento recibido. Procesamiento iniciado.",
    )


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
        # Calcular progreso
        progress = await _calculate_progress(db, doc)
        items.append(DocumentListItem(
            id=doc.id,
            filename=doc.filename,
            original_format=doc.original_format,
            status=doc.status,
            total_pages=doc.total_pages,
            created_at=doc.created_at,
            progress=progress,
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

    progress = await _calculate_progress(db, doc)
    pages_summary = await _get_pages_summary(db, doc_id)

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
        pages_summary=pages_summary,
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

    items = []
    for patch, block_no in rows:
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
# HELPERS
# =============================================

async def _get_doc_or_404(db: AsyncSession, doc_id: UUID) -> Document:
    result = await db.execute(select(Document).where(Document.id == doc_id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(404, "Documento no encontrado")
    return doc


async def _calculate_progress(db: AsyncSession, doc: Document) -> float:
    """Calcula el progreso del documento (0.0 a 1.0)."""
    if doc.status == "completed":
        return 1.0
    if doc.status in ("uploaded", "failed"):
        return 0.0
    if not doc.total_pages or doc.total_pages == 0:
        status_progress = {
            "converting": 0.1,
            "extracting": 0.2,
            "correcting": 0.5,
            "rendering": 0.8,
        }
        return status_progress.get(doc.status, 0.0)

    # Calcular basado en páginas completadas
    total = doc.total_pages
    rendered = await db.scalar(
        select(func.count(Page.id))
        .where(Page.doc_id == doc.id, Page.status == "rendered")
    ) or 0
    corrected = await db.scalar(
        select(func.count(Page.id))
        .where(Page.doc_id == doc.id, Page.status == "corrected")
    ) or 0
    extracted = await db.scalar(
        select(func.count(Page.id))
        .where(Page.doc_id == doc.id, Page.status == "extracted")
    ) or 0

    # Peso ponderado
    progress = (extracted * 0.3 + corrected * 0.6 + rendered * 1.0) / total
    return min(progress, 0.99)  # 1.0 solo cuando status=completed


async def _get_pages_summary(db: AsyncSession, doc_id: UUID) -> dict:
    """Resumen de estados de páginas."""
    result = await db.execute(
        select(Page.status, func.count(Page.id))
        .where(Page.doc_id == doc_id)
        .group_by(Page.status)
    )
    return {status: count for status, count in result.all()}


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
        raise HTTPException(404, "Este documento aún no tiene correcciones registradas")

    lt_count = sum(1 for p in patches if p.source == "languagetool")
    gpt_count = sum(1 for p in patches if "chatgpt" in p.source)

    # Reconstruir el flujo con contexto acumulado
    corrected_context: list[str] = []
    requests_list = []

    for i, patch in enumerate(patches):
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
            requests_list.append({
                "step": len(requests_list) + 1,
                "type": "chatgpt_style",
                "block_no": i,
                "original_text": patch.original_text,
                "corrected_text": patch.corrected_text,
                "context_blocks_count": len(corrected_context),
                "context_preview": ctx_preview,
                "prompt": f"Mejora de estilo con contexto de {len(corrected_context)} párrafos previos",
                "timestamp": patch.created_at.isoformat(),
            })

        corrected_context.append(patch.corrected_text)

    return {
        "document_id": doc_id,
        "flow_type": "real",
        "summary": {
            "total_blocks": len(patches),
            "total_requests": len(requests_list),
            "languagetool_requests": lt_count,
            "chatgpt_requests": gpt_count,
        },
        "requests": requests_list,
    }
