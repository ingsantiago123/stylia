"""
Tareas Celery para el pipeline MVP 1 + corrección paralela por lotes.
Pipeline: ingest → extract → analyze → correct (secuencial o paralelo) → render.
"""

import json
import logging
import re
import socket
import time
from datetime import datetime, timezone
from difflib import SequenceMatcher

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
from app.models.document_global_context import DocumentGlobalContext
from app.models.llm_audit_log import LlmAuditLog

from app.utils import minio_client
from app.services.ingestion import process_ingestion_sync
from app.services.extraction import extract_all_pages_sync
from app.services.analysis import analyze_document_sync, analyze_global_context_sync
from app.services.correction import (
    correct_page_blocks_sync,
    correct_docx_sync,
    correct_batch_with_llm_sync,
    compute_batch_boundaries,
    correct_all_paragraphs_lt_sync,
    check_batch_boundaries,
    save_paragraph_locations_sync,
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

def _persist_patches(db: Session, doc_id: str, docx_patches: list[dict]) -> None:
    """
    Persiste patches en BD y pone documento en pending_review.
    NO ejecuta renderizado — eso se hace después de la revisión humana.
    """
    t0 = time.time()
    doc = db.execute(select(Document).where(Document.id == doc_id)).scalar_one()
    existing_timings = dict(doc.stage_timings or {})
    pages = db.execute(
        select(Page).where(Page.doc_id == doc_id).order_by(Page.page_no)
    ).scalars().all()

    # PDF nativo: hay DOCX de trabajo (doc.docx_uri) → los patches SÍ se
    # persisten y renderizan. Antes este stub descartaba todo el trabajo
    # de corrección de cualquier entrada no-DOCX en silencio.
    _has_workable_docx = doc.original_format == "docx" or bool(doc.docx_uri)
    if not docx_patches or not _has_workable_docx:
        if not docx_patches:
            logger.info("[Persist] Sin correcciones — documento limpio, completando directo")
        elif not _has_workable_docx:
            logger.warning(
                "[Persist] Documento sin DOCX de trabajo — patches no aplicables"
            )
        elapsed = round(time.time() - t0, 1)
        existing_timings["D_persist"] = elapsed
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
            # Instrumentación Fase 0: este fallback ancla el patch a un bloque
            # ARBITRARIO. Cuantificarlo es prerequisito para eliminarlo.
            logger.warning(
                f"[Persist] fallback_first_block: patch sin match fiable "
                f"(score={best_score:.2f}, para_idx={para_idx}) → anclado a bloque "
                f"arbitrario de página estimada {est_page}"
            )
            if blocks_by_page.get(est_page):
                return blocks_by_page[est_page][0][0]
            return all_blocks_flat[0][0]
        return best_block

    # ── Crear registros Patch en BD ──
    total_paragraphs = len(docx_patches)
    patch_version = 1

    for patch_data in docx_patches:
        # H1: preservar None en patches grupales — forzarlos a 0 los hacía
        # colapsar entre sí en la deduplicación del render candidato.
        para_idx = patch_data.get("paragraph_index")
        p_location = patch_data.get("location") or None

        # Nivel 2/3 — patches grupales vienen con block_id explícito
        db_block = None
        if patch_data.get("block_id"):
            db_block = db.execute(
                select(Block).where(Block.id == patch_data["block_id"])
            ).scalar_one_or_none()

        if db_block is None:
            db_block = _find_best_block(
                patch_data.get("original_text", ""), para_idx or 0, total_paragraphs
            )
        if not db_block:
            continue

        llm_changes = patch_data.get("changes", [])
        route = patch_data.get("route_taken")
        p_review_status = patch_data.get("review_status", "auto_accepted")
        p_review_reason = patch_data.get("review_reason")
        p_gate_results = patch_data.get("gate_results")
        # Sprint 3: Audit trail dual-engine
        p_lt_corrections = patch_data.get("lt_corrections_json")
        p_llm_log = patch_data.get("llm_change_log_json")
        p_reverted = patch_data.get("reverted_lt_changes_json")
        p_protected = patch_data.get("protected_regions_snapshot")
        # Nivel 2/3 — agrupación grupal
        p_group_id = patch_data.get("group_id")
        p_group_call_index = patch_data.get("group_call_index")
        p_group_call_id = patch_data.get("group_call_id")
        p_structural_role = patch_data.get("structural_role")

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
                    pass_number=patch_data.get("pass_number") or (2 if "chatgpt" in patch_data["source"] else 1),
                    model_used=patch_data.get("model_used", "languagetool"),
                    paragraph_index=para_idx,
                    route_taken=route,
                    lt_corrections_json=p_lt_corrections,
                    llm_change_log_json=p_llm_log,
                    reverted_lt_changes_json=p_reverted,
                    protected_regions_snapshot=p_protected,
                    corrected_pass1_text=patch_data.get("corrected_pass1_text"),
                    pass2_audit_json=patch_data.get("pass2_audit_json"),
                    location=p_location,
                    group_id=p_group_id,
                    group_call_index=p_group_call_index,
                    group_call_id=p_group_call_id,
                    structural_role=p_structural_role,
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
                category=patch_data.get("category"),
                severity=patch_data.get("severity"),
                explanation=patch_data.get("explanation"),
                confidence=patch_data.get("confidence"),
                rewrite_ratio=patch_data.get("rewrite_ratio"),
                pass_number=patch_data.get("pass_number") or 1,
                model_used=patch_data.get("model_used", "languagetool"),
                paragraph_index=para_idx,
                route_taken=route,
                lt_corrections_json=p_lt_corrections,
                llm_change_log_json=p_llm_log,
                reverted_lt_changes_json=p_reverted,
                protected_regions_snapshot=p_protected,
                corrected_pass1_text=patch_data.get("corrected_pass1_text"),
                pass2_audit_json=patch_data.get("pass2_audit_json"),
                location=p_location,
                group_id=p_group_id,
                group_call_index=p_group_call_index,
                group_call_id=p_group_call_id,
                structural_role=p_structural_role,
            ))
            patch_version += 1

    # Marcar páginas como corregidas
    for page in pages:
        if page.status != "failed":
            _update_page_status(db, page.id, "corrected")

    db.commit()

    elapsed = round(time.time() - t0, 1)
    existing_timings["D_persist"] = elapsed
    db.execute(update(Document).where(Document.id == doc_id).values(
        stage_timings=existing_timings,
        heartbeat_at=datetime.now(timezone.utc),
    ))
    db.commit()

    logger.info(f"[Persist] {patch_version - 1} registros de patches guardados en BD")


