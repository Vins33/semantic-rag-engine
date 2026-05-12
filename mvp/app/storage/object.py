"""
MinIO — Object Storage (E1).
Gestisce upload/download dei PDF raw e degli artefatti di parsing.
"""

import io

from minio import Minio
from minio.error import S3Error

from app.core.config import settings

_client: Minio | None = None


def get_client() -> Minio:
    global _client
    if _client is None:
        _client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=False,
        )
    return _client


def ensure_bucket(client: Minio | None = None) -> None:
    c = client or get_client()
    if not c.bucket_exists(settings.minio_bucket):
        c.make_bucket(settings.minio_bucket)


def upload_pdf(doc_id: str, pdf_bytes: bytes) -> str:
    """Carica il PDF raw nel path raw/{doc_id}.pdf e restituisce la chiave."""
    c = get_client()
    key = f"raw/{doc_id}.pdf"
    c.put_object(
        settings.minio_bucket,
        key,
        io.BytesIO(pdf_bytes),
        length=len(pdf_bytes),
        content_type="application/pdf",
    )
    return key


def upload_markdown(doc_id: str, md_text: str) -> str:
    """Salva il markdown convertito nel path parsed/{doc_id}.md."""
    md_bytes = md_text.encode("utf-8")
    key = f"parsed/{doc_id}.md"
    c = get_client()
    c.put_object(
        settings.minio_bucket,
        key,
        io.BytesIO(md_bytes),
        length=len(md_bytes),
        content_type="text/markdown; charset=utf-8",
    )
    return key
