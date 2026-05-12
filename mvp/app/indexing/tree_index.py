"""
E5 — Tree Index gerarchico su PostgreSQL LTREE.

Struttura: documento → sezione → paragrafo → chunk
  level 0 = documento  (path: d<doc_short>)
  level 1 = sezione    (path: d<doc_short>.s<idx>)
  level 2 = paragrafo  (path: d<doc_short>.s<sec>.p<idx>)
  level 3 = chunk      (path: d<doc_short>.s<sec>.p<para>.c<idx>)

Funzioni pubbliche:
  build_tree(doc_id)                → costruisce tree_nodes per un documento
  get_node(path_str)  -> dict|None  → nodo per path LTREE
  get_children(path_str) -> list    → figli diretti
  get_ancestors(path_str) -> list   → antenati (dal doc in su)
"""

import hashlib
import logging
import re

from app.storage import db

logger = logging.getLogger(__name__)

# Quanti chunk per sezione / paragrafo
_CHUNKS_PER_SECTION = 8
_CHUNKS_PER_PARA    = 4


def _safe_label(text: str, maxlen: int = 20) -> str:
    """Converte testo in label LTREE-safe (solo [a-zA-Z0-9_])."""
    s = re.sub(r"[^a-zA-Z0-9]", "_", text.strip())
    s = re.sub(r"_+", "_", s).strip("_")
    return s[:maxlen] or "node"


def _doc_short(doc_id: str) -> str:
    """Prefisso breve per il doc (8 hex chars)."""
    return "d" + hashlib.md5(doc_id.encode()).hexdigest()[:8]


def build_tree(doc_id: str) -> dict:
    """
    Legge i chunk del documento da PostgreSQL e costruisce la gerarchia
    tree_nodes (doc → sezioni → paragrafi → chunk).
    Ritorna conteggio nodi creati.
    """
    conn = db.get_pool().getconn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT chunk_id, text_content, page_start
                FROM chunks
                WHERE doc_id = %s
                ORDER BY page_start, chunk_id
                """,
                (doc_id,),
            )
            chunks = cur.fetchall()
    finally:
        db.get_pool().putconn(conn)

    if not chunks:
        logger.debug("tree_index: nessun chunk per doc_id=%s", doc_id)
        return {"doc_id": doc_id, "nodes_created": 0}

    doc_pfx = _doc_short(doc_id)
    nodes: list[tuple] = []  # (node_id, doc_id, chunk_id, path, level, label, page_start, summary)

    # ── Nodo documento (level 0) ──────────────────────────────────────────────
    doc_path = doc_pfx
    doc_node_id = f"tree_{doc_id}_doc"
    # Leggi il filename dal DB per il label
    conn2 = db.get_pool().getconn()
    try:
        with conn2.cursor() as cur:
            cur.execute("SELECT filename FROM documents WHERE doc_id = %s", (doc_id,))
            row = cur.fetchone()
            filename = row[0] if row else doc_id
    finally:
        db.get_pool().putconn(conn2)

    nodes.append((doc_node_id, doc_id, None, doc_path, 0, filename[:50], 0, ""))

    # ── Raggruppa chunk in sezioni ───────────────────────────────────────────
    section_groups: list[list] = []
    for i in range(0, len(chunks), _CHUNKS_PER_SECTION):
        section_groups.append(chunks[i : i + _CHUNKS_PER_SECTION])

    for sec_idx, section_chunks in enumerate(section_groups):
        sec_path     = f"{doc_pfx}.s{sec_idx:04d}"
        sec_node_id  = f"tree_{doc_id}_s{sec_idx}"
        sec_page     = section_chunks[0][2] if section_chunks else 0
        sec_label    = f"sec{sec_idx}"
        nodes.append((sec_node_id, doc_id, None, sec_path, 1, sec_label, sec_page, ""))

        # ── Raggruppa in paragrafi ──────────────────────────────────────────
        para_groups: list[list] = []
        for i in range(0, len(section_chunks), _CHUNKS_PER_PARA):
            para_groups.append(section_chunks[i : i + _CHUNKS_PER_PARA])

        for para_idx, para_chunks in enumerate(para_groups):
            para_path    = f"{sec_path}.p{para_idx:04d}"
            para_node_id = f"tree_{doc_id}_s{sec_idx}_p{para_idx}"
            para_page    = para_chunks[0][2] if para_chunks else 0
            para_label   = f"para{para_idx}"
            nodes.append((para_node_id, doc_id, None, para_path, 2, para_label, para_page, ""))

            # ── Chunk leaf ─────────────────────────────────────────────────
            for c_idx, (chunk_id, text, page_start) in enumerate(para_chunks):
                chunk_path    = f"{para_path}.c{c_idx:04d}"
                chunk_node_id = f"tree_{chunk_id}"
                summary       = text[:120].replace("\n", " ")
                chunk_label   = f"c{c_idx}"
                nodes.append((
                    chunk_node_id, doc_id, chunk_id,
                    chunk_path, 3, chunk_label, page_start, summary,
                ))

    # ── Upsert in batch ──────────────────────────────────────────────────────
    conn3 = db.get_pool().getconn()
    try:
        with conn3.cursor() as cur:
            cur.executemany(
                """
                INSERT INTO tree_nodes
                    (node_id, doc_id, chunk_id, path, level, label, page_start, summary)
                VALUES (%s, %s, %s, %s::ltree, %s, %s, %s, %s)
                ON CONFLICT (node_id) DO UPDATE
                    SET path       = EXCLUDED.path,
                        level      = EXCLUDED.level,
                        label      = EXCLUDED.label,
                        page_start = EXCLUDED.page_start,
                        summary    = EXCLUDED.summary
                """,
                nodes,
            )
        conn3.commit()
    finally:
        db.get_pool().putconn(conn3)

    logger.info("tree_index: doc_id=%s → %d nodi creati", doc_id, len(nodes))
    return {"doc_id": doc_id, "nodes_created": len(nodes)}


def get_node(path_str: str) -> dict | None:
    """Ritorna il nodo con il path LTREE specificato."""
    conn = db.get_pool().getconn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT node_id, doc_id, chunk_id, path::text, level, label, page_start, summary
                FROM tree_nodes WHERE path = %s::ltree
                """,
                (path_str,),
            )
            row = cur.fetchone()
        if row is None:
            return None
        return {
            "node_id": row[0], "doc_id": row[1], "chunk_id": row[2],
            "path": row[3], "level": row[4], "label": row[5],
            "page_start": row[6], "summary": row[7],
        }
    finally:
        db.get_pool().putconn(conn)


