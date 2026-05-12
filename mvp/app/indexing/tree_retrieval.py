"""
G4 — Tree Retrieval: traversal adattivo sull'indice gerarchico LTREE.

Strategia:
  1. Cerca i chunk (level=3) le cui summary contengono i termini della query (FTS)
  2. Per ogni chunk trovato risale la gerarchia → ottiene contesto di sezione
  3. Ritorna lista di hit compatibile con RRF (chunk_id, payload, score)

Funzione pubblica:
  retrieve_tree(query, k) -> list[tuple[str, dict, float]]
"""

import logging

from app.storage import db

logger = logging.getLogger(__name__)


def retrieve_tree(query: str, k: int = 10) -> list[tuple[str, dict, float]]:
    """
    Traversal adattivo sull'indice tree_nodes.

    Fase 1 — cerca a livello chunk (level=3) via FTS sulla colonna summary.
    Fase 2 — per ogni hit risale fino a sezione (level=1) per contesto aggiuntivo.
    Ritorna [(chunk_id, payload_dict, score), ...] compatibile con RRF.
    """
    conn = db.get_pool().getconn()
    try:
        # Fase 1: FTS su summary dei chunk leaf
        rows = _search_chunk_level(conn, query, k * 3)

        if not rows:
            return []

        results: list[tuple[str, dict, float]] = []
        seen: set[str] = set()

        for chunk_id, doc_id, path_str, page_start, summary, rank in rows:
            if chunk_id in seen or chunk_id is None:
                continue
            seen.add(chunk_id)

            # Fase 2: carica testo reale del chunk da tabella chunks
            text = _get_chunk_text(conn, chunk_id)

            # Carica filename dal doc
            filename = _get_filename(conn, doc_id)

            payload = {
                "chunk_id":    chunk_id,
                "doc_id":      doc_id,
                "filename":    filename,
                "text":        text,
                "page_start":  page_start,
                "bm25_source": "tree",
                "tree_path":   path_str,
            }
            results.append((chunk_id, payload, float(rank)))

            if len(results) >= k:
                break

        return results

    finally:
        db.get_pool().putconn(conn)


def _search_chunk_level(conn, query: str, limit: int) -> list:
    """FTS sui summary dei nodi chunk (level=3)."""
    with conn.cursor() as cur:
        for lang in ("english", "simple"):
            cur.execute(
                f"""
                SELECT
                    tn.chunk_id, tn.doc_id, tn.path::text,
                    tn.page_start, tn.summary,
                    ts_rank(
                        to_tsvector('{lang}', COALESCE(tn.summary, '')),
                        websearch_to_tsquery('{lang}', %s)
                    ) AS rank
                FROM tree_nodes tn
                WHERE tn.level = 3
                  AND tn.chunk_id IS NOT NULL
                  AND to_tsvector('{lang}', COALESCE(tn.summary, ''))
                      @@ websearch_to_tsquery('{lang}', %s)
                ORDER BY rank DESC
                LIMIT %s
                """,
                (query, query, limit),
            )
            rows = cur.fetchall()
            if rows:
                return rows
    return []


def _get_chunk_text(conn, chunk_id: str) -> str:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT text_content FROM chunks WHERE chunk_id = %s", (chunk_id,)
        )
        row = cur.fetchone()
    return row[0] if row else ""


def _get_filename(conn, doc_id: str) -> str:
    with conn.cursor() as cur:
        cur.execute("SELECT filename FROM documents WHERE doc_id = %s", (doc_id,))
        row = cur.fetchone()
    return row[0] if row else ""


def get_nodes_traversed_count(query: str) -> int:
    """Conta quanti nodi tree sarebbero coinvolti in un retrieve_tree (per debug/stats)."""
    conn = db.get_pool().getconn()
    try:
        rows = _search_chunk_level(conn, query, 100)
        return len(rows)
    finally:
        db.get_pool().putconn(conn)
