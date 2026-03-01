"""
Cliente MinIO — Gestión de almacenamiento de objetos S3-compatible.
"""

import io
import logging
from functools import lru_cache

from minio import Minio
from minio.error import S3Error

from app.config import settings

logger = logging.getLogger(__name__)


@lru_cache()
def get_minio_client() -> Minio:
    """Obtiene el cliente MinIO (singleton)."""
    return Minio(
        endpoint=settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=settings.minio_secure,
    )


async def ensure_bucket() -> None:
    """Crea el bucket si no existe."""
    client = get_minio_client()
    bucket = settings.minio_bucket
    try:
        if not client.bucket_exists(bucket):
            client.make_bucket(bucket)
            logger.info(f"Bucket '{bucket}' creado.")
        else:
            logger.info(f"Bucket '{bucket}' ya existe.")
    except S3Error as e:
        logger.error(f"Error creando bucket: {e}")
        raise


def upload_file(object_name: str, file_data: bytes, content_type: str = "application/octet-stream") -> str:
    """
    Sube un archivo a MinIO.
    Devuelve el URI del objeto: bucket/object_name.
    """
    client = get_minio_client()
    bucket = settings.minio_bucket

    client.put_object(
        bucket_name=bucket,
        object_name=object_name,
        data=io.BytesIO(file_data),
        length=len(file_data),
        content_type=content_type,
    )
    logger.info(f"Archivo subido: {object_name} ({len(file_data)} bytes)")
    return f"{bucket}/{object_name}"


def upload_file_from_path(object_name: str, file_path: str, content_type: str = "application/octet-stream") -> str:
    """Sube un archivo desde una ruta local a MinIO."""
    client = get_minio_client()
    bucket = settings.minio_bucket

    client.fput_object(
        bucket_name=bucket,
        object_name=object_name,
        file_path=file_path,
        content_type=content_type,
    )
    logger.info(f"Archivo subido desde {file_path} → {object_name}")
    return f"{bucket}/{object_name}"


def download_file(object_name: str) -> bytes:
    """Descarga un archivo de MinIO y devuelve los bytes."""
    client = get_minio_client()
    bucket = settings.minio_bucket

    response = client.get_object(bucket, object_name)
    try:
        data = response.read()
    finally:
        response.close()
        response.release_conn()

    return data


def download_file_to_path(object_name: str, file_path: str) -> str:
    """Descarga un archivo de MinIO a una ruta local."""
    client = get_minio_client()
    bucket = settings.minio_bucket

    client.fget_object(bucket, object_name, file_path)
    return file_path


def get_presigned_url(object_name: str, expires_hours: int = 1) -> str:
    """Genera una URL presignada para descargar un archivo."""
    from datetime import timedelta

    client = get_minio_client()
    bucket = settings.minio_bucket

    url = client.presigned_get_object(
        bucket, object_name, expires=timedelta(hours=expires_hours)
    )
    return url


def delete_file(object_name: str) -> None:
    """Elimina un archivo de MinIO."""
    client = get_minio_client()
    bucket = settings.minio_bucket
    client.remove_object(bucket, object_name)


def file_exists(object_name: str) -> bool:
    """Verifica si un archivo existe en MinIO."""
    client = get_minio_client()
    bucket = settings.minio_bucket
    try:
        client.stat_object(bucket, object_name)
        return True
    except S3Error:
        return False
