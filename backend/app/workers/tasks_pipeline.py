"""
Tareas Celery para el pipeline MVP 1 + corrección paralela por lotes.
Pipeline: ingest → extract → analyze → correct (secuencial o paralelo) → render.
"""

import json
import logging
import re
import socket
import tempfile
import time
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path

from sqlalchemy import create_engine, delete, select, update
from sqlalchemy.orm import Session, sessionmaker

import redis as _redis

from app.workers.celery_app import celery_app
from app.config import settings
from app.models.document import Document
from app.models.page import Page
from app.models.block import Block
from app.models.patch import Patch
from app.models.job import Job
from app.models.style_profile import DocumentProfile
from app.models.llm_usage import LlmUsage
from app.models.correction_batch import CorrectionBatch

from app.utils import minio_client
from app.services.ingestion import process_ingestion_sync
from app.services.extraction import extract_all_pages_sync
from app.services.analysis import analyze_document_sync
from app.services.correction import (
    correct_page_blocks_sync,
    correct_docx_sync,
    correct_batch_with_llm_sync,
    compute_batch_boundaries,
    correct_all_paragraphs_lt_sync,
    check_batch_boundaries,
)
from app.services.rendering import render_docx_first_sync
from app.models.section_summary import SectionSummary
from app.models.term_registry import TermRegistry

logger = logging.getLogger(__name__)

# ── Motor síncrono per-process para Celery (prefork-safe) ──
import os as _os
_engines: dict[int, object] = {}
_session_factories: dict[int, object] = {}


def _get_sync_session() -> Session:
    """
    Crea/reutiliza un engine SQLAlchemy por PID de proceso.
    Celery prefork: cada child process debe tener su propio engine
    para evitar compartir file descriptors TCP del padre.
    """
    pid = _os.getpid()
    if pid not in _engines:
        _engines[pid] = create_engine(
            settings.database_url_sync,
            pool_size=3,
            max_overflow=2,
            pool_timeout=30,
            pool_recycle=1800,
            pool_pre_ping=True,
        )
        _session_factories[pid] = sessionmaker(bind=_engines[pid])
        logger.info(f"DB engine creado para PID {pid} (pool_size=3, max_overflow=2)")
    return _session_factories[pid]()


def _get_cached_docx_bytes(doc_id: str, docx_uri: str) -> bytes:
    """Obtiene DOCX bytes del cache Redis o descarga de MinIO como fallback."""
    try:
        rcache = _redis.Redis.from_url(settings.redis_url)
        cached = rcache.get(f"docx_cache:{doc_id}")
        if cached:
            logger.debug(f"[Cache] DOCX hit para {doc_id}")
            return cached
    except Exception:
        pass
    logger.debug(f"[Cache] DOCX miss para {doc_id}, descargando de MinIO")
    return minio_client.download_file(docx_uri)


def _acquire_pipeline_slot(doc_id: str) -> bool:
    """Intenta adquirir un slot de pipeline. Retorna True si fue exitoso."""
    try:
        r = _redis.Redis.from_url(settings.redis_url)
        current = r.scard("active_pipelines")
        if current >= settings.max_concurrent_pipelines:
            return False
        r.sadd("active_pipelines", doc_id)
        r.expire("active_pipelines", 7200)
        return True
    except Exception as e:
        logger.warning(f"[Semáforo] Error adquiriendo slot: {e}")
        return True  # fail-open: permitir si Redis falla


def _release_pipeline_slot(doc_id: str) -> None:
    """Libera un slot de pipeline."""
    try:
        r = _redis.Redis.from_url(settings.redis_url)
        r.srem("active_pipelines", doc_id)
    except Exception:
        pass


# =====================================================================
# HELPERS DE BD
# =====================================================================

def _update_document_status(db: Session, doc_id: str, status: str, **kwargs) -> None:
    """Helper para actualizar estado del documento."""
    values = {"status": status, "updated_at": datetime.now(timezone.utc)}
    values.update(kwargs)
    db.execute(
        update(Document).where(Document.id == doc_id).values(**values)
    )
    db.commit()


_last_progress_commit: dict[str, float] = {}

def _update_progress(
    db: Session,
    doc_id: str,
    stage: str,
    message: str,
    current: int | None = None,
    total: int | None = None,
    start_stage: bool = False,
    commit_interval: float = 5.0,
) -> None:
    """Actualiza progreso granular y heartbeat. Throttle: max 1 commit cada commit_interval segundos."""
    now_utc = datetime.now(timezone.utc)
    values = {
        "progress_stage": stage,
        "progress_message": message[:200],
        "heartbeat_at": now_utc,
        "updated_at": now_utc,
    }
    if current is not None:
        values["progress_stage_current"] = current
    if total is not None:
        values["progress_stage_total"] = total
    if start_stage:
        values["stage_started_at"] = now_utc
        values["progress_stage_current"] = 0
    db.execute(
        update(Document).where(Document.id == doc_id).values(**values)
    )
    key = f"{doc_id}:{stage}"
    now_ts = time.time()
    if start_stage or (now_ts - _last_progress_commit.get(key, 0)) >= commit_interval:
        db.commit()
        _last_progress_commit[key] = now_ts


