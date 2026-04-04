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
