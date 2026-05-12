"""
DAG: batch_pdf_ingest
=====================
Scansiona MinIO ogni giorno alle 02:00 UTC, trova i PDF non ancora
indicizzati nel backend RAG, li invia all'ingestion endpoint, poi
ottimizza i parametri AutoRAGTuner (I8) con le nuove osservazioni.

Flusso:
  [scan_minio] → [ingest_new_pdfs] → [run_auto_tuner]

Idempotenza: ogni esecuzione controlla GET /api/v1/documents per evitare
  di re-indicizzare file già presenti.

Dipendenze runtime (installate nell'immagine Airflow):
  - minio>=7.0  (MinIO Python SDK)
"""

from __future__ import annotations

import json
import logging
import os
import urllib.request
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator

log = logging.getLogger(__name__)

# ── Configurazione (da env vars injettate dal docker-compose) ─────────────────
RAG_BACKEND_URL  = os.getenv("RAG_BACKEND_URL",  "http://backend:8000")
MINIO_ENDPOINT   = os.getenv("MINIO_ENDPOINT",   "minio:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "minioadmin")
MINIO_BUCKET     = os.getenv("MINIO_BUCKET",     "rag-documents")
RAG_API_TOKEN    = os.getenv("RAG_API_TOKEN",     "")

_DEFAULT_ARGS = {
    "owner":            "rag-engine",
    "depends_on_past":  False,
    "retries":          2,
    "retry_delay":      timedelta(minutes=5),
    "email_on_failure": False,
}


# ── Task functions ─────────────────────────────────────────────────────────────

def scan_minio(**context) -> list[str]:
    """T1 — Elenca tutti i .pdf nel bucket MinIO e li pushia via XCom."""
    try:
        from minio import Minio  # type: ignore[import-untyped]
        client = Minio(
            MINIO_ENDPOINT,
            access_key=MINIO_ACCESS_KEY,
            secret_key=MINIO_SECRET_KEY,
            secure=False,
        )
        # Crea il bucket se non esiste ancora (primo avvio)
        if not client.bucket_exists(MINIO_BUCKET):
            log.warning("Bucket '%s' non trovato — salto scan", MINIO_BUCKET)
            return []
        objects = client.list_objects(MINIO_BUCKET, recursive=True)
        pdfs = [obj.object_name for obj in objects if obj.object_name.lower().endswith(".pdf")]
        log.info("MinIO scan: %d PDF trovati nel bucket '%s'", len(pdfs), MINIO_BUCKET)
        context["ti"].xcom_push(key="minio_pdfs", value=pdfs)
        return pdfs
    except Exception as exc:
        log.error("MinIO scan fallito: %s", exc)
        return []


def _get_indexed_filenames() -> set[str]:
    """Interroga GET /api/v1/documents per recuperare i file già indicizzati."""
    try:
        req = urllib.request.Request(
            f"{RAG_BACKEND_URL}/api/v1/documents?limit=10000",
            headers={"Authorization": f"Bearer {RAG_API_TOKEN}"},
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
            return {doc["filename"] for doc in data.get("documents", [])}
    except Exception as exc:
        log.warning("GET /api/v1/documents fallito: %s — assumerò 0 file indicizzati", exc)
        return set()


def ingest_new_pdfs(**context) -> dict:
    """T2 — Invia al backend i PDF non ancora indicizzati."""
    minio_pdfs: list[str] = context["ti"].xcom_pull(key="minio_pdfs", task_ids="scan_minio") or []
    indexed = _get_indexed_filenames()

    new_pdfs = [p for p in minio_pdfs if os.path.basename(p) not in indexed]
    log.info(
        "MinIO: %d PDF | Già indicizzati: %d | Da indicizzare: %d",
        len(minio_pdfs), len(indexed), len(new_pdfs),
    )

    ingested: list[dict] = []
    failed:   list[dict] = []

    for obj_name in new_pdfs:
        basename = os.path.basename(obj_name)
        payload  = json.dumps({"minio_key": obj_name, "filename": basename}).encode()
        try:
            req = urllib.request.Request(
                f"{RAG_BACKEND_URL}/api/v1/documents/ingest-from-minio",
                data=payload,
                headers={
                    "Content-Type":  "application/json",
                    "Authorization": f"Bearer {RAG_API_TOKEN}",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=180) as resp:
                result = json.loads(resp.read())
                ingested.append({"file": basename, "doc_id": result.get("doc_id")})
                log.info("Indicizzato: %s → doc_id=%s", basename, result.get("doc_id"))
        except Exception as exc:
            failed.append({"file": basename, "error": str(exc)})
            log.error("Errore indicizzazione %s: %s", basename, exc)

    summary = {
        "total_minio":  len(minio_pdfs),
        "already_indexed": len(indexed),
        "new_found":    len(new_pdfs),
        "ingested":     len(ingested),
        "failed":       len(failed),
        "details":      ingested + failed,
    }
    context["ti"].xcom_push(key="ingest_summary", value=summary)
    log.info("Ingestione completata: %s", summary)
    return summary


def run_auto_tuner(**context) -> dict:
    """T3 — POST /api/v1/tuner/optimize per aggiornare parametri RAG (I8)."""
    try:
        req = urllib.request.Request(
            f"{RAG_BACKEND_URL}/api/v1/tuner/optimize",
            data=b"{}",
            headers={
                "Content-Type":  "application/json",
                "Authorization": f"Bearer {RAG_API_TOKEN}",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read())
            log.info("AutoRAGTuner ottimizzato: %s", result)
            return result
    except Exception as exc:
        log.warning("AutoRAGTuner optimize fallito (non bloccante): %s", exc)
        return {"error": str(exc)}


# ── DAG definition ─────────────────────────────────────────────────────────────

with DAG(
    dag_id="batch_pdf_ingest",
    description=(
        "Scansiona MinIO ogni notte, indicizza nuovi PDF nel backend RAG, "
        "poi ottimizza i parametri con AutoRAGTuner (I8)."
    ),
    schedule="0 2 * * *",       # ogni giorno alle 02:00 UTC
    start_date=datetime(2025, 1, 1),
    catchup=False,
    max_active_runs=1,           # no run concorrenti (idempotenza)
    default_args=_DEFAULT_ARGS,
    tags=["rag", "ingestion", "batch", "autotuner"],
) as dag:

    t_scan = PythonOperator(
        task_id="scan_minio",
        python_callable=scan_minio,
    )

    t_ingest = PythonOperator(
        task_id="ingest_new_pdfs",
        python_callable=ingest_new_pdfs,
    )

    t_tune = PythonOperator(
        task_id="run_auto_tuner",
        python_callable=run_auto_tuner,
    )

    # Pipeline: scan → ingest → tune
    t_scan >> t_ingest >> t_tune
