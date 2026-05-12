#!/usr/bin/env python3
"""
E3 — Reindex OpenSearch from PostgreSQL.

Legge tutti i chunk dalla tabella `chunks` (con join `documents` per i metadata)
e li indicizza in batch su OpenSearch.

Uso:
  cd /home/vins/semantic-rag-engine/mvp
  source .venv/bin/activate
  python3 scripts/reindex_opensearch.py [--batch 200] [--doc-id <doc_id>]
"""

import argparse
import logging
import sys
import os

# Aggiungi la root del progetto al path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import settings
from app.storage import opensearch as os_store

import psycopg2

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)


def fetch_chunks(conn, doc_id: str | None, offset: int, batch: int) -> list[dict]:
    with conn.cursor() as cur:
        if doc_id:
            cur.execute(
                """
                SELECT c.chunk_id, c.doc_id, c.text_content, c.page_start,
                       d.filename, d.domain, d.language, d.doc_type
                FROM chunks c
                JOIN documents d ON d.doc_id = c.doc_id
                WHERE c.doc_id = %s
                ORDER BY c.page_start
                OFFSET %s LIMIT %s
                """,
                (doc_id, offset, batch),
            )
        else:
            cur.execute(
                """
                SELECT c.chunk_id, c.doc_id, c.text_content, c.page_start,
                       d.filename, d.domain, d.language, d.doc_type
                FROM chunks c
                JOIN documents d ON d.doc_id = c.doc_id
                ORDER BY c.doc_id, c.page_start
                OFFSET %s LIMIT %s
                """,
                (offset, batch),
            )
        rows = cur.fetchall()
    return [
        {
            "chunk_id": r[0],
            "doc_id":   r[1],
            "text":     r[2],
            "page_start": r[3],
            "filename": r[4],
            "domain":   r[5] or "",
            "language": r[6] or "",
            "doc_type": r[7] or "",
        }
        for r in rows
    ]


def main():
    parser = argparse.ArgumentParser(description="Reindex all chunks from PostgreSQL to OpenSearch")
    parser.add_argument("--batch", type=int, default=200, help="Batch size (default: 200)")
    parser.add_argument("--doc-id", type=str, default=None, help="Reindex only this doc_id")
    args = parser.parse_args()

    logger.info("Connessione a PostgreSQL: %s", settings.postgres_dsn)
    conn = psycopg2.connect(settings.postgres_dsn)

    logger.info("Inizializzazione indice OpenSearch: %s", settings.opensearch_url)
    os_store.create_index_if_not_exists()

    offset = 0
    total_indexed = 0

    while True:
        chunks = fetch_chunks(conn, args.doc_id, offset, args.batch)
        if not chunks:
            break

        indexed = os_store.index_chunks_bulk(chunks)
        total_indexed += indexed
        logger.info(
            "Batch %d-%d: indicizzati %d/%d chunk",
            offset, offset + len(chunks) - 1, indexed, len(chunks),
        )
        offset += len(chunks)

    conn.close()
    logger.info("Reindex completato: %d chunk totali indicizzati.", total_indexed)


if __name__ == "__main__":
    main()
