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
    worker_prefetch_multiplier=1,
    task_reject_on_worker_lost=True,
    task_time_limit=600,       # 10 min máx por tarea
    task_soft_time_limit=540,  # Warning a 9 min
    result_expires=86400,      # Resultados expiran en 24h
)

# Auto-descubrir tareas en los módulos de workers
celery_app.autodiscover_tasks([
    "app.workers.tasks_pipeline",
])