def _run_candidate_render(db: Session, doc_id: str) -> None:
    """
    Renderiza versión candidata usando TODOS los patches (sin filtrar por review_status).
    Genera previews PNG y anotaciones con patch_ids para revisión visual compare-first.
    Flujo: candidate_rendering → candidate_ready.
    """
    t0 = time.time()
    doc = db.execute(select(Document).where(Document.id == doc_id)).scalar_one()
    existing_timings = dict(doc.stage_timings or {})

    _update_document_status(db, doc_id, "candidate_rendering")
    _update_progress(db, doc_id, "candidate_rendering", "Generando vista previa candidata...", start_stage=True)
    logger.info(f"[Candidato] Renderizando versión candidata para {doc_id}...")

    # Cargar TODOS los patches de BD (sin filtrar) — incluye patch.id para vincular
    all_patch_rows = db.execute(
        select(Patch)
        .join(Block)
        .join(Page)
        .where(Page.doc_id == doc_id)
        .order_by(Patch.paragraph_index)
    ).scalars().all()

    if not all_patch_rows:
        logger.info("[Candidato] Sin patches — marcando como completed")
        elapsed = round(time.time() - t0, 1)
        existing_timings["E_candidate"] = elapsed
        _update_document_status(db, doc_id, "completed")
        db.execute(update(Document).where(Document.id == doc_id).values(
            processing_completed_at=datetime.now(timezone.utc),
            stage_timings=existing_timings,
        ))
        db.commit()
        _cleanup_progress(db, doc_id)
        return

    # H1: la identidad de un párrafo es su location (BD); paragraph_index es
    # solo fallback legacy. Antes, todos los patches grupales (paragraph_index
    # NULL) colapsaban en la clave 0 y se descartaban del render.
    def _dedup_key(p) -> str:
        if p.location:
            return f"loc:{p.location}"
        return f"idx:{p.paragraph_index if p.paragraph_index is not None else -1}"

    para_patch_ids: dict[str, list[str]] = {}
    for p in all_patch_rows:
        para_patch_ids.setdefault(_dedup_key(p), []).append(str(p.id))

    # Construir dicts con patch_ids y review_status
    # Deduplicar por identidad de párrafo (patches comparten original/corrected_text)
    seen_paragraphs: set[str] = set()
    docx_patches: list[dict] = []
    for p in all_patch_rows:
        key = _dedup_key(p)
        if key in seen_paragraphs:
            continue
        seen_paragraphs.add(key)
        docx_patches.append({
            "patch_ids": para_patch_ids.get(key, []),
            "paragraph_index": p.paragraph_index if p.paragraph_index is not None else 0,
            "location": p.location or "",
            "original_text": p.original_text,
            "corrected_text": p.corrected_text,
            "source": p.source,
            "review_status": p.review_status,
            "changes": p.operations_json or [],
            "category": p.category,
            "severity": p.severity,
            "explanation": p.explanation,
            "confidence": p.confidence,
            "group_id": str(p.group_id) if p.group_id else None,
            "group_call_index": p.group_call_index,
            "structural_role": p.structural_role,
        })

    # Fallback legacy: documentos procesados antes de la columna `location`
    # reconstruyen la ubicación desde MinIO (solo entradas sin location).
    missing_loc = [dp for dp in docx_patches if not dp["location"]]
    if missing_loc:
        try:
            patch_key = f"docx/{doc_id}/patches_docx.json"
            if minio_client.file_exists(patch_key):
                stored_patches = json.loads(minio_client.download_file(patch_key).decode("utf-8"))
                location_index: dict[tuple, str] = {}
                for sp in stored_patches:
                    key = (sp.get("paragraph_index", 0), sp.get("original_text", "")[:50])
                    location_index[key] = sp.get("location", "")
                for dp in missing_loc:
                    key = (dp["paragraph_index"], dp["original_text"][:50])
                    dp["location"] = location_index.get(key, "")
        except Exception as e:
            logger.warning(f"[Candidato] Error cargando locations de MinIO: {e}")

    logger.info(f"[Candidato] {len(docx_patches)} párrafos a renderizar como candidato")

    _render_docx_uri = doc.docx_uri or doc.source_uri
    _docx_bytes = _get_cached_docx_bytes(str(doc_id), _render_docx_uri)
    render_result = render_docx_first_sync(
        doc_id=str(doc_id),
        docx_uri=_render_docx_uri,
        filename=doc.filename,
        all_patches=docx_patches,
        docx_bytes_cached=_docx_bytes,
        apply_mode="all",
        render_mode="candidate",
    )

    elapsed = round(time.time() - t0, 1)
    existing_timings["E_candidate"] = elapsed
    _update_document_status(db, doc_id, "candidate_ready")
    db.execute(update(Document).where(Document.id == doc_id).values(
        stage_timings=existing_timings,
        progress_message="Candidato listo para revisión visual",
        heartbeat_at=datetime.now(timezone.utc),
    ))
    db.commit()

    logger.info(
        f"[Candidato] Documento {doc_id} → candidate_ready "
        f"({render_result.get('changes_count', 0)} correcciones renderizadas, {elapsed}s)"
    )


