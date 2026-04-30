# PIPELINE-REFACTOR.md — Instrucciones de Implementación para Claude Code

> **CONTEXTO**: Este documento contiene instrucciones exactas para reestructurar el pipeline de STYLIA.
> El sistema se detiene al procesar varios libros simultáneamente y es extremadamente lento.
> Ejecutar las 3 fases en orden. Cada fase es independiente y verificable.
> Después de cada fase: `docker-compose up --build` y probar con 2-3 documentos.

---

## DIAGNÓSTICO RAÍZ (para contexto del implementador)

### Por qué se detiene con múltiples documentos:
1. `backend/app/workers/tasks_pipeline.py:49` — Engine DB síncrono es MODULE-LEVEL con `pool_size=5, max_overflow=10`. Celery usa prefork: los procesos hijos heredan file descriptors TCP del engine padre, causando corrupción de conexiones. Con `concurrency=8`, 8 procesos comparten 5 conexiones.
2. `backend/app/workers/tasks_pipeline.py:64,94,102,117,127` — Cada helper hace `db.commit()` individual. Un doc de 500 páginas genera ~2000+ commits. Con 8 docs simultáneos = contención masiva de locks.
3. No hay colas separadas en Celery. Los `correct_batch_llm` (cola por defecto) compiten con `process_document_pipeline` por los mismos workers. El chord callback puede quedar en espera indefinida si todos los workers están ocupados con pipelines.
4. Un solo container worker sin memory limits ni health checks. Un doc grande puede OOM silenciosamente.

### Por qué es lento:
1. DOCX se descarga de MinIO 3-4 veces: Stage A (ingestion.py:86), Stage C (analysis.py:537), Stage D (correction.py:462), Stage E (rendering.py:335).
2. `_find_best_block` en tasks_pipeline.py:208-260 usa `SequenceMatcher` que es O(n*m) por comparación. Para 2000 patches es muy lento.
3. Un solo LanguageTool container con `Java_Xmx=2g` atendiendo 8+ threads paralelos de múltiples documentos.
4. Commits a DB en cada actualización de progreso.

---

## FASE 1: ESTABILIDAD (multi-documento sin crash)

### CAMBIO 1.1: Connection Pool per-process

**Archivo**: `backend/app/workers/tasks_pipeline.py`

**ELIMINAR** las líneas 48-50 (el bloque completo):
```python
# Motor síncrono para Celery (no usa async)
sync_engine = create_engine(settings.database_url_sync, pool_size=5, max_overflow=10)
SyncSession = sessionmaker(bind=sync_engine)
```

**REEMPLAZAR CON** (en la misma posición, después de `logger = logging.getLogger(__name__)`):
```python
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
```

**BUSCAR Y REEMPLAZAR** en todo el archivo `tasks_pipeline.py` — hay 3 ocurrencias de `SyncSession()`:

1. Línea ~537 (dentro de `process_document_pipeline`):
   - BUSCAR: `db = SyncSession()`
   - REEMPLAZAR: `db = _get_sync_session()`

2. Línea ~918 (dentro de `correct_batch_llm`):
   - BUSCAR: `db = SyncSession()`
   - REEMPLAZAR: `db = _get_sync_session()`

3. Línea ~1041 (dentro de `assemble_correction_results`):
   - BUSCAR: `db = SyncSession()`
   - REEMPLAZAR: `db = _get_sync_session()`

---

### CAMBIO 1.2: Throttle de commits en helpers

**Archivo**: `backend/app/workers/tasks_pipeline.py`

**REEMPLAZAR** la función `_update_document_status` (líneas 57-64):
```python
def _update_document_status(db: Session, doc_id: str, status: str, **kwargs) -> None:
    """Helper para actualizar estado del documento."""
    values = {"status": status, "updated_at": datetime.now(timezone.utc)}
    values.update(kwargs)
    db.execute(
        update(Document).where(Document.id == doc_id).values(**values)
    )
    db.commit()
```
**CON**:
```python
def _update_document_status(db: Session, doc_id: str, status: str, **kwargs) -> None:
    """Helper para actualizar estado del documento. Commit inmediato porque cambia status."""
    values = {"status": status, "updated_at": datetime.now(timezone.utc)}
    values.update(kwargs)
    db.execute(
        update(Document).where(Document.id == doc_id).values(**values)
    )
    db.commit()
```
(Este se queda igual — los cambios de status SÍ necesitan commit inmediato para que el frontend los vea via polling.)