def _save_stage_timing(db: Session, doc_id: str, stage_timings: dict) -> None:
    """Persiste los timings acumulados de etapas en el documento (sin commit propio)."""
    db.execute(
        update(Document).where(Document.id == doc_id).values(stage_timings=stage_timings)
    )
    # No commit aquí — se hace al final de la etapa


def _cleanup_progress(db: Session, doc_id: str) -> None:
    """Limpia campos de progreso granular al completar el documento (sin commit propio)."""
    db.execute(
        update(Document).where(Document.id == doc_id).values(
            progress_stage=None,
            progress_stage_current=None,
            progress_stage_total=None,
            progress_message="Procesamiento completado",
            heartbeat_at=datetime.now(timezone.utc),
            stage_started_at=None,
        )
    )
    # No commit aquí — el caller hace commit


def _update_page_status(db: Session, page_id: str, status: str, **kwargs) -> None:
    """Helper para actualizar estado de una página (sin commit propio)."""
    values = {"status": status, "updated_at": datetime.now(timezone.utc)}
    values.update(kwargs)
    db.execute(
        update(Page).where(Page.id == page_id).values(**values)
    )
    # No commit aquí — se hace batch al final del loop de páginas


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


# =====================================================================
# ETAPAS D+E COMPARTIDAS: PERSISTIR PATCHES + RENDERIZADO
# =====================================================================

def _run_stage_e(db: Session, doc_id: str, docx_patches: list[dict]) -> None:
    """
    Persiste patches en BD y ejecuta Etapa E (renderizado DOCX-first).
    Compartida por la ruta secuencial y por el chord assemble_correction_results.
    """
    t0_e = time.time()
    doc = db.execute(select(Document).where(Document.id == doc_id)).scalar_one()
    existing_timings = dict(doc.stage_timings or {})
    pages = db.execute(
        select(Page).where(Page.doc_id == doc_id).order_by(Page.page_no)
    ).scalars().all()

    _update_document_status(db, doc_id, "rendering")
    _update_progress(db, doc_id, "rendering", "Generando documento corregido...", start_stage=True)
    logger.info(f"[Etapa E] Renderizando documento {doc_id}...")

    if not docx_patches or doc.original_format != "docx":
        if not docx_patches:
            logger.info("[Etapa E] Sin correcciones que aplicar — documento limpio")
        elapsed_e = round(time.time() - t0_e, 1)
        existing_timings["E"] = elapsed_e
        _update_document_status(db, doc_id, "completed")
        db.execute(update(Document).where(Document.id == doc_id).values(
            processing_completed_at=datetime.now(timezone.utc),
            stage_timings=existing_timings,
        ))
        db.commit()
        _cleanup_progress(db, doc_id)
        return

    # ── Construir índice de bloques para matching rápido ──
    blocks_by_page: dict[int, list[tuple]] = {}
    all_blocks_flat: list[tuple] = []
    block_prefix_index: dict[str, object] = {}  # prefix → Block (O(1) lookup)

    for pi, page in enumerate(pages):
        page_blocks = db.execute(
            select(Block)
            .where(Block.page_id == page.id, Block.block_type == "text")
            .order_by(Block.block_no)
        ).scalars().all()
        page_entries = []
        for block in page_blocks:
            norm = re.sub(r'\s+', ' ', (block.original_text or "").lower().strip())
            page_entries.append((block, norm))
            all_blocks_flat.append((block, pi))
            # Índice por prefijo de 50 chars (primer bloque con ese prefijo gana)
            prefix = norm[:50]
            if prefix and prefix not in block_prefix_index:
                block_prefix_index[prefix] = block
        blocks_by_page[pi] = page_entries

    num_pages = len(pages)

    def _find_best_block(original_text: str, para_idx: int, total_paras: int):
        if not all_blocks_flat:
            return None
        norm_patch = re.sub(r'\s+', ' ', original_text.lower().strip())

        if not norm_patch:
            if total_paras > 0 and num_pages > 0:
                est_page = min(int(para_idx / total_paras * num_pages), num_pages - 1)
                if blocks_by_page.get(est_page):
                    return blocks_by_page[est_page][0][0]
            return all_blocks_flat[0][0]

        # Fast path: exact prefix match O(1)
        prefix = norm_patch[:50]
        if prefix in block_prefix_index:
            return block_prefix_index[prefix]

        # Slow path: search nearby pages only (no full scan)
        est_page = min(int(para_idx / max(total_paras, 1) * num_pages), num_pages - 1)
        search_window = 3
        best_block = None
        best_score = 0.0
        patch_snippet = norm_patch[:200]

        for offset in range(-search_window, search_window + 1):
            pi = est_page + offset
            for block, norm_block in blocks_by_page.get(pi, []):
                if not norm_block:
                    continue
                score = SequenceMatcher(None, patch_snippet, norm_block[:200]).ratio()
                if score > best_score:
                    best_score = score
                    best_block = block
                if best_score > 0.8:
                    return best_block

        if best_score < 0.3:
            if blocks_by_page.get(est_page):
                return blocks_by_page[est_page][0][0]
            return all_blocks_flat[0][0]
        return best_block

    # ── Crear registros Patch en BD ──
    total_paragraphs = len(docx_patches)
    patch_version = 1

    for patch_data in docx_patches:
        para_idx = patch_data.get("paragraph_index", 0)
        db_block = _find_best_block(
            patch_data.get("original_text", ""), para_idx, total_paragraphs
        )
        if not db_block:
            continue

        llm_changes = patch_data.get("changes", [])
        route = patch_data.get("route_taken")
        p_review_status = patch_data.get("review_status", "auto_accepted")
        p_review_reason = patch_data.get("review_reason")
        p_gate_results = patch_data.get("gate_results")

        if llm_changes:
            for change in llm_changes:
                db.add(Patch(
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
                ))
                patch_version += 1
        else:
            db.add(Patch(
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
            ))
            patch_version += 1

    # Marcar páginas como corregidas
    for page in pages:
        if page.status != "failed":
            _update_page_status(db, page.id, "corrected")

    db.commit()
    logger.info(f"[Etapa E] {patch_version - 1} registros de patches guardados en BD")

    # ── Renderizado DOCX → PDF ──
    _docx_bytes_for_render = _get_cached_docx_bytes(str(doc_id), doc.source_uri)
    render_result = render_docx_first_sync(
        doc_id=str(doc_id),
        docx_uri=doc.source_uri,
        filename=doc.filename,
        all_patches=docx_patches,
        docx_bytes_cached=_docx_bytes_for_render,
    )

    # Marcar patches como aplicados
    db.execute(
        update(Patch)
        .where(Patch.block_id.in_(
            select(Block.id).join(Page).where(Page.doc_id == doc_id)
        ))
        .where(Patch.review_status == "auto_accepted")
        .values(applied=True)
    )

    # Marcar páginas como renderizadas
    for page in pages:
        if page.status != "failed":
            _update_page_status(db, page.id, "rendered")
    db.commit()

    elapsed_e = round(time.time() - t0_e, 1)
    existing_timings["E"] = elapsed_e
    _update_document_status(db, doc_id, "completed")
    db.execute(update(Document).where(Document.id == doc_id).values(
        processing_completed_at=datetime.now(timezone.utc),
        stage_timings=existing_timings,
    ))
    db.commit()
    _cleanup_progress(db, doc_id)

    logger.info(
        f"[Etapa E] Completada: {render_result.get('changes_count', 0)} correcciones aplicadas"
    )