def get_children(path_str: str) -> list[dict]:
    """Ritorna i figli diretti (1 livello) del nodo indicato."""
    conn = db.get_pool().getconn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT node_id, doc_id, chunk_id, path::text, level, label, page_start, summary
                FROM tree_nodes
                WHERE path ~ (%s || '.*{1}')::lquery
                ORDER BY page_start
                """,
                (path_str,),
            )
            rows = cur.fetchall()
        return [
            {
                "node_id": r[0], "doc_id": r[1], "chunk_id": r[2],
                "path": r[3], "level": r[4], "label": r[5],
                "page_start": r[6], "summary": r[7],
            }
            for r in rows
        ]
    finally:
        db.get_pool().putconn(conn)


def get_ancestors(path_str: str) -> list[dict]:
    """Ritorna tutti gli antenati (dal documento fino al nodo padre)."""
    conn = db.get_pool().getconn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT node_id, doc_id, chunk_id, path::text, level, label, page_start, summary
                FROM tree_nodes
                WHERE path @> %s::ltree AND path != %s::ltree
                ORDER BY level
                """,
                (path_str, path_str),
            )
            rows = cur.fetchall()
        return [
            {
                "node_id": r[0], "doc_id": r[1], "chunk_id": r[2],
                "path": r[3], "level": r[4], "label": r[5],
                "page_start": r[6], "summary": r[7],
            }
            for r in rows
        ]
    finally:
        db.get_pool().putconn(conn)


def get_chunk_nodes_for_doc(doc_id: str) -> list[dict]:
    """Ritorna tutti i nodi chunk (level=3) di un documento."""
    conn = db.get_pool().getconn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT node_id, chunk_id, path::text, page_start, summary
                FROM tree_nodes
                WHERE doc_id = %s AND level = 3
                ORDER BY page_start
                """,
                (doc_id,),
            )
            rows = cur.fetchall()
        return [
            {"node_id": r[0], "chunk_id": r[1], "path": r[2],
             "page_start": r[3], "summary": r[4]}
            for r in rows
        ]
    finally:
        db.get_pool().putconn(conn)