**REEMPLAZAR** la función `_update_progress` (líneas 67-94) COMPLETA:
```python
def _update_progress(
    db: Session,
    doc_id: str,
    stage: str,
    message: str,
    current: int | None = None,
    total: int | None = None,
    start_stage: bool = False,
) -> None:
    """Actualiza progreso granular y heartbeat del documento."""
    now = datetime.now(timezone.utc)
    values = {
        "progress_stage": stage,
        "progress_message": message[:200],
        "heartbeat_at": now,
        "updated_at": now,
    }
    if current is not None:
        values["progress_stage_current"] = current
    if total is not None:
        values["progress_stage_total"] = total
    if start_stage:
        values["stage_started_at"] = now
        values["progress_stage_current"] = 0
    db.execute(
        update(Document).where(Document.id == doc_id).values(**values)
    )
    db.commit()
```
**CON**:
```python
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
```

**REEMPLAZAR** la función `_save_stage_timing` (líneas 97-102):
```python
def _save_stage_timing(db: Session, doc_id: str, stage_timings: dict) -> None:
    """Persiste los timings acumulados de etapas en el documento."""
    db.execute(
        update(Document).where(Document.id == doc_id).values(stage_timings=stage_timings)
    )
    db.commit()
```
**CON**:
```python
def _save_stage_timing(db: Session, doc_id: str, stage_timings: dict) -> None:
    """Persiste los timings acumulados de etapas en el documento (sin commit propio)."""
    db.execute(
        update(Document).where(Document.id == doc_id).values(stage_timings=stage_timings)
    )
    # No commit aquí — se hace al final de la etapa
```

**REEMPLAZAR** la función `_cleanup_progress` (líneas 105-117):
```python
def _cleanup_progress(db: Session, doc_id: str) -> None:
    """Limpia campos de progreso granular al completar el documento."""
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
    db.commit()
```
**CON**:
```python
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
```

**REEMPLAZAR** la función `_update_page_status` (líneas 120-127):
```python
def _update_page_status(db: Session, page_id: str, status: str, **kwargs) -> None:
    """Helper para actualizar estado de una página."""
    values = {"status": status, "updated_at": datetime.now(timezone.utc)}
    values.update(kwargs)
    db.execute(
        update(Page).where(Page.id == page_id).values(**values)
    )
    db.commit()
```
**CON**:
```python
def _update_page_status(db: Session, page_id: str, status: str, **kwargs) -> None:
    """Helper para actualizar estado de una página (sin commit propio)."""
    values = {"status": status, "updated_at": datetime.now(timezone.utc)}
    values.update(kwargs)
    db.execute(
        update(Page).where(Page.id == page_id).values(**values)
    )
    # No commit aquí — se hace batch al final del loop de páginas
```

**IMPORTANTE**: Después de quitar los commits de estos helpers, hay que asegurar que los commits se hagan en los puntos correctos del pipeline. Revisar `process_document_pipeline` y agregar `db.commit()` explícitos donde ya no se hacen:

- Después del loop de extracción de Stage B (línea ~669 ya tiene `db.commit()` — OK)
- Después del loop de páginas "corrected" en `_run_stage_e` (línea ~330 ya tiene `db.commit()` — OK)
- Después del loop de páginas "rendered" en `_run_stage_e` — actualmente NO hay commit después de este loop. **AGREGAR** `db.commit()` después del loop de `_update_page_status(db, page.id, "rendered")` en `_run_stage_e`, justo antes de la línea `elapsed_e = round(time.time() - t0_e, 1)`:

En `_run_stage_e`, BUSCAR:
```python
    # Marcar páginas como renderizadas
    for page in pages:
        if page.status != "failed":
            _update_page_status(db, page.id, "rendered")

    elapsed_e = round(time.time() - t0_e, 1)
```
REEMPLAZAR CON:
```python
    # Marcar páginas como renderizadas
    for page in pages:
        if page.status != "failed":
            _update_page_status(db, page.id, "rendered")
    db.commit()

    elapsed_e = round(time.time() - t0_e, 1)
```

Y en `_run_stage_e`, después de `_update_page_status(db, page.id, "corrected")` loop, BUSCAR:
```python
    # Marcar páginas como corregidas
    for page in pages:
        if page.status != "failed":
            _update_page_status(db, page.id, "corrected")

    db.commit()
```
Esto ya tiene `db.commit()` después del loop — OK, no cambiar.

---

### CAMBIO 1.3: Task Routing — Colas separadas

**Archivo**: `backend/app/workers/celery_app.py`

**REEMPLAZAR** el archivo completo:
```python
"""
Configuración de Celery.
"""

from celery import Celery
from app.config import settings

celery_app = Celery(
    "stylecorrector",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    task_acks_late=True,
    worker_prefetch_multiplier=settings.celery_worker_prefetch_multiplier,
    task_reject_on_worker_lost=True,
    task_time_limit=settings.celery_task_time_limit,
    task_soft_time_limit=settings.celery_task_soft_time_limit,
    result_expires=settings.celery_result_expires,
)

# Auto-descubrir tareas en los módulos de workers
celery_app.autodiscover_tasks([
    "app.workers.tasks_pipeline",
])
```