# =====================================================================
# ORQUESTACIÓN PARALELA (ruta paralela de Etapa D)
# =====================================================================

def _dispatch_parallel_correction(
    db: Session,
    doc_id: str,
    doc: Document,
    config: dict,
    profile_dict: dict | None,
    analysis_result: dict,
    job: Job,
) -> bool:
    """
    Orquesta la corrección paralela por lotes (Stage D).
    1. Pass 1: LT en paralelo (todos los párrafos)
    2. Compute batch boundaries alineados a secciones
    3. Serializar datos grandes a MinIO
    4. Dispatch Celery group/chord

    Returns:
        True  → lotes despachados; el chord maneja Etapa E + job completion.
        False → documento pequeño (1 lote); usar ruta secuencial.
    """
    from docx import Document as DocxDocument
    from app.services.correction import _collect_all_paragraphs

    # Descargar DOCX y recolectar párrafos
    docx_bytes = _get_cached_docx_bytes(str(doc_id), doc.source_uri)
    tmpfile = tempfile.mktemp(suffix=".docx")
    with open(tmpfile, "wb") as f:
        f.write(docx_bytes)
    docx_doc = DocxDocument(tmpfile)
    Path(tmpfile).unlink(missing_ok=True)
    all_paragraphs = _collect_all_paragraphs(docx_doc)

    language = config.get("language", "es")
    disabled_rules = config.get("lt_disabled_rules", [])
    if profile_dict and profile_dict.get("lt_disabled_rules"):
        disabled_rules = list(set(disabled_rules + profile_dict["lt_disabled_rules"]))

    # Calcular batch boundaries (alineados a finales de sección)
    sections = analysis_result.get("sections", [])
    target_size = settings.parallel_correction_batch_size
    batch_boundaries = compute_batch_boundaries(sections, all_paragraphs, target_size)
    n_batches = min(len(batch_boundaries), settings.parallel_correction_max_batches)
    batch_boundaries = batch_boundaries[:n_batches]

    if len(batch_boundaries) <= 1:
        logger.info(
            f"[Etapa D] Solo {len(batch_boundaries)} lote ({len(all_paragraphs)} párrafos) "
            f"→ ruta secuencial (overhead paralelo no justificado)"
        )
        return False

    # Pass 1: LT en paralelo
    lt_workers = settings.parallel_correction_lt_workers
    _update_progress(
        db, doc_id, "correcting",
        f"Pass 1: LanguageTool paralelo ({lt_workers} workers)...",
    )
    lt_results = correct_all_paragraphs_lt_sync(
        all_paragraphs=all_paragraphs,
        language=language,
        disabled_rules=disabled_rules,
        max_workers=lt_workers,
    )

    # Serializar datos grandes a MinIO (evitar sobrecargar Redis)
    lt_results_key = f"correction/{doc_id}/lt_results.json"
    minio_client.upload_file(
        lt_results_key,
        json.dumps(lt_results, ensure_ascii=False).encode("utf-8"),
        content_type="application/json",
    )

    all_paragraphs_key = f"correction/{doc_id}/all_paragraphs.json"
    minio_client.upload_file(
        all_paragraphs_key,
        json.dumps(all_paragraphs, ensure_ascii=False).encode("utf-8"),
        content_type="application/json",
    )

    analysis_key = f"correction/{doc_id}/analysis.json"
    minio_client.upload_file(
        analysis_key,
        json.dumps(analysis_result, ensure_ascii=False).encode("utf-8"),
        content_type="application/json",
    )

    # Context seeds: texto post-LT del último párrafo no-vacío del batch anterior
    seeds: list[str | None] = [None]
    for b_idx in range(1, len(batch_boundaries)):
        prev_end = batch_boundaries[b_idx - 1][1]
        seed_text = ""
        for k in range(prev_end, max(-1, prev_end - 5), -1):
            lt_r = lt_results[k] if k < len(lt_results) else None
            if lt_r and not lt_r.get("skip"):
                seed_text = lt_r["corrected_text"][:200]
                break
        seeds.append(seed_text or None)

    # Crear CorrectionBatch records en BD (limpiar anteriores si re-procesamiento)
    db.execute(delete(CorrectionBatch).where(CorrectionBatch.doc_id == doc_id))
    for b_idx, (start, end) in enumerate(batch_boundaries):
        db.add(CorrectionBatch(
            doc_id=doc_id,
            batch_index=b_idx,
            start_paragraph=start,
            end_paragraph=end,
            paragraphs_total=end - start + 1,
            status="pending",
            context_seed=seeds[b_idx],
            lt_pass_completed=True,
        ))
    db.commit()

    profile_json = json.dumps(profile_dict, ensure_ascii=False) if profile_dict else None

    # Dispatch Celery group/chord
    from celery import group, chord as celery_chord
    batch_tasks = group(
        correct_batch_llm.s(
            doc_id=doc_id,
            batch_index=b_idx,
            start_para=start,
            end_para=end,
            lt_results_key=lt_results_key,
            context_seed=seeds[b_idx],
            all_paragraphs_key=all_paragraphs_key,
            profile_json=profile_json,
            analysis_key=analysis_key,
            language=language,
            disabled_rules=disabled_rules,
        )
        for b_idx, (start, end) in enumerate(batch_boundaries)
    )

    celery_chord(batch_tasks)(assemble_correction_results.s(
        doc_id=doc_id,
        batch_boundaries_json=json.dumps(batch_boundaries),
        lt_results_key=lt_results_key,
        all_paragraphs_key=all_paragraphs_key,
        profile_json=profile_json,
        analysis_key=analysis_key,
        enable_boundary_check=settings.parallel_correction_boundary_check,
        job_id=str(job.id),
    ))

    logger.info(
        f"[Etapa D] {len(batch_boundaries)} lotes paralelos despachados: "
        f"{[f'{s}-{e}' for s, e in batch_boundaries]}"
    )
    return True


