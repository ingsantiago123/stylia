"""
Configuración centralizada del backend.
Usa Pydantic Settings para cargar variables de entorno.
"""

from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Configuración de la aplicación. Carga desde variables de entorno o .env."""

    # --- App ---
    app_name: str = "StyleCorrector"
    debug: bool = False

    # --- Base de datos ---
    database_url: str = Field(
        default="postgresql+asyncpg://stylecorrector:changeme@localhost:5432/stylecorrector",
        description="URL de conexión a PostgreSQL (async)",
    )
    database_url_sync: str = Field(
        default="postgresql+psycopg2://stylecorrector:changeme@localhost:5432/stylecorrector",
        description="URL de conexión a PostgreSQL (sync, para Alembic y Celery)",
    )

    # --- Redis ---
    redis_url: str = "redis://localhost:6379/0"

    # --- Celery ---
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"
    celery_task_time_limit: int = 7200
    celery_task_soft_time_limit: int = 6900
    celery_worker_prefetch_multiplier: int = 1
    celery_result_expires: int = 86400

    # --- MinIO ---
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "stylecorrector"
    minio_secure: bool = False

    # --- LanguageTool ---
    languagetool_url: str = "http://localhost:8010"
    languagetool_language: str = "es"

    # --- OpenAI API ---
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    openai_cheap_model: str = "gpt-4o-mini"
    openai_editorial_model: str = "gpt-4o-mini"
    openai_max_tokens: int = 500
    openai_temperature: float = 0.3

    # --- Precios OpenAI (USD por 1M tokens) ---
    # Actualizar cuando cambien: https://openai.com/api/pricing/
    openai_pricing_input: float = 0.15     # gpt-4o-mini input
    openai_pricing_output: float = 0.60    # gpt-4o-mini output

    # --- LLM (llama.cpp) - Fase 2 ---
    llama_url: str = "http://localhost:8080"

    # --- Procesamiento ---
    max_upload_size_mb: int = 500
    max_document_pages: int = 1000
    window_size: int = 10  # páginas por ventana de contexto
    max_overflow_ratio: float = 1.10  # máx 110% longitud del original
    font_size_min_ratio: float = 0.90  # reducción máx de fuente

    # --- Performance ---
    # Extraction
    extraction_upload_workers: int = 6  # threads for concurrent MinIO uploads

    # LanguageTool
    lt_timeout: float = 30.0
    lt_max_retries: int = 2

    # OpenAI resilience
    openai_max_retries: int = 3
    openai_timeout: float = 60.0

    # --- Corrección paralela por lotes (Stage D) ---
    parallel_correction_enabled: bool = False       # OFF por defecto; activar cuando esté validado
    parallel_correction_batch_size: int = 150       # párrafos objetivo por lote
    parallel_correction_max_batches: int = 8        # cap de paralelismo (máx lotes simultáneos)
    parallel_correction_lt_workers: int = 8         # threads para Pass 1 LT paralelo
    parallel_correction_boundary_check: bool = True  # re-corregir primer párrafo de cada lote con seed real

    # --- LibreOffice ---
    libreoffice_path: str = "soffice"

    # --- Concurrency control ---
    max_concurrent_pipelines: int = 4

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
