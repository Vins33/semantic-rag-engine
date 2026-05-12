"""
PostgreSQL — schema + operazioni per E4 (Metadata Store).
Usa psycopg2 con un ThreadedConnectionPool.
"""

import psycopg2
from psycopg2 import pool as pg_pool

from app.core.config import settings

_pool: pg_pool.ThreadedConnectionPool | None = None

_SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    doc_id        TEXT PRIMARY KEY,
    sha256_raw    CHAR(64) UNIQUE NOT NULL,
    filename      TEXT NOT NULL,
    page_count    INTEGER,
    ingested_at   TIMESTAMPTZ DEFAULT NOW(),
    domain        TEXT    DEFAULT 'unknown',
    doc_type      TEXT    DEFAULT 'research_paper',
    language      TEXT    DEFAULT 'en',
    year          INTEGER,
    topics        TEXT[]  DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS chunks (
    chunk_id     TEXT PRIMARY KEY,
    doc_id       TEXT REFERENCES documents ON DELETE CASCADE,
    text_content TEXT NOT NULL,
    page_start   INTEGER,
    page_end     INTEGER
);

CREATE TABLE IF NOT EXISTS audit_log (
    entry_id    BIGSERIAL   PRIMARY KEY,
    prev_hash   CHAR(64)    NOT NULL,
    event_type  TEXT        NOT NULL,
    doc_id      TEXT,
    payload     JSONB       NOT NULL DEFAULT '{}',
    entry_hash  CHAR(64)    NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_chunks_doc ON chunks(doc_id);
CREATE INDEX IF NOT EXISTS idx_chunks_fts
    ON chunks USING GIN (to_tsvector('simple', text_content));
CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_log(created_at);
"""

# Migrations per DB già esistenti — idempotenti con IF NOT EXISTS
_MIGRATIONS = """
ALTER TABLE documents ADD COLUMN IF NOT EXISTS domain   TEXT    DEFAULT 'unknown';
ALTER TABLE documents ADD COLUMN IF NOT EXISTS doc_type TEXT    DEFAULT 'research_paper';
ALTER TABLE documents ADD COLUMN IF NOT EXISTS language TEXT    DEFAULT 'en';
ALTER TABLE documents ADD COLUMN IF NOT EXISTS year     INTEGER;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS topics   TEXT[]  DEFAULT '{}';
CREATE TABLE IF NOT EXISTS audit_log (
    entry_id    BIGSERIAL   PRIMARY KEY,
    prev_hash   CHAR(64)    NOT NULL,
    event_type  TEXT        NOT NULL,
    doc_id      TEXT,
    payload     JSONB       NOT NULL DEFAULT '{}',
    entry_hash  CHAR(64)    NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS entities (
    entity_id   BIGSERIAL   PRIMARY KEY,
    doc_id      TEXT        REFERENCES documents ON DELETE CASCADE,
    chunk_id    TEXT        REFERENCES chunks    ON DELETE CASCADE,
    page        INTEGER,
    text        TEXT        NOT NULL,
    type        TEXT        NOT NULL,
    confidence  REAL        NOT NULL,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS triples (
    triple_id   BIGSERIAL   PRIMARY KEY,
    doc_id      TEXT        REFERENCES documents ON DELETE CASCADE,
    chunk_id    TEXT        REFERENCES chunks    ON DELETE CASCADE,
    page        INTEGER,
    subject     TEXT        NOT NULL,
    predicate   TEXT        NOT NULL,
    object      TEXT        NOT NULL,
    confidence  REAL        NOT NULL,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_entities_doc    ON entities(doc_id);
CREATE INDEX IF NOT EXISTS idx_entities_type   ON entities(type);
CREATE INDEX IF NOT EXISTS idx_entities_text   ON entities USING GIN (to_tsvector('simple', text));
CREATE INDEX IF NOT EXISTS idx_triples_doc     ON triples(doc_id);
CREATE INDEX IF NOT EXISTS idx_triples_subject ON triples(subject);
CREATE INDEX IF NOT EXISTS idx_triples_object  ON triples(object);
CREATE INDEX IF NOT EXISTS idx_documents_domain ON documents(domain);
CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_log(created_at);
-- E5 — Tree Index (LTREE)
CREATE EXTENSION IF NOT EXISTS ltree;
CREATE TABLE IF NOT EXISTS tree_nodes (
    node_id     TEXT        PRIMARY KEY,
    doc_id      TEXT        REFERENCES documents ON DELETE CASCADE,
    chunk_id    TEXT        REFERENCES chunks    ON DELETE CASCADE,
    path        LTREE       NOT NULL,
    level       INTEGER     NOT NULL,   -- 0=doc, 1=section, 2=para, 3=chunk
    label       TEXT        NOT NULL,
    page_start  INTEGER     DEFAULT 0,
    summary     TEXT        DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_tree_path   ON tree_nodes USING GIST (path);
CREATE INDEX IF NOT EXISTS idx_tree_doc    ON tree_nodes (doc_id);
CREATE INDEX IF NOT EXISTS idx_tree_chunk  ON tree_nodes (chunk_id);
-- Chat persistence
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE TABLE IF NOT EXISTS chats (
    chat_id     UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    username    TEXT        NOT NULL,
    title       TEXT        NOT NULL DEFAULT 'Nuova chat',
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_chats_user ON chats(username, updated_at DESC);
CREATE TABLE IF NOT EXISTS chat_messages (
    msg_id      BIGSERIAL   PRIMARY KEY,
    chat_id     UUID        REFERENCES chats ON DELETE CASCADE,
    role        TEXT        NOT NULL,
    content     TEXT        NOT NULL,
    meta        JSONB       DEFAULT '{}',
    created_at  TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_chat_msgs ON chat_messages(chat_id, created_at);
"""


def get_pool() -> pg_pool.ThreadedConnectionPool:
    global _pool
    if _pool is None:
        _pool = pg_pool.ThreadedConnectionPool(1, 10, dsn=settings.postgres_dsn)
    return _pool


def init_schema() -> None:
    conn = get_pool().getconn()
    try:
        with conn.cursor() as cur:
            cur.execute(_SCHEMA)
            cur.execute(_MIGRATIONS)
        conn.commit()
    finally:
        get_pool().putconn(conn)


def insert_document(doc_id: str, sha256: str, filename: str, page_count: int) -> str:
    """Inserisce il documento e restituisce il doc_id effettivamente presente in DB."""
    conn = get_pool().getconn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO documents (doc_id, sha256_raw, filename, page_count)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (sha256_raw) DO UPDATE
                    SET filename   = EXCLUDED.filename,
                        page_count = EXCLUDED.page_count
                RETURNING doc_id
                """,
                (doc_id, sha256, filename, page_count),
            )
            row = cur.fetchone()
        conn.commit()
        return row[0]
    finally:
        get_pool().putconn(conn)


def insert_chunks(records: list[tuple]) -> None:
    """records = [(chunk_id, doc_id, text, page_start, page_end), ...]"""
    conn = get_pool().getconn()
    try:
        with conn.cursor() as cur:
            cur.executemany(
                """
                INSERT INTO chunks (chunk_id, doc_id, text_content, page_start, page_end)
                VALUES (%s, %s, %s, %s, %s)
                """,
                records,
            )
        conn.commit()
    finally:
        get_pool().putconn(conn)


def document_exists(sha256: str) -> bool:
    """True se un documento con questo SHA-256 è già indicizzato."""
    conn = get_pool().getconn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM documents WHERE sha256_raw = %s", (sha256,))
            return cur.fetchone() is not None
    finally:
        get_pool().putconn(conn)


def update_document_metadata(
    doc_id: str,
    domain: str,
    doc_type: str,
    language: str,
    year: int | None,
    topics: list[str],
) -> None:
    """D3+D4: salva i metadati arricchiti nel documento."""
    conn = get_pool().getconn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE documents
                   SET domain = %s, doc_type = %s, language = %s,
                       year = %s, topics = %s
                 WHERE doc_id = %s
                """,
                (domain, doc_type, language, year, topics, doc_id),
            )
        conn.commit()
    finally:
        get_pool().putconn(conn)


def get_document_text_excerpt(doc_id: str, max_chars: int = 2000) -> str:
    """Primi max_chars di testo del documento (per metadata enrichment e migration)."""
    conn = get_pool().getconn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT text_content FROM chunks
                WHERE doc_id = %s
                ORDER BY page_start LIMIT 3
                """,
                (doc_id,),
            )
            rows = cur.fetchall()
        return " ".join(r[0] for r in rows)[:max_chars]
    finally:
        get_pool().putconn(conn)


def get_all_documents() -> list[dict]:
    """Tutti i documenti con metadati correnti (per migration script)."""
    conn = get_pool().getconn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT doc_id, filename, domain, language, doc_type, year
                FROM documents
                ORDER BY ingested_at
                """
            )
            rows = cur.fetchall()
        return [
            {
                "doc_id":   r[0],
                "filename": r[1],
                "domain":   r[2],
                "language": r[3],
                "doc_type": r[4],
                "year":     r[5],
            }
            for r in rows
        ]
    finally:
        get_pool().putconn(conn)


def fts_search(
    query: str,
    limit: int,
    domain: str | None = None,
    language: str | None = None,
    doc_type: str | None = None,
) -> list[dict]:
    """Full-text search con filtri metadata opzionali (G3) e fallback english→simple."""
    conn = get_pool().getconn()
    try:
        # Costruisci WHERE clause aggiuntiva per G3
        extra_conds: list[str] = []
        extra_params: list = []
        if domain:
            extra_conds.append("d.domain = %s")
            extra_params.append(domain)
        if language:
            extra_conds.append("d.language = %s")
            extra_params.append(language)
        if doc_type:
            extra_conds.append("d.doc_type = %s")
            extra_params.append(doc_type)
        extra_where = (" AND " + " AND ".join(extra_conds)) if extra_conds else ""

        with conn.cursor() as cur:
            for lang in ("english", "simple"):
                cur.execute(
                    f"""
                    SELECT
                        c.chunk_id, c.doc_id, c.text_content,
                        c.page_start, c.page_end, d.filename,
                        ts_rank(
                            to_tsvector('{lang}', c.text_content),
                            websearch_to_tsquery('{lang}', %s)
                        ) AS rank
                    FROM chunks c
                    JOIN documents d ON d.doc_id = c.doc_id
                    WHERE to_tsvector('{lang}', c.text_content)
                          @@ websearch_to_tsquery('{lang}', %s)
                    {extra_where}
                    ORDER BY rank DESC
                    LIMIT %s
                    """,
                    (query, query, *extra_params, limit),
                )
                rows = cur.fetchall()
                if rows:
                    break
        return [
            {
                "chunk_id":   r[0],
                "doc_id":     r[1],
                "text":       r[2],
                "page_start": r[3],
                "page_end":   r[4],
                "filename":   r[5],
                "fts_rank":   float(r[6]),
            }
            for r in rows
        ]
    finally:
        get_pool().putconn(conn)


# ── D1/D2 Entity + Triple CRUD ────────────────────────────────────────────────

def insert_entities(entities: list[dict], doc_id: str, chunk_id: str, page: int) -> None:
    """Inserisce entità estratte da D1 (NER) nella tabella entities."""
    if not entities:
        return
    conn = get_pool().getconn()
    try:
        with conn.cursor() as cur:
            cur.executemany(
                """
                INSERT INTO entities (doc_id, chunk_id, page, text, type, confidence)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                [(doc_id, chunk_id, page, e["text"], e["type"], e["confidence"])
                 for e in entities],
            )
        conn.commit()
    finally:
        get_pool().putconn(conn)


def insert_triples(triples: list[dict], doc_id: str, chunk_id: str, page: int) -> None:
    """Inserisce triple semantiche estratte da D2 nella tabella triples."""
    if not triples:
        return
    conn = get_pool().getconn()
    try:
        with conn.cursor() as cur:
            cur.executemany(
                """
                INSERT INTO triples (doc_id, chunk_id, page, subject, predicate, object, confidence)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                [(doc_id, chunk_id, page, t["subject"], t["predicate"], t["object"], t["confidence"])
                 for t in triples],
            )
        conn.commit()
    finally:
        get_pool().putconn(conn)


def get_chunks_for_doc(doc_id: str, limit: int = 10) -> list[dict]:
    """Ritorna i primi N chunk di un documento con testo e pagina."""
    conn = get_pool().getconn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT chunk_id, text_content, page_start
                FROM chunks
                WHERE doc_id = %s
                ORDER BY page_start
                LIMIT %s
                """,
                (doc_id, limit),
            )
            rows = cur.fetchall()
        return [{"chunk_id": r[0], "text": r[1], "page_start": r[2]} for r in rows]
    finally:
        get_pool().putconn(conn)


def get_entities_for_doc(doc_id: str, limit: int = 200) -> list[dict]:
    """Ritorna tutte le entità estratte da un documento."""
    conn = get_pool().getconn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT text, type, confidence, page
                FROM entities
                WHERE doc_id = %s
                ORDER BY confidence DESC
                LIMIT %s
                """,
                (doc_id, limit),
            )
            rows = cur.fetchall()
        return [{"text": r[0], "type": r[1], "confidence": r[2], "page": r[3]} for r in rows]
    finally:
        get_pool().putconn(conn)


def get_triples_for_doc(doc_id: str, limit: int = 200) -> list[dict]:
    """Ritorna tutte le triple semantiche di un documento."""
    conn = get_pool().getconn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT subject, predicate, object, confidence, page
                FROM triples
                WHERE doc_id = %s
                ORDER BY confidence DESC
                LIMIT %s
                """,
                (doc_id, limit),
            )
            rows = cur.fetchall()
        return [{"subject": r[0], "predicate": r[1], "object": r[2],
                 "confidence": r[3], "page": r[4]} for r in rows]
    finally:
        get_pool().putconn(conn)


def search_entities(text_query: str, entity_type: str | None = None, limit: int = 20) -> list[dict]:
    """Cerca entità per testo (FTS) con filtro tipo opzionale."""
    conn = get_pool().getconn()
    try:
        extra = "AND type = %s" if entity_type else ""
        params = [text_query, text_query] + ([entity_type] if entity_type else []) + [limit]
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT e.text, e.type, e.confidence, e.page, d.filename, e.doc_id
                FROM entities e
                JOIN documents d ON d.doc_id = e.doc_id
                WHERE to_tsvector('simple', e.text) @@ websearch_to_tsquery('simple', %s)
                   OR e.text ILIKE %s
                {extra}
                ORDER BY e.confidence DESC
                LIMIT %s
                """,
                [text_query, f"%{text_query}%"] + ([entity_type] if entity_type else []) + [limit],
            )
            rows = cur.fetchall()
        return [{"text": r[0], "type": r[1], "confidence": r[2],
                 "page": r[3], "filename": r[4], "doc_id": r[5]} for r in rows]
    finally:
        get_pool().putconn(conn)


# ── Chat persistence ───────────────────────────────────────────────────────

import json as _json


def chat_create(username: str, title: str = "Nuova chat") -> str:
    conn = get_pool().getconn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO chats (username, title) VALUES (%s, %s) RETURNING chat_id::text",
                (username, title),
            )
            chat_id = cur.fetchone()[0]
        conn.commit()
        return chat_id
    finally:
        get_pool().putconn(conn)


def chat_list(username: str) -> list[dict]:
    conn = get_pool().getconn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT c.chat_id::text, c.title, c.created_at, c.updated_at,
                       COUNT(m.msg_id) AS msg_count
                FROM chats c
                LEFT JOIN chat_messages m ON m.chat_id = c.chat_id
                WHERE c.username = %s
                GROUP BY c.chat_id, c.title, c.created_at, c.updated_at
                ORDER BY c.updated_at DESC
                """,
                (username,),
            )
            rows = cur.fetchall()
        return [
            {"chat_id": r[0], "title": r[1], "created_at": r[2].isoformat(),
             "updated_at": r[3].isoformat(), "msg_count": r[4]}
            for r in rows
        ]
    finally:
        get_pool().putconn(conn)


def chat_rename(chat_id: str, username: str, title: str) -> bool:
    conn = get_pool().getconn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE chats SET title=%s, updated_at=NOW() WHERE chat_id=%s::uuid AND username=%s",
                (title, chat_id, username),
            )
            updated = cur.rowcount > 0
        conn.commit()
        return updated
    finally:
        get_pool().putconn(conn)


def chat_delete(chat_id: str, username: str) -> bool:
    conn = get_pool().getconn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM chats WHERE chat_id=%s::uuid AND username=%s",
                (chat_id, username),
            )
            deleted = cur.rowcount > 0
        conn.commit()
        return deleted
    finally:
        get_pool().putconn(conn)


def chat_messages_get(chat_id: str, username: str) -> list[dict]:
    conn = get_pool().getconn()
    try:
        with conn.cursor() as cur:
            # verify ownership
            cur.execute("SELECT 1 FROM chats WHERE chat_id=%s::uuid AND username=%s", (chat_id, username))
            if not cur.fetchone():
                return []
            cur.execute(
                "SELECT role, content, meta FROM chat_messages WHERE chat_id=%s::uuid ORDER BY created_at",
                (chat_id,),
            )
            rows = cur.fetchall()
        return [{"role": r[0], "content": r[1], "meta": r[2] or {}} for r in rows]
    finally:
        get_pool().putconn(conn)


def chat_message_append(chat_id: str, role: str, content: str, meta: dict | None = None) -> None:
    conn = get_pool().getconn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO chat_messages (chat_id, role, content, meta) VALUES (%s::uuid, %s, %s, %s)",
                (chat_id, role, content, _json.dumps(meta or {})),
            )
            cur.execute(
                "UPDATE chats SET updated_at=NOW() WHERE chat_id=%s::uuid",
                (chat_id,),
            )
        conn.commit()
    finally:
        get_pool().putconn(conn)