**CON**:
```python
"""
Configuración de Celery con routing de colas.
Pipeline tasks → cola 'pipeline' (procesamiento pesado: LibreOffice, PyMuPDF, análisis).
Batch tasks → cola 'batch' (corrección LLM, I/O-bound).
"""

from celery import Celery
from app.config import settings

celery_app = Celery(
    "stylecorrector",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    task_acks_late=True,
    worker_prefetch_multiplier=settings.celery_worker_prefetch_multiplier,
    task_reject_on_worker_lost=True,
    task_time_limit=settings.celery_task_time_limit,
    task_soft_time_limit=settings.celery_task_soft_time_limit,
    result_expires=settings.celery_result_expires,
    # Routing: separar pipeline (pesado) de batch (LLM I/O)
    task_routes={
        "tasks_pipeline.process_document_pipeline": {"queue": "pipeline"},
        "tasks_pipeline.correct_batch_llm": {"queue": "batch"},
        "tasks_pipeline.assemble_correction_results": {"queue": "batch"},
    },
    task_default_queue="pipeline",
)

# Auto-descubrir tareas en los módulos de workers
celery_app.autodiscover_tasks([
    "app.workers.tasks_pipeline",
])
```

---

### CAMBIO 1.4: Docker Compose — Workers separados con limits y healthchecks

**Archivo**: `docker-compose.yml`

**BUSCAR** el bloque completo del servicio `worker` (líneas 130-152):
```yaml
  worker:
    build:
      context: ./backend
      dockerfile: Dockerfile
    env_file:
      - .env
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
      minio:
        condition: service_healthy
      languagetool:
        condition: service_healthy
    command: >
      celery -A app.workers.celery_app worker
      --loglevel=info
      --concurrency=${CELERY_WORKER_CONCURRENCY:-2}
      --max-tasks-per-child=${CELERY_MAX_TASKS_PER_CHILD:-20}
    volumes:
      - ./backend:/app
    restart: unless-stopped
```

**REEMPLAZAR CON**:
```yaml
  # Worker para tareas de pipeline (pesadas: LibreOffice, PyMuPDF, análisis, corrección secuencial)
  worker-pipeline:
    build:
      context: ./backend
      dockerfile: Dockerfile
    env_file:
      - .env
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
      minio:
        condition: service_healthy
      languagetool:
        condition: service_healthy
    command: >
      celery -A app.workers.celery_app worker
      --loglevel=info
      --concurrency=${CELERY_PIPELINE_CONCURRENCY:-4}
      --max-tasks-per-child=10
      --queues=pipeline
      --hostname=pipeline@%h
    volumes:
      - ./backend:/app
      - stylia_tmp:/tmp/stylia
    mem_limit: 4g
    memswap_limit: 4g
    healthcheck:
      test: ["CMD-SHELL", "celery -A app.workers.celery_app inspect ping -d pipeline@$$HOSTNAME 2>/dev/null || exit 1"]
      interval: 30s
      timeout: 15s
      retries: 3
      start_period: 30s
    restart: unless-stopped

  # Worker para tareas batch (LLM correction, I/O-bound)
  worker-batch:
    build:
      context: ./backend
      dockerfile: Dockerfile
    env_file:
      - .env
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
      minio:
        condition: service_healthy
    command: >
      celery -A app.workers.celery_app worker
      --loglevel=info
      --concurrency=${CELERY_BATCH_CONCURRENCY:-6}
      --max-tasks-per-child=50
      --queues=batch
      --hostname=batch@%h
    volumes:
      - ./backend:/app
    mem_limit: 2g
    memswap_limit: 2g
    healthcheck:
      test: ["CMD-SHELL", "celery -A app.workers.celery_app inspect ping -d batch@$$HOSTNAME 2>/dev/null || exit 1"]
      interval: 30s
      timeout: 15s
      retries: 3
      start_period: 30s
    restart: unless-stopped
```

**AGREGAR** al bloque `volumes:` al final del archivo (líneas 174-177):
```yaml
volumes:
  pgdata:
  miniodata:
  pgadmin_data:
  stylia_tmp:
```

**MODIFICAR** el servicio `postgres` — agregar `command` para aumentar max_connections. BUSCAR:
```yaml
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: stylecorrector
      POSTGRES_PASSWORD: changeme
      POSTGRES_DB: stylecorrector
    ports:
      - "5432:5432"
```
REEMPLAZAR CON:
```yaml
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: stylecorrector
      POSTGRES_PASSWORD: changeme
      POSTGRES_DB: stylecorrector
    command: postgres -c max_connections=200 -c shared_buffers=256MB
    ports:
      - "5432:5432"
```

---

### CAMBIO 1.5: Pool safety en async engine

**Archivo**: `backend/app/database.py`

