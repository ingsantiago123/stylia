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
    openai_max_tokens: int = 500
    openai_temperature: float = 0.3
    # Máximo de bloques previos incluidos en cada prompt (se aplican ambos límites y se detiene al alcanzar cualquiera).
    # Valor inicial pensado para mantener coherencia sin inflar costo/tokens.
    openai_max_context_blocks: int = 8
    # Límite de caracteres acumulados para el contexto (se aplican ambos límites y se detiene al alcanzar cualquiera).
    # Valor inicial pensado para prompts compactos y estables en gpt-4o-mini.
    openai_max_context_chars: int = 2400
    # Umbral 0.0-1.0 para aceptar correcciones; 0.8 implica al menos 80% de similitud.
    openai_min_similarity_ratio: float = 0.8

    # --- LLM (llama.cpp) - Fase 2 ---
    llama_url: str = "http://localhost:8080"

    # --- Procesamiento ---
    max_upload_size_mb: int = 500
    max_document_pages: int = 1000
    window_size: int = 10  # páginas por ventana de contexto
    max_overflow_ratio: float = 1.10  # máx 110% longitud del original
    font_size_min_ratio: float = 0.90  # reducción máx de fuente

    # --- LibreOffice ---
    libreoffice_path: str = "soffice"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