# =====================================================================
# TAREA PRINCIPAL: PIPELINE COMPLETO
# =====================================================================

@celery_app.task(bind=True, max_retries=3, name="tasks_pipeline.process_document_pipeline")
def process_document_pipeline(self, doc_id: str):
    """
    Pipeline completo para un documento.
    Etapas A→B→C→D→E. Etapa D puede ser secuencial o paralela por lotes.
    """
    db = _get_sync_session()
    job = None

    try:
        # Semáforo: limitar pipelines concurrentes
        if not _acquire_pipeline_slot(doc_id):
            logger.info(f"Pipeline {doc_id}: esperando slot (max {settings.max_concurrent_pipelines} concurrentes)")
            raise self.retry(countdown=15, max_retries=200)

        doc = db.execute(select(Document).where(Document.id == doc_id)).scalar_one()
        job = _create_job(db, doc_id, "full_pipeline", self.request.id)

        stage_timings: dict[str, float] = {}
        worker_host = socket.gethostname()
        pipeline_start_dt = datetime.now(timezone.utc)

        db.execute(
            update(Document).where(Document.id == doc_id).values(
                processing_started_at=pipeline_start_dt,
                processing_completed_at=None,
                stage_timings={},
                worker_hostname=worker_host,
            )
        )
        db.commit()

        logger.info(f"=== INICIO PIPELINE: {doc.filename} ({doc_id}) worker={worker_host} ===")

        # ── Limpieza: eliminar datos previos (re-procesamiento) ──
        existing_pages = db.execute(
            select(Page).where(Page.doc_id == doc_id)
        ).scalars().all()
        if existing_pages:
            logger.info(f"Limpiando {len(existing_pages)} páginas previas...")
            for page in existing_pages:
                db.delete(page)
            db.commit()

        db.execute(delete(LlmUsage).where(LlmUsage.doc_id == doc_id))
        db.execute(delete(SectionSummary).where(SectionSummary.doc_id == doc_id))
        db.execute(delete(TermRegistry).where(TermRegistry.doc_id == doc_id))
        db.commit()

        # =============================================
        # ETAPA A: INGESTA
        # =============================================
        _update_document_status(db, doc_id, "converting")
        _update_progress(db, doc_id, "converting", "Convirtiendo DOCX a PDF...", start_stage=True)
        logger.info(f"[Etapa A] Convirtiendo {doc.filename}...")
        t0_a = time.time()

        ingestion_result = process_ingestion_sync(
            doc_id=str(doc_id),
            source_key=doc.source_uri,
            filename=doc.filename,
            original_format=doc.original_format,
        )

        pdf_uri = ingestion_result["pdf_uri"]
        total_pages = ingestion_result["total_pages"]

        _update_document_status(db, doc_id, "extracting", pdf_uri=pdf_uri, total_pages=total_pages)

        for page_no in range(1, total_pages + 1):
            db.add(Page(
                doc_id=doc_id,
                page_no=page_no,
                page_type="digital",
                render_route="docx_first",
                status="pending",
            ))
        db.commit()

        _update_progress(db, doc_id, "converting", "Conversión completada", current=1, total=1)
        logger.info(f"[Etapa A] Completada: {total_pages} páginas creadas")
        stage_timings["A"] = round(time.time() - t0_a, 1)
        _save_stage_timing(db, doc_id, stage_timings)

        # Cache DOCX bytes en Redis para evitar re-descargas en etapas C, D, E
        try:
            _rcache = _redis.Redis.from_url(settings.redis_url)
            _docx_cache_key = f"docx_cache:{doc_id}"
            _docx_bytes_cached = minio_client.download_file(doc.source_uri)
            _rcache.setex(_docx_cache_key, 7200, _docx_bytes_cached)  # TTL 2h
            logger.info(f"[Cache] DOCX cacheado en Redis ({len(_docx_bytes_cached)} bytes)")
        except Exception as _cache_err:
            logger.warning(f"[Cache] No se pudo cachear DOCX: {_cache_err}")

        # =============================================
        # ETAPA B: EXTRACCIÓN
        # =============================================
        _update_progress(
            db, doc_id, "extracting",
            f"Extrayendo layout de {total_pages} páginas...",
            total=total_pages, start_stage=True,
        )
        logger.info(f"[Etapa B] Extrayendo layout de {total_pages} páginas...")
        t0_b = time.time()

        pages = db.execute(
            select(Page).where(Page.doc_id == doc_id).order_by(Page.page_no)
        ).scalars().all()

        all_page_blocks = {}

        # Descargar PDF una sola vez para todas las páginas
        pdf_bytes = minio_client.download_file(pdf_uri)
        logger.info(f"[Etapa B] PDF descargado una vez ({len(pdf_bytes)} bytes)")

        batch_results = extract_all_pages_sync(doc_id=str(doc_id), pdf_bytes=pdf_bytes)

        for page_idx, page in enumerate(pages):
            _update_page_status(db, page.id, "extracting")
            _update_progress(
                db, doc_id, "extracting",
                f"Extrayendo página {page.page_no}/{total_pages}",
                current=page_idx, total=total_pages,
            )
            try:
                extraction_result = batch_results[page_idx]
                _update_page_status(
                    db, page.id, "extracted",
                    layout_uri=extraction_result["layout_uri"],
                    text_uri=extraction_result["text_uri"],
                    preview_uri=extraction_result["preview_uri"],
                )
                for block_data in extraction_result["blocks"]:
                    db.add(Block(
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
                    ))
                all_page_blocks[page.page_no] = extraction_result["blocks"]
            except Exception as e:
                logger.error(f"Error extrayendo página {page.page_no}: {e}")
                _update_page_status(db, page.id, "failed")

        db.commit()
        logger.info(f"[Etapa B] Completada: layouts extraídos")
        stage_timings["B"] = round(time.time() - t0_b, 1)
        _save_stage_timing(db, doc_id, stage_timings)

        # =============================================
        # ETAPA C: ANÁLISIS EDITORIAL
        # =============================================
        _update_document_status(db, doc_id, "analyzing")
        _update_progress(db, doc_id, "analyzing", "Análisis editorial en curso...", start_stage=True)
        logger.info(f"[Etapa C] Analizando documento...")
        t0_c = time.time()

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

        _docx_bytes = _get_cached_docx_bytes(str(doc_id), doc.source_uri)
        analysis_result = analyze_document_sync(
            doc_id=str(doc_id),
            docx_uri=doc.source_uri,
            profile=profile_dict,
            docx_bytes_cached=_docx_bytes,
        )

        for sec_data in analysis_result.get("sections", []):
            db.add(SectionSummary(
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
            ))

        for term_data in analysis_result.get("terms", []):
            db.add(TermRegistry(
                doc_id=doc_id,
                term=term_data["term"],
                normalized_form=term_data["normalized_form"],
                frequency=term_data["frequency"],
                first_occurrence_paragraph=term_data["first_occurrence_paragraph"],
                is_protected=term_data["is_protected"],
                decision=term_data["decision"],
            ))

        for record in analysis_result.get("usage_records", []):
            db.add(LlmUsage(doc_id=doc_id, **record))

        profile_updates = analysis_result.get("profile_updates", {})
        if profile_updates and profile_row:
            for key, value in profile_updates.items():
                if hasattr(profile_row, key):
                    setattr(profile_row, key, value)
            logger.info(f"[Etapa C] Perfil actualizado: {list(profile_updates.keys())}")

        if profile_dict and profile_updates:
            profile_dict.update(profile_updates)

        if profile_dict:
            analysis_protected = [
                t["term"] for t in analysis_result.get("terms", []) if t["is_protected"]
            ]
            existing_protected = set(profile_dict.get("protected_terms", []))
            new_terms = [t for t in analysis_protected if t not in existing_protected]
            if new_terms:
                profile_dict["protected_terms"] = list(existing_protected) + new_terms
                logger.info(f"[Etapa C] {len(new_terms)} términos protegidos agregados")

        classifications = analysis_result.get("paragraph_classifications", [])
        if classifications:
            cls_key = f"analysis/{doc_id}/classifications.json"
            minio_client.upload_file(
                cls_key,
                json.dumps(classifications, ensure_ascii=False).encode("utf-8"),
                content_type="application/json",
            )

        db.commit()
        logger.info(
            f"[Etapa C] Completada: "
            f"{len(analysis_result.get('sections', []))} secciones, "
            f"{len(analysis_result.get('terms', []))} términos"
        )
        stage_timings["C"] = round(time.time() - t0_c, 1)
        _save_stage_timing(db, doc_id, stage_timings)

        # =============================================
        # ETAPA D: CORRECCIÓN — LanguageTool + ChatGPT
        # =============================================
        _update_document_status(db, doc_id, "correcting")
        _update_progress(
            db, doc_id, "correcting", "Iniciando corrección de párrafos...", start_stage=True
        )
        logger.info(f"[Etapa D] Corrigiendo texto...")
        t0_d = time.time()

        config = doc.config_json or {}

        # Recargar páginas después del commit de Etapa C
        pages = db.execute(
            select(Page).where(Page.doc_id == doc_id).order_by(Page.page_no)
        ).scalars().all()

        docx_patches = []
        usage_records = []

        if doc.original_format == "docx":
            # ── Ruta paralela (feature flag) ──
            if settings.parallel_correction_enabled:
                dispatched = _dispatch_parallel_correction(
                    db=db, doc_id=str(doc_id), doc=doc,
                    config=config, profile_dict=profile_dict,
                    analysis_result=analysis_result, job=job,
                )
                if dispatched:
                    stage_timings["D"] = round(time.time() - t0_d, 1)
                    _save_stage_timing(db, doc_id, stage_timings)
                    logger.info(f"[Etapa D] Lotes paralelos despachados — pipeline delega a chord")
                    return  # assemble_correction_results maneja Etapa E + job completion

            # ── Ruta secuencial ──
            if profile_dict:
                logger.info(f"[Etapa D] Usando perfil editorial enriquecido por análisis")

            def _correction_progress(current: int, total: int):
                _update_progress(
                    db, doc_id, "correcting",
                    f"Corrigiendo párrafo {current}/{total}",
                    current=current, total=total,
                )

            logger.info("[Etapa D] Ruta 1: corrigiendo párrafos directamente del DOCX...")
            docx_patches, usage_records = correct_docx_sync(
                doc_id=str(doc_id),
                docx_uri=doc.source_uri,
                config=config,
                profile=profile_dict,
                analysis_data=analysis_result,
                on_progress=_correction_progress,
                docx_bytes_cached=_docx_bytes,
            )

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
                f"costo=${total_cost:.6f} USD, llamadas: {len(usage_records)}"
            )

        db.commit()
        logger.info(f"[Etapa D] Completada: {len(docx_patches)} párrafos corregidos")
        stage_timings["D"] = round(time.time() - t0_d, 1)
        _save_stage_timing(db, doc_id, stage_timings)

        # =============================================
        # ETAPAS D+E: PERSISTIR PATCHES + RENDERIZADO
        # =============================================
        _run_stage_e(db, str(doc_id), docx_patches)

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
            failed_stage = None
            try:
                d = db.execute(select(Document).where(Document.id == doc_id)).scalar_one_or_none()
                if d:
                    failed_stage = d.progress_stage or d.status
            except Exception:
                pass
            _update_document_status(db, doc_id, "failed", error_message=str(e))
            db.execute(
                update(Document).where(Document.id == doc_id).values(
                    processing_completed_at=datetime.now(timezone.utc),
                    progress_message=f"Error en etapa: {failed_stage or 'desconocida'}",
                    heartbeat_at=datetime.now(timezone.utc),
                )
            )
            db.commit()
        except Exception:
            pass
        # Retry con backoff exponencial (30s, 90s, 270s) en vez de fijo 60s
        retry_countdown = 30 * (3 ** self.request.retries)
        logger.warning(f"Pipeline {doc_id}: reintentando en {retry_countdown}s (intento {self.request.retries + 1}/3)")
        self.retry(exc=e, countdown=retry_countdown)

    finally:
        db.close()
        _release_pipeline_slot(doc_id)
        # Limpiar cache Redis
        try:
            _rcache = _redis.Redis.from_url(settings.redis_url)
            _rcache.delete(f"docx_cache:{doc_id}")
        except Exception:
            pass