**BUSCAR** (líneas 11-16):
```python
engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    pool_size=10,
    max_overflow=20,
)
```

**REEMPLAZAR CON**:
```python
engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    pool_recycle=1800,
)
```

---

### CAMBIO 1.6: Variables de entorno

**Archivo**: `.env`

**BUSCAR** (líneas 62-63):
```
CELERY_WORKER_CONCURRENCY=8
```

**REEMPLAZAR CON**:
```
# Concurrency por tipo de worker (docker-compose tiene 2 servicios separados)
CELERY_PIPELINE_CONCURRENCY=4
CELERY_BATCH_CONCURRENCY=6
```

**BUSCAR** (líneas 54-58):
```
PARALLEL_CORRECTION_ENABLED=true
PARALLEL_CORRECTION_BATCH_SIZE=150
PARALLEL_CORRECTION_MAX_BATCHES=8
PARALLEL_CORRECTION_LT_WORKERS=8
PARALLEL_CORRECTION_BOUNDARY_CHECK=true
```

**REEMPLAZAR CON**:
```
PARALLEL_CORRECTION_ENABLED=true
PARALLEL_CORRECTION_BATCH_SIZE=150
PARALLEL_CORRECTION_MAX_BATCHES=6
PARALLEL_CORRECTION_LT_WORKERS=4
PARALLEL_CORRECTION_BOUNDARY_CHECK=true
```

---

### VERIFICACIÓN FASE 1:
```bash
docker-compose up --build
```
Subir 3 documentos medianos (50-100 páginas) simultáneamente. Verificar en logs:
- `DB engine creado para PID XXXX` aparece por cada worker process (no repetido)
- No hay errores de "connection pool exhausted" ni "QueuePool limit"
- Los batch tasks aparecen con `[batch@...]` en logs, pipeline con `[pipeline@...]`
- Los 3 documentos llegan a `completed` sin colgarse

---

## FASE 2: PERFORMANCE (reducir tiempo de procesamiento)

### CAMBIO 2.1: Cache DOCX entre etapas via Redis

**Archivo**: `backend/app/workers/tasks_pipeline.py`

Agregar al inicio del archivo (después de los imports existentes, antes de `logger`):
```python
import redis as _redis
```

**En la función `process_document_pipeline`**, después de Stage A (después de la línea `stage_timings["A"] = round(time.time() - t0_a, 1)`), AGREGAR cache del DOCX:

BUSCAR:
```python
        _update_progress(db, doc_id, "converting", "Conversión completada", current=1, total=1)
        logger.info(f"[Etapa A] Completada: {total_pages} páginas creadas")
        stage_timings["A"] = round(time.time() - t0_a, 1)
        _save_stage_timing(db, doc_id, stage_timings)
```

AGREGAR DESPUÉS (antes de `# ETAPA B`):
```python
        # Cache DOCX bytes en Redis para evitar re-descargas en etapas C, D, E
        try:
            _rcache = _redis.Redis.from_url(settings.redis_url)
            _docx_cache_key = f"docx_cache:{doc_id}"
            _docx_bytes_cached = minio_client.download_file(doc.source_uri)
            _rcache.setex(_docx_cache_key, 7200, _docx_bytes_cached)  # TTL 2h
            logger.info(f"[Cache] DOCX cacheado en Redis ({len(_docx_bytes_cached)} bytes)")
        except Exception as _cache_err:
            logger.warning(f"[Cache] No se pudo cachear DOCX: {_cache_err}")
```

**Crear función helper** para obtener DOCX cacheado. Agregar cerca del inicio del archivo, después de `_get_sync_session`:

```python
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
```

**Ahora modificar los servicios para usar el cache.**

**Archivo**: `backend/app/services/analysis.py`

BUSCAR en `analyze_document_sync` (líneas 536-543):
```python
    # Descargar DOCX
    docx_bytes = minio_client.download_file(docx_uri)
    tmpfile = tempfile.mktemp(suffix=".docx")
    with open(tmpfile, "wb") as f:
        f.write(docx_bytes)
```

REEMPLAZAR CON:
```python
    # Descargar DOCX (con cache si disponible)
    if docx_bytes_cached is not None:
        docx_bytes = docx_bytes_cached
    else:
        docx_bytes = minio_client.download_file(docx_uri)
    tmpfile = tempfile.mktemp(suffix=".docx")
    with open(tmpfile, "wb") as f:
        f.write(docx_bytes)
```

Y CAMBIAR la firma de `analyze_document_sync` (línea 514):
```python
def analyze_document_sync(
    doc_id: str,
    docx_uri: str,
    profile: dict | None = None,
) -> dict:
```
A:
```python
def analyze_document_sync(
    doc_id: str,
    docx_uri: str,
    profile: dict | None = None,
    docx_bytes_cached: bytes | None = None,
) -> dict:
```

