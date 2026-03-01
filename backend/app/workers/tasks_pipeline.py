"""
Tareas Celery para el pipeline MVP 1.
Pipeline completo: ingest → extract → correct → render.
Todo en un solo archivo para MVP. Se dividirá en fases posteriores.
"""

import logging
from datetime import datetime, timezone

from sqlalchemy import create_engine, select, update
from sqlalchemy.orm import Session, sessionmaker

from app.workers.celery_app import celery_app
from app.config import settings
from app.models.document import Document
from app.models.page import Page
from app.models.block import Block
from app.models.patch import Patch
from app.models.job import Job

from app.services.ingestion import process_ingestion_sync
from app.services.extraction import extract_page_layout_sync
from app.services.correction import correct_page_blocks_sync, correct_docx_sync
from app.services.rendering import render_docx_first_sync

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
            logger.info("[Etapa D] Ruta 1: corrigiendo párrafos directamente del DOCX...")
            docx_patches = correct_docx_sync(
                doc_id=str(doc_id),
                docx_uri=doc.source_uri,
                config=config,
            )

            # Registrar parches en BD (vinculados al primer bloque de cada página)
            patch_version = 1
            for patch_data in docx_patches:
                # Buscar un bloque asociable (por simplicidad, usar el primero de la primera página)
                first_page = pages[0] if pages else None
                if first_page:
                    db_block = db.execute(
                        select(Block).where(Block.page_id == first_page.id).order_by(Block.block_no)
                    ).scalars().first()
                    if db_block:
                        patch = Patch(
                            block_id=db_block.id,
                            version=patch_version,
                            source=patch_data["source"],
                            original_text=patch_data["original_text"],
                            corrected_text=patch_data["corrected_text"],
                            operations_json=patch_data.get("lt_operations", []),
                            review_status="auto_accepted",
                            applied=False,
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