# =====================================================================
# TAREAS CELERY PARA CORRECCIÓN PARALELA
# =====================================================================

@celery_app.task(bind=True, max_retries=3, name="tasks_pipeline.correct_batch_llm")
def correct_batch_llm(
    self,
    doc_id: str,
    batch_index: int,
    start_para: int,
    end_para: int,
    lt_results_key: str,
    context_seed: str | None,
    all_paragraphs_key: str,
    profile_json: str | None,
    analysis_key: str | None,
    language: str,
    disabled_rules: list[str],
) -> str:
    """
    Tarea Celery: Pass 2 (LLM) para un batch de párrafos [start_para..end_para].
    Descarga datos de MinIO, corre LLM secuencial dentro del batch, guarda resultado.

    Returns: MinIO key del resultado JSON.
    """
    from app.services.prompt_builder import build_system_prompt

    db = _get_sync_session()
    cb = None
    try:
        cb = db.execute(
            select(CorrectionBatch)
            .where(
                CorrectionBatch.doc_id == doc_id,
                CorrectionBatch.batch_index == batch_index,
            )
        ).scalar_one_or_none()

        if cb:
            cb.status = "running"
            cb.started_at = datetime.now(timezone.utc)
            cb.celery_task_id = self.request.id
            db.commit()

        # Descargar datos de MinIO
        lt_results = json.loads(minio_client.download_file(lt_results_key).decode("utf-8"))
        all_paragraphs = [
            tuple(p)
            for p in json.loads(minio_client.download_file(all_paragraphs_key).decode("utf-8"))
        ]

        analysis_data: dict = {}
        if analysis_key:
            analysis_data = json.loads(minio_client.download_file(analysis_key).decode("utf-8"))

        profile = json.loads(profile_json) if profile_json else None
        system_prompt = build_system_prompt() if profile else None
        max_expansion = profile.get("max_expansion_ratio", 1.15) if profile else 1.15
        sections = analysis_data.get("sections", [])
        para_classifications = {
            pc["paragraph_index"]: pc
            for pc in analysis_data.get("paragraph_classifications", [])
        }

        # Pass 2: LLM secuencial para este batch
        patches, usage_records, last_corrected_text = correct_batch_with_llm_sync(
            batch_index=batch_index,
            start_para=start_para,
            end_para=end_para,
            lt_results=lt_results,
            all_paragraphs=all_paragraphs,
            language=language,
            disabled_rules=disabled_rules,
            profile=profile,
            system_prompt=system_prompt,
            max_expansion=max_expansion,
            sections=sections,
            para_classifications=para_classifications,
            context_seed=context_seed,
        )

        # Guardar resultado en MinIO
        result_key = f"correction/{doc_id}/batch_{batch_index}_result.json"
        minio_client.upload_file(
            result_key,
            json.dumps(
                {
                    "batch_index": batch_index,
                    "patches": patches,
                    "usage_records": usage_records,
                    "last_corrected_text": last_corrected_text,
                },
                ensure_ascii=False,
            ).encode("utf-8"),
            content_type="application/json",
        )

        # Actualizar CorrectionBatch en BD
        if cb:
            cb.status = "completed"
            cb.llm_pass_completed = True
            cb.patches_count = len(patches)
            cb.paragraphs_corrected = len(patches)
            cb.last_corrected_text = (last_corrected_text or "")[:500]
            cb.completed_at = datetime.now(timezone.utc)
            db.commit()

        # Insertar LlmUsage records (costo por párrafo)
        for record in usage_records:
            db.add(LlmUsage(doc_id=doc_id, **record))
        db.commit()

        logger.info(
            f"[correct_batch_llm] Batch {batch_index} completado: "
            f"{len(patches)} parches → {result_key}"
        )
        return result_key

    except Exception as e:
        logger.exception(f"[correct_batch_llm] Error en batch {batch_index}: {e}")
        if cb:
            try:
                cb.status = "failed"
                cb.error_message = str(e)[:500]
                db.commit()
            except Exception:
                pass
        self.retry(exc=e, countdown=30)

    finally:
        db.close()