**Archivo**: `backend/app/services/correction.py`

BUSCAR en `correct_docx_sync` (líneas 461-468):
```python
    # Descargar DOCX
    docx_bytes = minio_client.download_file(docx_uri)
    tmpfile = tempfile.mktemp(suffix=".docx")
    with open(tmpfile, "wb") as f:
        f.write(docx_bytes)
```

REEMPLAZAR CON:
```python
    # Descargar DOCX (con cache si disponible)
    if docx_bytes_cached is not None:
        docx_bytes = docx_bytes_cached
    else:
        docx_bytes = minio_client.download_file(docx_uri)
    tmpfile = tempfile.mktemp(suffix=".docx")
    with open(tmpfile, "wb") as f:
        f.write(docx_bytes)
```

Y CAMBIAR la firma de `correct_docx_sync` (líneas 437-444):
```python
def correct_docx_sync(
    doc_id: str,
    docx_uri: str,
    config: dict,
    profile: dict | None = None,
    analysis_data: dict | None = None,
    on_progress: Callable[[int, int], None] | None = None,
) -> tuple[list[dict], list[dict]]:
```
A:
```python
def correct_docx_sync(
    doc_id: str,
    docx_uri: str,
    config: dict,
    profile: dict | None = None,
    analysis_data: dict | None = None,
    on_progress: Callable[[int, int], None] | None = None,
    docx_bytes_cached: bytes | None = None,
) -> tuple[list[dict], list[dict]]:
```

**Archivo**: `backend/app/services/rendering.py`

BUSCAR en `render_docx_first_sync` (líneas 333-335):
```python
        # Descargar DOCX original
        local_docx = str(Path(tmpdir) / filename)
        minio_client.download_file_to_path(docx_uri, local_docx)
```

REEMPLAZAR CON:
```python
        # Descargar DOCX original (con cache si disponible)
        local_docx = str(Path(tmpdir) / filename)
        if docx_bytes_cached is not None:
            with open(local_docx, "wb") as _f:
                _f.write(docx_bytes_cached)
        else:
            minio_client.download_file_to_path(docx_uri, local_docx)
```

Y CAMBIAR la firma de `render_docx_first_sync` (líneas 315-320):
```python
def render_docx_first_sync(
    doc_id: str,
    docx_uri: str,
    filename: str,
    all_patches: list[dict],
) -> dict:
```
A:
```python
def render_docx_first_sync(
    doc_id: str,
    docx_uri: str,
    filename: str,
    all_patches: list[dict],
    docx_bytes_cached: bytes | None = None,
) -> dict:
```

**Ahora actualizar las llamadas en `tasks_pipeline.py`** para pasar el cache:

En `process_document_pipeline`, BUSCAR la llamada a `analyze_document_sync` (línea ~704):
```python
        analysis_result = analyze_document_sync(
            doc_id=str(doc_id),
            docx_uri=doc.source_uri,
            profile=profile_dict,
        )
```
REEMPLAZAR CON:
```python
        _docx_bytes = _get_cached_docx_bytes(str(doc_id), doc.source_uri)
        analysis_result = analyze_document_sync(
            doc_id=str(doc_id),
            docx_uri=doc.source_uri,
            profile=profile_dict,
            docx_bytes_cached=_docx_bytes,
        )
```

BUSCAR la llamada a `correct_docx_sync` (línea ~822):
```python
            docx_patches, usage_records = correct_docx_sync(
                doc_id=str(doc_id),
                docx_uri=doc.source_uri,
                config=config,
                profile=profile_dict,
                analysis_data=analysis_result,
                on_progress=_correction_progress,
            )
```
REEMPLAZAR CON:
```python
            docx_patches, usage_records = correct_docx_sync(
                doc_id=str(doc_id),
                docx_uri=doc.source_uri,
                config=config,
                profile=profile_dict,
                analysis_data=analysis_result,
                on_progress=_correction_progress,
                docx_bytes_cached=_docx_bytes,
            )
```

BUSCAR la llamada a `render_docx_first_sync` dentro de `_run_stage_e` (línea ~334):
```python
    render_result = render_docx_first_sync(
        doc_id=str(doc_id),
        docx_uri=doc.source_uri,
        filename=doc.filename,
        all_patches=docx_patches,
    )
```
REEMPLAZAR CON:
```python
    _docx_bytes_for_render = _get_cached_docx_bytes(str(doc_id), doc.source_uri)
    render_result = render_docx_first_sync(
        doc_id=str(doc_id),
        docx_uri=doc.source_uri,
        filename=doc.filename,
        all_patches=docx_patches,
        docx_bytes_cached=_docx_bytes_for_render,
    )
```