def _run_stage_e(db: Session, doc_id: str, apply_mode: str = "accepted_and_auto") -> None:
    """
    Etapa E: Renderizado DOCX-first con patches filtrados por review_status.
    Se ejecuta DESPUÉS de la revisión humana, lanzada por render_approved_patches.
    """
    t0_e = time.time()
    doc = db.execute(select(Document).where(Document.id == doc_id)).scalar_one()
    existing_timings = dict(doc.stage_timings or {})
    pages = db.execute(
        select(Page).where(Page.doc_id == doc_id).order_by(Page.page_no)
    ).scalars().all()

    _update_document_status(db, doc_id, "finalizing")
    _update_progress(db, doc_id, "finalizing", "Generando documento final...", start_stage=True)
    logger.info(f"[Etapa E] Finalizando documento {doc_id} (mode={apply_mode})...")

    # Cargar patches de BD filtrados por review_status
    if apply_mode == "accepted_only":
        accepted_statuses = ("accepted",)
    else:  # accepted_and_auto: incluye auto_accepted + bulk_finalized
        accepted_statuses = ("accepted", "auto_accepted", "bulk_finalized")

    all_patch_rows = db.execute(
        select(Patch)
        .join(Block)
        .join(Page)
        .where(
            Page.doc_id == doc_id,
            Patch.review_status.in_(accepted_statuses),
        )
        .order_by(Patch.paragraph_index)
    ).scalars().all()

    # Convertir a dicts para render_docx_first_sync
    # H1: location, group_id y structural_role salen de BD — antes los patches
    # grupales llegaban aquí sin agrupación ni ubicación y nunca se aplicaban.
    # Si hay edited_text, usar eso en lugar de corrected_text.
    # Deduplicar por identidad (varios Patch por párrafo comparten texto completo).
    seen_keys: set[str] = set()
    docx_patches = []
    patch_ids_by_key: dict[str, list[str]] = {}
    for p in all_patch_rows:
        key = f"loc:{p.location}" if p.location else (
            f"idx:{p.paragraph_index if p.paragraph_index is not None else -1}"
        )
        patch_ids_by_key.setdefault(key, []).append(str(p.id))
    for p in all_patch_rows:
        key = f"loc:{p.location}" if p.location else (
            f"idx:{p.paragraph_index if p.paragraph_index is not None else -1}"
        )
        if key in seen_keys:
            continue
        seen_keys.add(key)
        final_text = p.corrected_text
        if hasattr(p, 'edited_text') and p.edited_text:
            final_text = p.edited_text
        docx_patches.append({
            "patch_ids": patch_ids_by_key.get(key, []),
            "paragraph_index": p.paragraph_index if p.paragraph_index is not None else 0,
            "location": p.location or "",
            "original_text": p.original_text,
            "corrected_text": final_text,
            "source": p.source,
            "review_status": p.review_status,
            "changes": p.operations_json or [],
            "category": p.category,
            "severity": p.severity,
            "explanation": p.explanation,
            "confidence": p.confidence,
            "group_id": str(p.group_id) if p.group_id else None,
            "group_call_index": p.group_call_index,
            "structural_role": p.structural_role,
        })

    # Fallback legacy: documentos sin columna location poblada
    missing_loc = [dp for dp in docx_patches if not dp["location"]]
    if missing_loc:
        try:
            patch_key = f"docx/{doc_id}/patches_docx.json"
            if minio_client.file_exists(patch_key):
                import json as _json
                stored_patches = _json.loads(minio_client.download_file(patch_key).decode("utf-8"))
                location_index: dict[tuple, str] = {}
                for sp in stored_patches:
                    key = (sp.get("paragraph_index", 0), sp.get("original_text", "")[:50])
                    location_index[key] = sp.get("location", "")
                for dp in missing_loc:
                    key = (dp["paragraph_index"], dp["original_text"][:50])
                    dp["location"] = location_index.get(key, "")
        except Exception as e:
            logger.warning(f"[Etapa E] Error cargando locations de MinIO: {e}")

    if not docx_patches:
        logger.info("[Etapa E] Sin correcciones aprobadas — documento sin cambios")
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

    logger.info(f"[Etapa E] {len(docx_patches)} correcciones aprobadas a aplicar")

    _render_docx_uri = doc.docx_uri or doc.source_uri
    _docx_bytes_for_render = _get_cached_docx_bytes(str(doc_id), _render_docx_uri)
    render_result = render_docx_first_sync(
        doc_id=str(doc_id),
        docx_uri=_render_docx_uri,
        filename=doc.filename,
        all_patches=docx_patches,
        docx_bytes_cached=_docx_bytes_for_render,
        apply_mode="all",  # Already filtered above
    )

    # H4: marcar como aplicados SOLO los patches que el renderer aplicó de
    # verdad. Antes se marcaba en bloque todo lo aprobado, aunque el render
    # los hubiera omitido por mismatch/no_paragraph — la BD mentía.
    applied_ids = render_result.get("applied_patch_ids") or []
    if applied_ids:
        db.execute(
            update(Patch)
            .where(Patch.id.in_(applied_ids))
            .values(applied=True)
        )
    _applied_set = set(applied_ids)
    skipped_in_render = sum(
        1 for dp in docx_patches
        if not (_applied_set & set(dp.get("patch_ids") or []))
    )
    if skipped_in_render > 0:
        logger.warning(
            f"[Etapa E] {skipped_in_render} párrafos aprobados NO se aplicaron "
            f"(mismatch/no_paragraph) — quedan con applied=False"
        )

    # Marcar páginas como renderizadas
    for page in pages:
        if page.status != "failed":
            _update_page_status(db, page.id, "rendered")
    db.commit()

    # Incrementar render_version
    current_version = doc.render_version if hasattr(doc, 'render_version') else 1
    new_version = current_version + 1

    elapsed_e = round(time.time() - t0_e, 1)
    existing_timings["E"] = elapsed_e
    _update_document_status(db, doc_id, "completed")
    db.execute(update(Document).where(Document.id == doc_id).values(
        processing_completed_at=datetime.now(timezone.utc),
        stage_timings=existing_timings,
        render_version=new_version,
    ))
    db.commit()
    _cleanup_progress(db, doc_id)

    logger.info(
        f"[Etapa E] Completada: {render_result.get('changes_count', 0)} correcciones aplicadas, "
        f"render_version={new_version}"
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
    global_context_dict: dict | None = None,
    block_meta_map: dict | None = None,
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
    import io as _io
    from docx import Document as DocxDocument
    from app.services.correction import (
        _collect_all_paragraphs,
        compute_grouped_paragraph_indexes_sync,
    )

    # Descargar DOCX y recolectar párrafos (BytesIO: sin tempfile inseguro)
    # PDF nativo: doc.docx_uri apunta al DOCX convertido por pdf2docx
    docx_bytes = _get_cached_docx_bytes(str(doc_id), doc.docx_uri or doc.source_uri)
    docx_doc = DocxDocument(_io.BytesIO(docx_bytes))
    all_paragraphs = _collect_all_paragraphs(docx_doc)

    # H3 (Fase 0): párrafos que pertenecen a un ElementGroup (B.5) se omiten
    # de la pasada individual en TODOS los lotes — antes la ruta paralela
    # ignoraba por completo la conciencia estructural.
    grouped_indexes: list[int] = []
    try:
        grouped_indexes = sorted(
            compute_grouped_paragraph_indexes_sync(doc_id, db, all_paragraphs)
        )
        if grouped_indexes:
            logger.info(
                f"[Etapa D] {len(grouped_indexes)} párrafos agrupados (listas/tablas) "
                f"se omitirán en los lotes individuales"
            )
    except Exception as _gie:
        logger.warning(f"[Etapa D] No se pudieron computar índices grupales: {_gie}")

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

    # Plan v4: serializar contexto global para que cada lote lo use en la doble pasada
    global_context_key: str | None = None
    if global_context_dict:
        global_context_key = f"correction/{doc_id}/global_context.json"
        minio_client.upload_file(
            global_context_key,
            json.dumps(global_context_dict, ensure_ascii=False).encode("utf-8"),
            content_type="application/json",
        )

    # Fase 3/5: metadata estructural + página real para los prompts de los lotes
    block_meta_key: str | None = None
    if block_meta_map:
        block_meta_key = f"correction/{doc_id}/block_meta.json"
        minio_client.upload_file(
            block_meta_key,
            json.dumps(block_meta_map, ensure_ascii=False).encode("utf-8"),
            content_type="application/json",
        )

    # Context seeds: texto post-LT del último párrafo no-vacío del batch anterior
    # seed_windows: ventana de N párrafos previos (configurable context_window_size)
    seeds: list[str | None] = [None]
    seed_windows: list[list[str] | None] = [None]
    for b_idx in range(1, len(batch_boundaries)):
        prev_end = batch_boundaries[b_idx - 1][1]
        window_texts: list[str] = []
        scan_back = settings.context_window_size * 3  # scan wider to find N non-empty
        for k in range(prev_end, max(-1, prev_end - scan_back), -1):
            lt_r = lt_results[k] if k < len(lt_results) else None
            if lt_r and not lt_r.get("skip") and lt_r.get("corrected_text", "").strip():
                window_texts.insert(0, lt_r["corrected_text"][:200])
                if len(window_texts) >= settings.context_window_size:
                    break
        seed_text = window_texts[-1] if window_texts else ""
        seeds.append(seed_text or None)
        seed_windows.append(window_texts if window_texts else None)

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
            context_seed_window=seed_windows[b_idx],
            all_paragraphs_key=all_paragraphs_key,
            profile_json=profile_json,
            analysis_key=analysis_key,
            language=language,
            disabled_rules=disabled_rules,
            global_context_key=global_context_key,
            grouped_indexes=grouped_indexes,
            block_meta_key=block_meta_key,
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
        global_context_key=global_context_key,
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

        # PDF nativo: la ingesta generó un DOCX de trabajo (pdf2docx).
        # Todo el pipeline DOCX-first opera sobre él.
        _status_extra = {}
        if ingestion_result.get("docx_uri"):
            doc.docx_uri = ingestion_result["docx_uri"]
            _status_extra["docx_uri"] = ingestion_result["docx_uri"]
            logger.info(f"[Etapa A] PDF nativo → DOCX de trabajo: {doc.docx_uri}")

        _update_document_status(
            db, doc_id, "extracting",
            pdf_uri=pdf_uri, total_pages=total_pages, **_status_extra,
        )

        # URI del DOCX sobre el que corre TODO el pipeline (source para DOCX
        # nativos; el convertido para PDFs)
        docx_source_uri = doc.docx_uri or doc.source_uri

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
            _docx_bytes_cached = minio_client.download_file(docx_source_uri)
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
        # ETAPA B.5: EXTRACCIÓN ESTRUCTURAL DOCX (Nivel 3)
        # Enriquece los Block con metadata nativa del DOCX (style_name,
        # list_*, table_*) y crea ElementGroup por cada lista/tabla.
        # =============================================
        _update_document_status(db, doc_id, "extracted_docx")
        _update_progress(
            db, doc_id, "extracted_docx",
            "Detectando estructura DOCX...", start_stage=True,
        )
        t0_b5 = time.time()
        try:
            from app.services.extraction_docx import extract_docx_structure_sync
            docx_bytes = _get_cached_docx_bytes(doc_id, doc.docx_uri or doc.source_uri)
            b5_summary = extract_docx_structure_sync(
                doc_id=doc_id,
                docx_uri=doc.docx_uri or doc.source_uri,
                session=db,
                docx_bytes_cached=docx_bytes,
            )
            logger.info(f"[Etapa B.5] {b5_summary}")
        except Exception as e:
            # NO bloqueante: si B.5 falla, el pipeline sigue con el flujo
            # heurístico clásico. La metadata estructural simplemente no
            # se persiste y los prompts caen a su comportamiento Nivel 1.
            logger.warning(
                f"[Etapa B.5] Falló enrichment estructural (se continúa sin él): {e}"
            )
        stage_timings["B5"] = round(time.time() - t0_b5, 1)

        # Recoger ubicaciones DOCX de bloques ya asignados a un grupo estructural.
        # Se usará en Etapa D para saltar esos párrafos en la pasada individual.
        _grouped_locations: set[str] = set()
        try:
            from app.models.block import Block as _Block
            from app.models.page import Page as _Page
            _grp_rows = db.execute(
                select(_Block.docx_location)
                .join(_Page, _Block.page_id == _Page.id)
                .where(_Page.doc_id == doc_id, _Block.element_group_id.isnot(None))
            ).all()
            _grouped_locations = {r[0] for r in _grp_rows if r[0]}
            if _grouped_locations:
                logger.info(f"[Etapa B.5] {len(_grouped_locations)} ubicaciones grupales — se omitirán en D individual")
        except Exception as _ge:
            logger.warning(f"[Etapa B.5] No se pudo construir grouped_locations: {_ge}")
        _save_stage_timing(db, doc_id, stage_timings)

        # =============================================
        # ETAPA B.6: AST DOCUMENTAL (Fases 1-2)
        # Parsea el DOCX a document_nodes en orden REAL del documento
        # (identidad determinista oxml_path + content_hash). Captura tablas
        # anidadas, textboxes y footnotes invisibles para el flujo legacy.
        # ETAPA B.7: PAGINACIÓN REAL (Fase 3)
        # Alinea las palabras del PDF contra los nodos y escribe la página
        # real de cada párrafo — reemplaza la estimación lineal.
        # =============================================
        _node_page_map: dict[str, dict] = {}
        t0_b6 = time.time()
        try:
            if settings.structural_parser_enabled:
                from app.services.document_parser import parse_document_to_nodes_sync
                _docx_b6 = _get_cached_docx_bytes(doc_id, doc.docx_uri or doc.source_uri)
                b6_summary = parse_document_to_nodes_sync(
                    doc_id=str(doc_id), docx_bytes=_docx_b6, session=db,
                )
                logger.info(f"[Etapa B.6] {b6_summary}")
                if settings.page_alignment_enabled:
                    try:
                        from app.services.page_alignment import align_nodes_to_pdf_sync
                        _node_page_map = align_nodes_to_pdf_sync(str(doc_id), pdf_bytes, db)
                        logger.info(
                            f"[Etapa B.7] {len(_node_page_map)} ubicaciones con página real"
                        )
                    except Exception as _pa_err:
                        logger.warning(
                            f"[Etapa B.7] Alineación de páginas falló (no bloqueante): {_pa_err}"
                        )
        except Exception as _b6_err:
            logger.warning(f"[Etapa B.6] Parser estructural falló (no bloqueante): {_b6_err}")
        stage_timings["B6"] = round(time.time() - t0_b6, 1)
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
                "genre": getattr(profile_row, "genre", None),
                "subgenre": getattr(profile_row, "subgenre", None),
                "preserve_author_voice": profile_row.preserve_author_voice,
                "max_rewrite_ratio": profile_row.max_rewrite_ratio,
                "max_expansion_ratio": profile_row.max_expansion_ratio,
                "style_priorities": profile_row.style_priorities or [],
                "protected_terms": profile_row.protected_terms or [],
                "forbidden_changes": profile_row.forbidden_changes or [],
                "lt_disabled_rules": profile_row.lt_disabled_rules or [],
                "register_constraints": getattr(profile_row, "register_constraints", None) or [],
                "idiolect_protections": getattr(profile_row, "idiolect_protections", None) or [],
                # Configuración granular del prompt (UI). None = todos los bloques activos.
                "prompt_blocks": getattr(profile_row, "prompt_blocks", None),
            }
            logger.info(f"[Etapa C] Perfil editorial: {profile_row.preset_name or 'custom'}")

        _docx_bytes = _get_cached_docx_bytes(str(doc_id), docx_source_uri)
        analysis_result = analyze_document_sync(
            doc_id=str(doc_id),
            docx_uri=docx_source_uri,
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
            # Escribir paragraph_type en blocks (match por docx_location = location)
            try:
                from app.models.block import Block as _BlockC
                from app.models.page import Page as _PageC
                loc_to_ptype = {pc["location"]: pc["paragraph_type"] for pc in classifications if pc.get("paragraph_type")}
                if loc_to_ptype:
                    _blk_rows = db.execute(
                        select(_BlockC)
                        .join(_PageC, _BlockC.page_id == _PageC.id)
                        .where(_PageC.doc_id == doc_id)
                    ).scalars().all()
                    updated_count = 0
                    for blk in _blk_rows:
                        loc = blk.docx_location or ""
                        ptype = loc_to_ptype.get(loc)
                        if ptype and blk.paragraph_type != ptype:
                            blk.paragraph_type = ptype
                            updated_count += 1
                    if updated_count:
                        db.flush()
                        logger.info(f"[Etapa C] paragraph_type escrito en {updated_count} blocks")
            except Exception as _pte:
                logger.warning(f"[Etapa C] No se pudo escribir paragraph_type en blocks (no bloqueante): {_pte}")

        # =============================================
        # C.6: Análisis de Contexto Global (Plan v4)
        # =============================================
        global_context_dict: dict | None = None
        try:
            all_paras_for_c6 = [
                (pc["text_preview"], pc["location"])
                for pc in analysis_result.get("paragraph_classifications", [])
            ]
            protected_terms_for_c6 = [
                t["term"] for t in analysis_result.get("terms", []) if t["is_protected"]
            ]
            c6_result = analyze_global_context_sync(
                doc_id=str(doc_id),
                all_paragraphs=all_paras_for_c6,
                profile=profile_dict,
                protected_terms=protected_terms_for_c6,
            )
            global_context_dict = {
                "global_summary": c6_result.get("global_summary"),
                "dominant_voice": c6_result.get("dominant_voice"),
                "dominant_register": c6_result.get("dominant_register"),
                "key_themes_json": c6_result.get("key_themes_json", []),
                "protected_globals_json": c6_result.get("protected_globals_json", []),
                "style_fingerprint_json": c6_result.get("style_fingerprint_json", {}),
            }
            # Persistir en document_global_context
            existing_gc = db.execute(
                select(DocumentGlobalContext).where(DocumentGlobalContext.doc_id == doc_id)
            ).scalar_one_or_none()
            if existing_gc:
                for k, v in global_context_dict.items():
                    setattr(existing_gc, k, v)
                existing_gc.total_paragraphs = analysis_result.get("stats", {}).get("total_paragraphs")
            else:
                db.add(DocumentGlobalContext(
                    doc_id=doc_id,
                    total_paragraphs=analysis_result.get("stats", {}).get("total_paragraphs"),
                    **global_context_dict,
                ))
            # Agregar uso LLM de C.6 si existe
            if c6_result.get("usage_record"):
                db.add(LlmUsage(doc_id=doc_id, **c6_result["usage_record"]))
            # Agregar términos globales protegidos al perfil activo
            global_protected = [p.get("term") for p in c6_result.get("protected_globals_json", []) if p.get("term")]
            if global_protected and profile_dict:
                existing_pt = set(profile_dict.get("protected_terms", []))
                new_global = [t for t in global_protected if t not in existing_pt]
                if new_global:
                    profile_dict["protected_terms"] = list(existing_pt) + new_global
                    logger.info(f"[Etapa C.6] {len(new_global)} términos globales protegidos añadidos al perfil")
            logger.info(f"[Etapa C.6] Contexto global generado: register={c6_result.get('dominant_register')}")
        except Exception as _c6_err:
            logger.warning(f"[Etapa C.6] Error no bloqueante: {_c6_err}")

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

        # ── Mapa de metadata estructural por ubicación (B.5 + B.7) ──
        # Fase 3/5: antes los parámetros block_meta/page_no de build_user_prompt
        # NUNCA se pasaban — toda la metadata de B.5 moría en la BD sin llegar
        # a un solo prompt. Este mapa la conecta de verdad.
        block_meta_map: dict[str, dict] = {}
        try:
            _meta_rows = db.execute(
                select(Block)
                .join(Page, Block.page_id == Page.id)
                .where(Page.doc_id == doc_id, Block.docx_location.isnot(None))
            ).scalars().all()
            for _b in _meta_rows:
                block_meta_map[_b.docx_location] = {
                    "style_name": _b.style_name,
                    "style_level": _b.style_level,
                    "list_id": _b.list_id,
                    "list_position": _b.list_position,
                    "list_total": _b.list_total,
                    "list_format_type": _b.list_format_type,
                    "list_level": _b.list_level,
                    "table_id": _b.table_id,
                    "row_index": _b.row_index,
                    "column_index": _b.column_index,
                    "row_total": _b.row_total,
                    "col_total": _b.col_total,
                    "table_cell_role": _b.table_cell_role,
                }
            # Página real por ubicación (Etapa B.7)
            for _loc, _pinfo in (_node_page_map or {}).items():
                meta = block_meta_map.setdefault(_loc, {})
                meta["page_start"] = _pinfo.get("page_start")
                meta["page_end"] = _pinfo.get("page_end")
                meta["crosses_page"] = _pinfo.get("crosses_page")
            if block_meta_map:
                logger.info(
                    f"[Etapa D] block_meta_map: {len(block_meta_map)} ubicaciones "
                    f"con metadata estructural/página para prompts"
                )
        except Exception as _bm_err:
            logger.warning(f"[Etapa D] No se pudo construir block_meta_map: {_bm_err}")

        # Recargar páginas después del commit de Etapa C
        pages = db.execute(
            select(Page).where(Page.doc_id == doc_id).order_by(Page.page_no)
        ).scalars().all()

        docx_patches = []
        usage_records = []

        # PDF nativo cuenta como DOCX-first: opera sobre el DOCX convertido
        if doc.original_format == "docx" or doc.docx_uri:
            # ── Ruta paralela (feature flag) ──
            if settings.parallel_correction_enabled:
                dispatched = _dispatch_parallel_correction(
                    db=db, doc_id=str(doc_id), doc=doc,
                    config=config, profile_dict=profile_dict,
                    analysis_result=analysis_result, job=job,
                    global_context_dict=global_context_dict,
                    block_meta_map=block_meta_map or None,
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

            logger.info("[Etapa D] Ruta 1: corrigiendo párrafos (doble pasada Plan v4)...")
            docx_patches, usage_records, _all_paragraphs, audit_log_entries = correct_docx_sync(
                doc_id=str(doc_id),
                docx_uri=docx_source_uri,
                config=config,
                profile=profile_dict,
                analysis_data=analysis_result,
                on_progress=_correction_progress,
                docx_bytes_cached=_docx_bytes,
                global_context=global_context_dict,
                grouped_locations=_grouped_locations or None,
                block_meta_map=block_meta_map or None,
                total_pages=doc.total_pages,
            )

            # Sprint 2: persistir mapa canónico paragraph_index → página
            try:
                _para_cls = {
                    pc["paragraph_index"]: pc
                    for pc in (analysis_result or {}).get("paragraph_classifications", [])
                }
                save_paragraph_locations_sync(
                    doc_id=str(doc_id),
                    all_paragraphs=_all_paragraphs,
                    para_classifications=_para_cls,
                    total_pages=doc.total_pages or 1,
                    db=db,
                )
            except Exception as _e:
                logger.warning(f"[Etapa D] paragraph_locations no guardadas (no bloqueante): {_e}")

            for record in usage_records:
                db.add(LlmUsage(doc_id=doc_id, **record))

            # Plan v4: persistir audit log entries (RAW request/response)
            if audit_log_entries:
                for entry in audit_log_entries:
                    db.add(LlmAuditLog(
                        doc_id=doc_id,
                        paragraph_index=entry.get("paragraph_index"),
                        location=entry.get("location"),
                        pass_number=entry.get("pass_number", 1),
                        call_purpose=entry.get("call_purpose", "mechanical_correction"),
                        model_used=entry.get("model_used"),
                        request_payload=entry.get("request_payload"),
                        response_payload=entry.get("response_payload"),
                        prompt_tokens=entry.get("prompt_tokens"),
                        completion_tokens=entry.get("completion_tokens"),
                        total_tokens=entry.get("total_tokens"),
                        latency_ms=entry.get("latency_ms"),
                        error_text=entry.get("error_text"),
                    ))
                logger.info(f"[Etapa D] {len(audit_log_entries)} entradas de audit log guardadas")

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
        # ETAPA D.5: PASADA GRUPAL (Nivel 2/3)
        # Corrige listas/tablas detectadas en B.5 en una sola llamada
        # por grupo. Los patches grupales tienen prioridad sobre los
        # individuales en _apply_docx_patches.
        # =============================================
        try:
            from app.services.correction import correct_groups_for_doc_sync
            group_patches, group_usage = correct_groups_for_doc_sync(
                doc_id=doc_id,
                session=db,
                profile=profile_dict,
                global_context=global_context_dict,
            )
            if group_patches:
                docx_patches.extend(group_patches)
                for r in group_usage:
                    db.add(LlmUsage(doc_id=doc_id, **r))
                db.commit()
                logger.info(
                    f"[Etapa D.5] Pasada grupal: +{len(group_patches)} patches"
                )
        except Exception as e:
            logger.warning(
                f"[Etapa D.5] Pasada grupal falló (no bloqueante): {e}"
            )

        # =============================================
        # PERSISTIR PATCHES → PENDING_REVIEW
        # =============================================
        # Guardar patches en MinIO para uso en Etapa E posterior
        patches_key = f"docx/{doc_id}/patches_docx.json"
        minio_client.upload_file(
            patches_key,
            json.dumps(docx_patches, ensure_ascii=False, indent=2, default=str).encode("utf-8"),
            content_type="application/json",
        )

        _persist_patches(db, str(doc_id), docx_patches)
        _run_candidate_render(db, str(doc_id))

        _complete_job(db, job)
        logger.info(f"=== PIPELINE COMPLETADO (candidate_ready): {doc.filename} ===")

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
    global_context_key: str | None = None,
    context_seed_window: list | None = None,
    grouped_indexes: list[int] | None = None,
    block_meta_key: str | None = None,
) -> str:
    """
    Tarea Celery: Pass 2 (LLM) para un batch de párrafos [start_para..end_para].
    Descarga datos de MinIO, corre LLM secuencial dentro del batch, guarda resultado.

    Args:
        grouped_indexes: H3 — índices de párrafos que pertenecen a un
            ElementGroup (lista/tabla); se omiten aquí porque la pasada
            grupal D.5 los procesa en bloque.

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

        # Plan v4: cargar contexto global para doble pasada
        global_context_dict: dict | None = None
        if global_context_key:
            try:
                global_context_dict = json.loads(
                    minio_client.download_file(global_context_key).decode("utf-8")
                )
            except Exception as gc_err:
                logger.warning(
                    f"[correct_batch_llm] No se pudo cargar global_context ({global_context_key}): {gc_err}"
                )

        profile = json.loads(profile_json) if profile_json else None
        system_prompt = build_system_prompt() if profile else None
        max_expansion = profile.get("max_expansion_ratio", 1.15) if profile else 1.15
        sections = analysis_data.get("sections", [])
        para_classifications = {
            pc["paragraph_index"]: pc
            for pc in analysis_data.get("paragraph_classifications", [])
        }

        # S1: Extraer term_registry del analysis_data para proteger términos en LT/LLM
        term_registry_list = analysis_data.get("terms", [])

        # Fase 3/5: metadata estructural + página real por ubicación
        block_meta_map: dict | None = None
        if block_meta_key:
            try:
                block_meta_map = json.loads(
                    minio_client.download_file(block_meta_key).decode("utf-8")
                )
            except Exception as bm_err:
                logger.warning(
                    f"[correct_batch_llm] No se pudo cargar block_meta ({block_meta_key}): {bm_err}"
                )

        # LLM secuencial para este batch — Plan v4: doble pasada activada
        patches, usage_records, last_corrected_text, audit_log_entries = correct_batch_with_llm_sync(
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
            context_seed_window=context_seed_window,
            global_context=global_context_dict,
            term_registry=term_registry_list,
            grouped_paragraph_indexes=set(grouped_indexes) if grouped_indexes else None,
            block_meta_map=block_meta_map,
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

        # Plan v4: persistir audit log entries (RAW payloads de ambas pasadas)
        p2_count = 0
        for entry in audit_log_entries:
            try:
                db.add(LlmAuditLog(
                    doc_id=doc_id,
                    paragraph_index=entry.get("paragraph_index"),
                    location=entry.get("location"),
                    pass_number=entry.get("pass_number", 1),
                    call_purpose=entry.get("call_purpose", "mechanical_correction"),
                    model_used=entry.get("model_used"),
                    request_payload=entry.get("request_payload"),
                    response_payload=entry.get("response_payload"),
                    prompt_tokens=entry.get("prompt_tokens"),
                    completion_tokens=entry.get("completion_tokens"),
                    total_tokens=entry.get("total_tokens"),
                    latency_ms=entry.get("latency_ms"),
                    error_text=entry.get("error_text"),
                ))
                if entry.get("pass_number") == 2:
                    p2_count += 1
            except Exception as ae:
                logger.warning(f"[correct_batch_llm] Error guardando audit log entry: {ae}")
        db.commit()

        logger.info(
            f"[correct_batch_llm] Batch {batch_index} completado: "
            f"{len(patches)} parches, {p2_count} auditorías P2 → {result_key}"
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
    global_context_key: str | None = None,
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

        # =============================================
        # ETAPA D.5 (ruta paralela): PASADA GRUPAL
        # H3 (Fase 0): antes la ruta paralela NUNCA ejecutaba la corrección
        # grupal de listas/tablas — toda la conciencia estructural de B.5
        # desaparecía cuando parallel_correction_enabled estaba activo.
        # =============================================
        try:
            from app.services.correction import correct_groups_for_doc_sync
            _profile_d5 = json.loads(profile_json) if profile_json else None
            _gc_d5: dict | None = None
            if global_context_key:
                try:
                    _gc_d5 = json.loads(
                        minio_client.download_file(global_context_key).decode("utf-8")
                    )
                except Exception:
                    pass
            group_patches, group_usage = correct_groups_for_doc_sync(
                doc_id=doc_id,
                session=db,
                profile=_profile_d5,
                global_context=_gc_d5,
            )
            if group_patches:
                all_patches.extend(group_patches)
                for r in group_usage:
                    db.add(LlmUsage(doc_id=doc_id, **r))
                db.commit()
                logger.info(
                    f"[assemble] Etapa D.5 grupal: +{len(group_patches)} patches"
                )
        except Exception as e:
            logger.warning(f"[assemble] Pasada grupal D.5 falló (no bloqueante): {e}")

        # Ordenar patches por paragraph_index (garantiza orden DOCX).
        # Los grupales tienen paragraph_index=None → van al final; el orden
        # real de aplicación lo resuelve el renderer (grupos primero).
        all_patches.sort(
            key=lambda p: (
                p.get("paragraph_index") is None,
                p.get("paragraph_index") or 0,
            )
        )

        # Guardar patches consolidados en MinIO (default=str: block_id/group_id UUID)
        patch_key = f"docx/{doc_id}/patches_docx.json"
        minio_client.upload_file(
            patch_key,
            json.dumps(all_patches, ensure_ascii=False, indent=2, default=str).encode("utf-8"),
            content_type="application/json",
        )

        # Persistir patches en BD y renderizar candidato
        _persist_patches(db, doc_id, all_patches)
        _run_candidate_render(db, doc_id)

        if job:
            _complete_job(db, job)

        logger.info(f"=== [assemble] PIPELINE PARALELO COMPLETADO (candidate_ready): {doc_id} ===")

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


# =====================================================================
# TAREA CELERY: RENDERIZADO POST-REVISIÓN HUMANA
# =====================================================================

@celery_app.task(bind=True, max_retries=2, name="tasks_pipeline.render_approved_patches")
def render_approved_patches(self, doc_id: str, apply_mode: str = "accepted_and_auto"):
    """
    Etapa E separada: renderiza solo las correcciones aprobadas.
    Se lanza desde el endpoint POST /documents/{id}/finalize
    después de que el usuario revise las correcciones.
    """
    db = _get_sync_session()
    job = None
    try:
        doc = db.execute(select(Document).where(Document.id == doc_id)).scalar_one()

        if doc.status not in ("pending_review", "candidate_ready"):
            logger.warning(
                f"[render_approved] Doc {doc_id} no está en candidate_ready/pending_review "
                f"(status={doc.status}), abortando"
            )
            return

        job = _create_job(db, doc_id, "render_approved", self.request.id)

        logger.info(f"=== RENDERIZADO POST-REVISIÓN: {doc.filename} (mode={apply_mode}) ===")

        # Re-cachear DOCX si no está en Redis
        try:
            _rcache = _redis.Redis.from_url(settings.redis_url)
            _docx_cache_key = f"docx_cache:{doc_id}"
            cached = _rcache.get(_docx_cache_key)
            if not cached:
                _docx_bytes = minio_client.download_file(doc.docx_uri or doc.source_uri)
                _rcache.setex(_docx_cache_key, 3600, _docx_bytes)
                logger.info(f"[render_approved] DOCX re-cacheado ({len(_docx_bytes)} bytes)")
        except Exception as e:
            logger.warning(f"[render_approved] Cache error: {e}")

        _run_stage_e(db, doc_id, apply_mode=apply_mode)

        _complete_job(db, job)
        logger.info(f"=== RENDERIZADO COMPLETADO: {doc.filename} ===")

    except Exception as e:
        logger.exception(f"[render_approved] Error: {e}")
        try:
            db.rollback()
        except Exception:
            pass
        if job:
            _complete_job(db, job, error=str(e))
        try:
            _update_document_status(db, doc_id, "failed", error_message=str(e))
            db.execute(
                update(Document).where(Document.id == doc_id).values(
                    processing_completed_at=datetime.now(timezone.utc),
                    progress_message="Error en renderizado post-revisión",
                    heartbeat_at=datetime.now(timezone.utc),
                )
            )
            db.commit()
        except Exception:
            pass
        self.retry(exc=e, countdown=30)

    finally:
        db.close()
        # Limpiar cache Redis
        try:
            _rcache = _redis.Redis.from_url(settings.redis_url)
            _rcache.delete(f"docx_cache:{doc_id}")
        except Exception:
            pass


# =====================================================================
# TAREA CELERY: RECORRECCIÓN IA INDIVIDUAL
# =====================================================================

@celery_app.task(bind=True, max_retries=1, name="tasks_pipeline.recorrect_single_patch")
def recorrect_single_patch(self, doc_id: str, patch_id: str, feedback: str):
    """
    Recorrige un patch individual usando feedback del usuario.
    """
    db = _get_sync_session()
    try:
        doc = db.execute(select(Document).where(Document.id == doc_id)).scalar_one()
        patch = db.execute(select(Patch).where(Patch.id == patch_id)).scalar_one_or_none()

        if not patch:
            logger.warning(f"[recorrect] Patch {patch_id} no encontrado")
            return

        patch.recorrection_count = (patch.recorrection_count or 0) + 1
        patch.recorrection_note = feedback

        profile_dict = None
        try:
            profile = db.execute(
                select(DocumentProfile).where(DocumentProfile.doc_id == doc_id)
            ).scalar_one_or_none()
            if profile:
                profile_dict = {
                    "register": profile.register,
                    "intervention_level": profile.intervention_level,
                    "audience_type": profile.audience_type,
                    "audience_expertise": getattr(profile, "audience_expertise", "general"),
                    "tone": profile.tone,
                    "preserve_author_voice": getattr(profile, "preserve_author_voice", False),
                    "max_rewrite_ratio": getattr(profile, "max_rewrite_ratio", 0.5),
                    "max_expansion_ratio": getattr(profile, "max_expansion_ratio", 1.1),
                    "style_priorities": profile.style_priorities or [],
                    "protected_terms": profile.protected_terms or [],
                    "forbidden_changes": getattr(profile, "forbidden_changes", []) or [],
                    "lt_disabled_rules": getattr(profile, "lt_disabled_rules", []) or [],
                    "register_constraints": getattr(profile, "register_constraints", None) or [],
                    "idiolect_protections": getattr(profile, "idiolect_protections", None) or [],
                    "prompt_blocks": getattr(profile, "prompt_blocks", None),
                }
        except Exception:
            pass

        # Fase 0: este bloque importaba clases INEXISTENTES (OpenAIStyleCorrector,
        # PromptBuilder) — toda recorrección moría con ImportError. Reescrito
        # sobre las funciones reales del módulo.
        from app.utils.openai_client import openai_client as _llm_client
        from app.services.prompt_builder import build_system_prompt, build_user_prompt
        original_text = patch.original_text

        try:
            if profile_dict:
                from app.services.llm_schemas import INDIVIDUAL_CORRECTION_SCHEMA
                system_prompt = build_system_prompt()
                user_prompt = build_user_prompt(
                    text=original_text,
                    profile=profile_dict,
                    paragraph_index=patch.paragraph_index or 0,
                )
                # Inyectar feedback al user prompt
                user_prompt += (
                    f"\n\nFEEDBACK DEL USUARIO sobre la corrección anterior:\n"
                    f'"{feedback}"\n'
                    f"Texto corregido anterior: \"{patch.corrected_text}\"\n"
                    f"Corrige nuevamente considerando este feedback."
                )
                data, usage = _llm_client.correct_with_profile(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    max_length=int(len(original_text) * 1.5),
                    response_schema=INDIVIDUAL_CORRECTION_SCHEMA,
                    schema_name="recorreccion",
                )
            else:
                # Fallback: correct_text_style con contexto de feedback
                feedback_text = (
                    f"{original_text}\n\n"
                    f"[FEEDBACK del usuario: {feedback}. "
                    f"Corrección anterior: {patch.corrected_text}]"
                )
                corrected, usage = _llm_client.correct_text_style(
                    original_text=feedback_text,
                    context_blocks=[],
                )
                data = {"corrected_text": corrected} if corrected else None

            if data and data.get("corrected_text"):
                new_corrected = data["corrected_text"]
                if new_corrected and len(new_corrected) <= len(original_text) * 2.2:
                    patch.corrected_text = new_corrected
                    patch.review_status = "pending"
                    patch.decision_source = "ai_recorrection"
                    patch.explanation = data.get("explanation", f"Recorrección #{patch.recorrection_count}")
                    patch.model_used = settings.openai_model
                    logger.info(f"[recorrect] Patch {patch_id} recorregido exitosamente")

        except Exception as llm_err:
            logger.error(f"[recorrect] Error LLM para {patch_id}: {llm_err}")
            patch.review_reason = f"Error en recorrección: {str(llm_err)[:200]}"

        db.commit()

    except Exception as e:
        logger.exception(f"[recorrect] Error: {e}")
        try:
            db.rollback()
        except Exception:
            pass
        self.retry(exc=e, countdown=10)

    finally:
        db.close()


@celery_app.task(bind=True, max_retries=1, name="tasks_pipeline.rerender_candidate_preview")
def rerender_candidate_preview(self, doc_id: str):
    """
    Re-renderiza el preview candidato con el estado actual de patches.
    Usa edited_text donde disponible. Excluye patches rechazados.
    No cambia el status del documento.
    """
    import json as _json
    db = _get_sync_session()
    try:
        doc = db.execute(select(Document).where(Document.id == doc_id)).scalar_one()

        # Cargar patches no rechazados con edited_text si disponible
        all_patch_rows = db.execute(
            select(Patch).join(Block).join(Page)
            .where(
                Page.doc_id == doc_id,
                Patch.review_status.notin_(("rejected", "gate_rejected")),
            )
            .order_by(Patch.paragraph_index)
        ).scalars().all()

        if not all_patch_rows:
            logger.info(f"[Rerender] Sin patches para {doc_id}, nada que re-renderizar")
            return

        # H1: identidad por location (BD) con fallback a paragraph_index.
        def _rr_key(p) -> str:
            if p.location:
                return f"loc:{p.location}"
            return f"idx:{p.paragraph_index if p.paragraph_index is not None else -1}"

        para_patch_ids: dict[str, list[str]] = {}
        for p in all_patch_rows:
            para_patch_ids.setdefault(_rr_key(p), []).append(str(p.id))

        # Deduplicar por identidad y aplicar edited_text si existe
        seen: set[str] = set()
        docx_patches: list[dict] = []
        for p in all_patch_rows:
            key = _rr_key(p)
            if key in seen:
                continue
            seen.add(key)
            final_text = (
                p.edited_text
                if (hasattr(p, "edited_text") and p.edited_text)
                else p.corrected_text
            )
            docx_patches.append({
                "patch_ids": para_patch_ids.get(key, []),
                "paragraph_index": p.paragraph_index if p.paragraph_index is not None else 0,
                "location": p.location or "",
                "original_text": p.original_text,
                "corrected_text": final_text,
                "source": p.source,
                "review_status": p.review_status,
                "changes": p.operations_json or [],
                "category": p.category,
                "severity": p.severity,
                "explanation": p.explanation,
                "confidence": p.confidence,
                "group_id": str(p.group_id) if p.group_id else None,
                "group_call_index": p.group_call_index,
                "structural_role": p.structural_role,
            })

        # Fallback legacy: cargar locations desde patches_docx.json
        missing_loc = [dp for dp in docx_patches if not dp["location"]]
        if missing_loc:
            try:
                patch_key = f"docx/{doc_id}/patches_docx.json"
                if minio_client.file_exists(patch_key):
                    stored_patches = _json.loads(
                        minio_client.download_file(patch_key).decode("utf-8")
                    )
                    location_index: dict[tuple, str] = {}
                    for sp in stored_patches:
                        key = (sp.get("paragraph_index", 0), sp.get("original_text", "")[:50])
                        location_index[key] = sp.get("location", "")
                    for dp in missing_loc:
                        key = (dp["paragraph_index"], dp["original_text"][:50])
                        dp["location"] = location_index.get(key, "")
            except Exception as loc_err:
                logger.warning(f"[Rerender] Error cargando locations: {loc_err}")

        logger.info(
            f"[Rerender] {len(docx_patches)} patches → re-renderizando candidato para {doc_id}"
        )

        _rr_docx_uri = doc.docx_uri or doc.source_uri
        _docx_bytes = _get_cached_docx_bytes(str(doc_id), _rr_docx_uri)
        render_docx_first_sync(
            doc_id=str(doc_id),
            docx_uri=_rr_docx_uri,
            filename=doc.filename,
            all_patches=docx_patches,
            docx_bytes_cached=_docx_bytes,
            apply_mode="all",
            render_mode="candidate",
        )

        logger.info(f"[Rerender] Preview candidato actualizado para {doc_id}")

    except Exception as e:
        logger.exception(f"[Rerender] Error: {e}")
        try:
            db.rollback()
        except Exception:
            pass
        self.retry(exc=e, countdown=5)

    finally:
        db.close()


# =====================================================================
# TAREA CELERY: CORRECCIÓN MACRO (S5 — opt-in)
# =====================================================================

@celery_app.task(bind=True, max_retries=2, name="tasks_pipeline.correct_macro_pass")
def correct_macro_pass(self, doc_id: str):
    """
    Pase de corrección macro post-merge (S5).
    Solo activo cuando document_profile.macro_correction_level != 'none'.
    """
    from app.services.macro_correction import run_macro_pass_sync
    from app.schemas.style_profile import StyleProfileResponse

    db = _get_sync_session()
    try:
        doc = db.execute(select(Document).where(Document.id == doc_id)).scalar_one()

        if doc.status not in ("candidate_ready", "correcting"):
            logger.warning(
                f"[macro_pass] Doc {doc_id} status={doc.status}, abortando"
            )
            return

        profile_obj = db.execute(
            select(DocumentProfile).where(DocumentProfile.doc_id == doc_id)
        ).scalar_one_or_none()

        if not profile_obj:
            logger.warning(f"[macro_pass] Sin perfil para {doc_id}")
            return

        profile_dict = StyleProfileResponse.model_validate(profile_obj).model_dump()
        macro_level = profile_dict.get("macro_correction_level", "none")
        if macro_level == "none":
            logger.info(f"[macro_pass] macro_correction_level=none, omitiendo")
            return

        logger.info(f"=== PASE MACRO: {doc.filename} (nivel={macro_level}) ===")

        patch_key = f"docx/{doc_id}/patches_docx.json"
        existing_patches = json.loads(minio_client.download_file(patch_key).decode("utf-8"))

        all_paragraphs_key = f"correction/{doc_id}/all_paragraphs.json"
        all_paragraphs = [
            tuple(p)
            for p in json.loads(minio_client.download_file(all_paragraphs_key).decode("utf-8"))
        ]

        analysis_data: dict = {}
        try:
            analysis_data = json.loads(
                minio_client.download_file(f"correction/{doc_id}/analysis.json").decode("utf-8")
            )
        except Exception:
            pass

        global_context_dict: dict | None = None
        try:
            global_context_dict = json.loads(
                minio_client.download_file(f"correction/{doc_id}/global_context.json").decode("utf-8")
            )
        except Exception:
            pass

        corrected_texts: dict[int, str] = {i: p[0] for i, p in enumerate(all_paragraphs)}
        for patch in existing_patches:
            pidx = patch.get("paragraph_index")
            if pidx is not None:
                corrected_texts[pidx] = patch.get("corrected_text", corrected_texts.get(pidx, ""))

        macro_patches, usage_records = run_macro_pass_sync(
            doc_id=doc_id,
            all_paragraphs=all_paragraphs,
            corrected_texts=corrected_texts,
            sections=analysis_data.get("sections", []),
            global_context=global_context_dict,
            profile=profile_dict,
            level=macro_level,
        )

        if not macro_patches:
            logger.info(f"[macro_pass] Sin correcciones macro para {doc_id}")
            return

        _persist_patches(db, doc_id, macro_patches)

        all_patches_updated = existing_patches + macro_patches
        all_patches_updated.sort(key=lambda p: p.get("paragraph_index", 0))
        minio_client.upload_file(
            patch_key,
            json.dumps(all_patches_updated, ensure_ascii=False, indent=2).encode("utf-8"),
            content_type="application/json",
        )

        for record in usage_records:
            record_data = {k: v for k, v in record.items() if k != "doc_id"}
            db.add(LlmUsage(doc_id=doc_id, **record_data))
        db.commit()

        _run_candidate_render(db, doc_id)

        logger.info(
            f"=== PASE MACRO COMPLETADO: {doc.filename} — "
            f"{len(macro_patches)} patches macro ==="
        )

    except Exception as e:
        logger.exception(f"[macro_pass] Error para {doc_id}: {e}")
        try:
            db.rollback()
        except Exception:
            pass
        self.retry(exc=e, countdown=30)

    finally:
        db.close()