@celery_app.task(bind=True, name="tasks_pipeline.assemble_correction_results")
def assemble_correction_results(
    self,
    batch_result_keys: list[str],
    doc_id: str,
    batch_boundaries_json: str,
    lt_results_key: str,
    all_paragraphs_key: str,
    profile_json: str | None,
    analysis_key: str | None,
    enable_boundary_check: bool,
    job_id: str,
) -> None:
    """
    Chord callback: combina todos los batch results, aplica boundary check opcional,
    ordena patches, persiste en BD y lanza Etapa E (renderizado).
    """
    db = _get_sync_session()
    job = None
    try:
        job = db.execute(select(Job).where(Job.id == job_id)).scalar_one_or_none()

        # Cargar todos los resultados de los batches desde MinIO
        all_patches: list[dict] = []
        all_usage_records: list[dict] = []
        batch_results_map: dict[int, dict] = {}

        for result_key in batch_result_keys:
            try:
                data = json.loads(minio_client.download_file(result_key).decode("utf-8"))
                bidx = data["batch_index"]
                batch_results_map[bidx] = data
                all_patches.extend(data.get("patches", []))
                all_usage_records.extend(data.get("usage_records", []))
            except Exception as e:
                logger.error(f"[assemble] Error cargando batch result {result_key}: {e}")

        logger.info(
            f"[assemble] {len(all_patches)} patches cargados de "
            f"{len(batch_result_keys)} batches"
        )

        # Boundary check opcional (Fase 4: re-corrección real; ahora es stub)
        if enable_boundary_check and len(batch_results_map) > 1:
            try:
                batch_boundaries = json.loads(batch_boundaries_json)
                all_paragraphs = [
                    tuple(p)
                    for p in json.loads(
                        minio_client.download_file(all_paragraphs_key).decode("utf-8")
                    )
                ]
                lt_results = json.loads(
                    minio_client.download_file(lt_results_key).decode("utf-8")
                )
                profile = json.loads(profile_json) if profile_json else None
                analysis_data = (
                    json.loads(minio_client.download_file(analysis_key).decode("utf-8"))
                    if analysis_key
                    else {}
                )

                from app.services.prompt_builder import build_system_prompt
                system_prompt = build_system_prompt() if profile else None
                max_expansion = profile.get("max_expansion_ratio", 1.15) if profile else 1.15
                disabled_rules = profile.get("lt_disabled_rules", []) if profile else []

                all_patches = check_batch_boundaries(
                    batch_results=batch_results_map,
                    batch_boundaries=batch_boundaries,
                    lt_results=lt_results,
                    all_paragraphs=all_paragraphs,
                    language="es",
                    disabled_rules=disabled_rules,
                    profile=profile,
                    system_prompt=system_prompt,
                    max_expansion=max_expansion,
                    sections=analysis_data.get("sections", []),
                    para_classifications={
                        pc["paragraph_index"]: pc
                        for pc in analysis_data.get("paragraph_classifications", [])
                    },
                    all_patches=all_patches,
                )
                logger.info(f"[assemble] Boundary check completado")
            except Exception as e:
                logger.warning(f"[assemble] Boundary check falló, continuando: {e}")

        # Ordenar patches por paragraph_index (garantiza orden DOCX)
        all_patches.sort(key=lambda p: p.get("paragraph_index", 0))

        # Guardar patches consolidados en MinIO (sobrescribe el de la ruta secuencial si existe)
        patch_key = f"docx/{doc_id}/patches_docx.json"
        minio_client.upload_file(
            patch_key,
            json.dumps(all_patches, ensure_ascii=False, indent=2).encode("utf-8"),
            content_type="application/json",
        )

        # Etapas D+E: persistir patches + renderizado
        _run_stage_e(db, doc_id, all_patches)

        if job:
            _complete_job(db, job)

        logger.info(f"=== [assemble] PIPELINE PARALELO COMPLETADO: {doc_id} ===")

    except Exception as e:
        logger.exception(f"[assemble] Error ensamblando resultados para {doc_id}: {e}")
        try:
            db.rollback()
        except Exception:
            pass
        if job:
            try:
                _complete_job(db, job, error=str(e))
            except Exception:
                pass
        try:
            _update_document_status(db, doc_id, "failed", error_message=str(e))
            db.execute(
                update(Document).where(Document.id == doc_id).values(
                    processing_completed_at=datetime.now(timezone.utc),
                    progress_message="Error ensamblando resultados paralelos",
                    heartbeat_at=datetime.now(timezone.utc),
                )
            )
            db.commit()
        except Exception:
            pass

    finally:
        db.close()
        _release_pipeline_slot(doc_id)