También actualizar `_dispatch_parallel_correction` — BUSCAR (línea ~399):
```python
    docx_bytes = minio_client.download_file(doc.source_uri)
```
REEMPLAZAR CON:
```python
    docx_bytes = _get_cached_docx_bytes(str(doc_id), doc.source_uri)
```

**Limpiar cache en finally del pipeline**. En `process_document_pipeline`, BUSCAR el bloque `finally:` (línea ~887):
```python
    finally:
        db.close()
```
REEMPLAZAR CON:
```python
    finally:
        db.close()
        # Limpiar cache Redis
        try:
            _rcache = _redis.Redis.from_url(settings.redis_url)
            _rcache.delete(f"docx_cache:{doc_id}")
        except Exception:
            pass
```

---

### CAMBIO 2.2: Optimizar `_find_best_block` con índice por prefijo

**Archivo**: `backend/app/workers/tasks_pipeline.py`

BUSCAR el bloque dentro de `_run_stage_e` (líneas 190-260, la definición de `_find_best_block` y el código que lo precede):

```python
    # ── Construir índice de bloques por página para matching O(ventana) ──
    blocks_by_page: dict[int, list[tuple]] = {}
    all_blocks_flat: list[tuple] = []
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

        est_page = min(int(para_idx / max(total_paras, 1) * num_pages), num_pages - 1)
        search_window = 2
        best_block = None
        best_score = 0.0
        patch_snippet = norm_patch[:300]

        # Phase 1: search nearby pages
        for offset in range(-search_window, search_window + 1):
            pi = est_page + offset
            for block, norm_block in blocks_by_page.get(pi, []):
                if not norm_block:
                    continue
                score = SequenceMatcher(None, patch_snippet, norm_block[:300]).ratio()
                if score > best_score:
                    best_score = score
                    best_block = block
                if best_score > 0.9:
                    return best_block  # early exit

        # Phase 2: full scan if no good match nearby
        if best_score < 0.5:
            searched = set(range(max(0, est_page - search_window),
                                 min(num_pages, est_page + search_window + 1)))
            for pi in range(num_pages):
                if pi in searched:
                    continue
                for block, norm_block in blocks_by_page.get(pi, []):
                    if not norm_block:
                        continue
                    score = SequenceMatcher(None, patch_snippet, norm_block[:300]).ratio()
                    if score > best_score:
                        best_score = score
                        best_block = block
                    if best_score > 0.9:
                        return best_block

        if best_score < 0.3:
            if blocks_by_page.get(est_page):
                return blocks_by_page[est_page][0][0]
            return all_blocks_flat[0][0]
        return best_block
```

**REEMPLAZAR TODO ESE BLOQUE CON**:

```python
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
```

---

### CAMBIO 2.3: Escalar LanguageTool

**Archivo**: `docker-compose.yml`

**BUSCAR** el servicio languagetool (líneas 83-96):
```yaml
  languagetool:
    image: erikvl87/languagetool:latest
    environment:
      Java_Xms: 512m
      Java_Xmx: 2g
    ports:
      - "8010:8010"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8010/v2/languages"]
      interval: 20s
      timeout: 10s
      retries: 10
      start_period: 60s
    restart: unless-stopped
```

**REEMPLAZAR CON** (2 instancias como servicios separados + nginx LB):
```yaml
  languagetool-1:
    image: erikvl87/languagetool:latest
    environment:
      Java_Xms: 512m
      Java_Xmx: 2g
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8010/v2/languages"]
      interval: 20s
      timeout: 10s
      retries: 10
      start_period: 60s
    restart: unless-stopped

  languagetool-2:
    image: erikvl87/languagetool:latest
    environment:
      Java_Xms: 512m
      Java_Xmx: 2g
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8010/v2/languages"]
      interval: 20s
      timeout: 10s
      retries: 10
      start_period: 60s
    restart: unless-stopped

  languagetool:
    image: nginx:alpine
    volumes:
      - ./nginx-lt.conf:/etc/nginx/nginx.conf:ro
    ports:
      - "8010:8010"
    depends_on:
      languagetool-1:
        condition: service_healthy
      languagetool-2:
        condition: service_healthy
    restart: unless-stopped
```

**ACTUALIZAR** las dependencias de `backend` y `worker-pipeline` — cambiar:
```yaml
      languagetool:
        condition: service_healthy
```
A:
```yaml
      languagetool-1:
        condition: service_healthy
```
(Ya que ahora `languagetool` es nginx y no tiene healthcheck propio, depender de al menos una instancia real.)

**CREAR** nuevo archivo `nginx-lt.conf` en la raíz del proyecto:
```nginx
events {
    worker_connections 64;
}

http {
    upstream languagetool_backend {
        server languagetool-1:8010;
        server languagetool-2:8010;
    }

    server {
        listen 8010;

        location / {
            proxy_pass http://languagetool_backend;
            proxy_connect_timeout 10s;
            proxy_read_timeout 60s;
            proxy_send_timeout 30s;
        }
    }
}
```

