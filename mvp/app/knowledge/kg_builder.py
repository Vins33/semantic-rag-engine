"""
C6 — Knowledge Graph Builder.

Pipeline: legge triples da PostgreSQL → normalizza → scrive in Neo4j.

Funzioni pubbliche:
  build_from_doc(doc_id)   → indicizza triple di un singolo documento in Neo4j
  build_all()              → indicizza TUTTE le triple presenti in PostgreSQL
"""

import logging

from app.storage import db, kg

logger = logging.getLogger(__name__)


def _normalize(text: str) -> str:
    """Normalizza testo entità: strip + lowercase."""
    return text.strip().lower()


def build_from_doc(doc_id: str) -> dict:
    """
    Legge le triple del documento da PostgreSQL e le scrive in Neo4j.
    Ritorna dict con conteggi.
    """
    triples = db.get_triples_for_doc(doc_id, limit=1000)
    if not triples:
        logger.debug("C6: nessuna tripla per doc_id=%s", doc_id)
        return {"doc_id": doc_id, "triples_written": 0}

    normalized = [
        {
            "subject":    _normalize(t["subject"]),
            "predicate":  _normalize(t["predicate"]),
            "object":     _normalize(t["object"]),
            "doc_id":     doc_id,
            "confidence": t.get("confidence", 1.0),
        }
        for t in triples
        if t.get("subject") and t.get("predicate") and t.get("object")
    ]

    written = kg.store_triples_bulk(normalized)
    logger.info("C6: doc_id=%s → %d/%d triple scritte in Neo4j", doc_id, written, len(triples))
    return {"doc_id": doc_id, "triples_written": written, "triples_total": len(triples)}


def build_all(batch_size: int = 500) -> dict:
    """
    Legge tutte le triple da PostgreSQL (in batch) e le scrive in Neo4j.
    Utile per una migrazione iniziale / ricostruzione completa del KG.
    """
    conn = db.get_pool().getconn()
    try:
        offset = 0
        total_written = 0
        total_read = 0

        while True:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT t.subject, t.predicate, t.object,
                           t.doc_id, t.confidence
                    FROM triples t
                    ORDER BY t.doc_id, t.triple_id
                    OFFSET %s LIMIT %s
                    """,
                    (offset, batch_size),
                )
                rows = cur.fetchall()

            if not rows:
                break

            normalized = [
                {
                    "subject":    _normalize(r[0]),
                    "predicate":  _normalize(r[1]),
                    "object":     _normalize(r[2]),
                    "doc_id":     r[3],
                    "confidence": float(r[4]),
                }
                for r in rows
                if r[0] and r[1] and r[2]
            ]

            written = kg.store_triples_bulk(normalized)
            total_written += written
            total_read    += len(rows)
            logger.info(
                "C6 build_all: batch %d-%d → %d/%d scritte",
                offset, offset + len(rows) - 1, written, len(rows),
            )
            offset += len(rows)

        return {"triples_read": total_read, "triples_written": total_written}
    finally:
        db.get_pool().putconn(conn)