---

### CAMBIO 2.4: Aumentar conexiones LT en httpx client

**Archivo**: `backend/app/services/correction.py`

BUSCAR (líneas 24-27):
```python
_lt_client = httpx.Client(
    limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
    timeout=httpx.Timeout(settings.lt_timeout),
)
```

REEMPLAZAR CON:
```python
_lt_client = httpx.Client(
    limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
    timeout=httpx.Timeout(settings.lt_timeout),
)
```

---

### VERIFICACIÓN FASE 2:
```bash
docker-compose up --build
```
Subir 1 documento de 200+ páginas. Comparar tiempo de procesamiento con el anterior. Verificar en logs:
- `[Cache] DOCX hit` aparece en Stages C, D, E (no se re-descarga)
- Stage E es significativamente más rápido (block matching usa fast path)
- LanguageTool responde via nginx (`languagetool:8010` sigue funcionando como antes)

---

## FASE 3: RESILIENCIA (retry por etapa, concurrency control)

### CAMBIO 3.1: Semáforo de concurrencia con Redis

**Archivo**: `backend/app/config.py`

BUSCAR (antes de la línea `model_config`):
```python
    # --- LibreOffice ---
    libreoffice_path: str = "soffice"
```

REEMPLAZAR CON:
```python
    # --- LibreOffice ---
    libreoffice_path: str = "soffice"

    # --- Concurrency control ---
    max_concurrent_pipelines: int = 4
```

**Archivo**: `backend/app/workers/tasks_pipeline.py`

Agregar funciones de semáforo después de `_get_cached_docx_bytes`:

```python
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
```

**En `process_document_pipeline`**, agregar al inicio del try block (después de `db = _get_sync_session()`, antes de cualquier query):

BUSCAR:
```python
    try:
        doc = db.execute(select(Document).where(Document.id == doc_id)).scalar_one()
        job = _create_job(db, doc_id, "full_pipeline", self.request.id)
```

REEMPLAZAR CON:
```python
    try:
        # Semáforo: limitar pipelines concurrentes
        if not _acquire_pipeline_slot(doc_id):
            logger.info(f"Pipeline {doc_id}: esperando slot (max {settings.max_concurrent_pipelines} concurrentes)")
            raise self.retry(countdown=15, max_retries=200)

        doc = db.execute(select(Document).where(Document.id == doc_id)).scalar_one()
        job = _create_job(db, doc_id, "full_pipeline", self.request.id)
```

**En el finally block**, liberar el slot. BUSCAR:
```python
    finally:
        db.close()
        # Limpiar cache Redis
        try:
            _rcache = _redis.Redis.from_url(settings.redis_url)
            _rcache.delete(f"docx_cache:{doc_id}")
        except Exception:
            pass
```

REEMPLAZAR CON:
```python
    finally:
        db.close()
        _release_pipeline_slot(doc_id)
        # Limpiar cache Redis
        try:
            _rcache = _redis.Redis.from_url(settings.redis_url)
            _rcache.delete(f"docx_cache:{doc_id}")
        except Exception:
            pass
```

También liberar en `assemble_correction_results` — en su finally block, BUSCAR:
```python
    finally:
        db.close()
```
REEMPLAZAR CON:
```python
    finally:
        db.close()
        _release_pipeline_slot(doc_id)
```

---

### CAMBIO 3.2: Rate limiter para OpenAI

**Archivo**: `backend/app/utils/openai_client.py`

BUSCAR (línea 1):
```python
"""
Cliente OpenAI para corrección de estilo con contexto.
Usa gpt-4o-mini para ser económico y eficiente.
"""

import json
import logging
from typing import Optional
```

REEMPLAZAR CON:
```python
"""
Cliente OpenAI para corrección de estilo con contexto.
Usa gpt-4o-mini para ser económico y eficiente.
"""

import json
import logging
import threading
from typing import Optional
```

BUSCAR la definición de `correct_with_profile` (línea ~170):
```python
        try:
            response = self._retry(self.client.chat.completions.create)(
```

AGREGAR un semáforo al inicio de la clase `OpenAIClient.__init__` — BUSCAR:
```python
        # Build tenacity retry decorator from config
        self._retry = retry(
```
AGREGAR ANTES:
```python
        # Semáforo: max 3 llamadas concurrentes a OpenAI por proceso
        self._semaphore = threading.Semaphore(3)

```

Y envolver ambos métodos de corrección. En `correct_text_style`, BUSCAR:
```python
        try:
            # Llamar a OpenAI API con retry automático ante errores transitorios
            response = self._retry(self.client.chat.completions.create)(
```
REEMPLAZAR CON:
```python
        try:
            with self._semaphore:
                # Llamar a OpenAI API con retry automático ante errores transitorios
                response = self._retry(self.client.chat.completions.create)(
```

Y ajustar el indentado del bloque hasta el return/except correspondiente. Alternativamente, es más limpio envolver solo la llamada:

Mejor enfoque — en `correct_with_profile`, BUSCAR:
```python
        try:
            response = self._retry(self.client.chat.completions.create)(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                response_format={"type": "json_object"},
            )
```
REEMPLAZAR CON:
```python
        try:
            with self._semaphore:
                response = self._retry(self.client.chat.completions.create)(
                    model=model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    max_tokens=self.max_tokens,
                    temperature=self.temperature,
                    response_format={"type": "json_object"},
                )
```

En `correct_text_style`, BUSCAR:
```python
        try:
            # Llamar a OpenAI API con retry automático ante errores transitorios
            response = self._retry(self.client.chat.completions.create)(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "Eres un corrector de estilo experto en español. Siempre respondes en formato JSON válido."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                response_format={"type": "json_object"}
            )
```
REEMPLAZAR CON:
```python
        try:
            with self._semaphore:
                # Llamar a OpenAI API con retry automático ante errores transitorios
                response = self._retry(self.client.chat.completions.create)(
                    model=self.model,
                    messages=[
                        {
                            "role": "system",
                            "content": "Eres un corrector de estilo experto en español. Siempre respondes en formato JSON válido."
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    max_tokens=self.max_tokens,
                    temperature=self.temperature,
                    response_format={"type": "json_object"}
                )
```

---

### CAMBIO 3.3: Retry mejorado en pipeline principal

**Archivo**: `backend/app/workers/tasks_pipeline.py`

BUSCAR el retry del pipeline principal (línea ~885):
```python
        self.retry(exc=e, countdown=60)
```

REEMPLAZAR CON:
```python
        # Retry con backoff exponencial (30s, 90s, 270s) en vez de fijo 60s
        retry_countdown = 30 * (3 ** self.request.retries)
        logger.warning(f"Pipeline {doc_id}: reintentando en {retry_countdown}s (intento {self.request.retries + 1}/3)")
        self.retry(exc=e, countdown=retry_countdown)
```

---
### VERIFICACIÓN FASE 3:
```bash
docker-compose up --build
```
1. Subir 8 documentos simultáneamente. Verificar en logs que solo 4 procesan a la vez, los otros esperan con mensajes `esperando slot`.
2. Los que esperan deben empezar automáticamente cuando los primeros 4 terminan.
3. Verificar que no hay errores de `RateLimitError` de OpenAI.
---

## RESUMEN DE ARCHIVOS MODIFICADOS

| Archivo | Fase | Tipo de cambio |
|---------|------|---------------|
| `backend/app/workers/tasks_pipeline.py` | 1,2,3 | Pool per-process, throttle commits, cache, block matching, semáforo, retry |
| `backend/app/workers/celery_app.py` | 1 | Task routing colas |
| `docker-compose.yml` | 1,2 | 2 workers, memory limits, healthchecks, postgres tuning, LT scaling |
| `backend/app/database.py` | 1 | pool_pre_ping, pool_recycle |
| `backend/app/config.py` | 3 | max_concurrent_pipelines |
| `backend/app/services/correction.py` | 2 | Cache param, LT connections |
| `backend/app/services/analysis.py` | 2 | Cache param |
| `backend/app/services/rendering.py` | 2 | Cache param |
| `backend/app/utils/openai_client.py` | 3 | Semáforo rate limiter |
| `.env` | 1 | Worker concurrency split, LT workers reducidos |
| `nginx-lt.conf` | 2 | NUEVO — nginx LB para LanguageTool |

---

## NOTAS IMPORTANTES

1. **La API key de OpenAI está expuesta en `.env`**. Rotarla en https://platform.openai.com/api-keys inmediatamente.

2. **Si la máquina tiene <16GB RAM**, reducir:
   - `CELERY_PIPELINE_CONCURRENCY=2`
   - `CELERY_BATCH_CONCURRENCY=4`
   - Quitar `languagetool-2` y el nginx LB, dejar solo `languagetool-1` renombrado a `languagetool`

3. **El cache de DOCX en Redis** agrega uso de RAM de Redis. Para documentos muy grandes (>50MB), el cache podría ser contraproducente. Si Redis se queda sin memoria, el fallback (descargar de MinIO) se activa automáticamente.

4. **Después de completar las 3 fases**, considerar:
   - Descomponer `process_document_pipeline` en un chain de Celery (A→B→C→D→E como tareas separadas) para retry granular por etapa. Esto es el cambio más grande y riesgoso, por eso NO está incluido en estas instrucciones.
   - Agregar Flower (`pip install flower`) para monitoreo de Celery en tiempo real.