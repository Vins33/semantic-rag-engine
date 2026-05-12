#!/usr/bin/env python3
"""
Semantic RAG Engine — Local Stack Integration Test
Verifica tutti e 6 i servizi del data layer (E-layer) dell'architettura.

Componenti testati:
  [1] MinIO      → E1  Object Storage: upload/download PDF, struttura bucket
  [2] PostgreSQL → E4  Metadata Store: schema documents/chunks, CRUD
  [3] Redis      → BB4 Status Tracker + broker Celery: hash set, TTL
  [4] Qdrant     → E2  Vector DB: collection, upsert, search con payload filter
  [5] OpenSearch → E3  Keyword Index BM25: index, bulk, multi-field search
  [6] Neo4j      → C5  Knowledge Graph: nodi, relazioni, query Cypher

Uso:
    cp .env.example .env          # o usa .env già presente
    pip install -r requirements-test.txt
    python test_stack.py
"""

import io
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from typing import NamedTuple

from dotenv import load_dotenv

load_dotenv()

# ── Configurazione ────────────────────────────────────────────────────────────
MINIO_ENDPOINT   = os.getenv("MINIO_ENDPOINT",   "localhost:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ROOT_USER",  "minioadmin")
MINIO_SECRET_KEY = os.getenv("MINIO_ROOT_PASSWORD", "minioadmin")
MINIO_BUCKET     = os.getenv("MINIO_BUCKET",     "rag-documents")

PG_HOST     = os.getenv("POSTGRES_HOST",     "localhost")
PG_PORT     = int(os.getenv("POSTGRES_PORT", "5432"))
PG_USER     = os.getenv("POSTGRES_USER",     "raguser")
PG_PASSWORD = os.getenv("POSTGRES_PASSWORD", "ragpassword")
PG_DB       = os.getenv("POSTGRES_DB",       "ragdb")

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))

QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))

OS_HOST = os.getenv("OPENSEARCH_HOST", "localhost")
OS_PORT = int(os.getenv("OPENSEARCH_PORT", "9200"))

NEO4J_URI      = os.getenv("NEO4J_URI",      "bolt://localhost:7687")
NEO4J_USER     = os.getenv("NEO4J_USER",     "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "ragpassword")

# ── PDF minimo valido (in memoria, senza librerie esterne) ────────────────────
_MINIMAL_PDF = b"""%PDF-1.4
1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj
2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj
3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]
/Contents 4 0 R/Resources<</Font<</F1 5 0 R>>>>>>endobj
4 0 obj<</Length 51>>stream
BT /F1 12 Tf 72 720 Td (Semantic RAG Engine - Test PDF) Tj ET
endstream
endobj
5 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>endobj
xref
0 6
0000000000 65535 f\x20
0000000009 00000 n\x20
0000000058 00000 n\x20
0000000115 00000 n\x20
0000000266 00000 n\x20
0000000369 00000 n\x20
trailer<</Size 6/Root 1 0 R>>
startxref
441
%%EOF"""

# ── Helpers ───────────────────────────────────────────────────────────────────
def _ok(msg: str)  -> None: print(f"    \033[32m✓\033[0m {msg}")
def _fail(msg: str)-> None: print(f"    \033[31m✗\033[0m {msg}")
def _sep(n: int = 1, name: str = "") -> None:
    print(f"\n[{n}/6] {name}")

class Result(NamedTuple):
    service: str
    passed: bool
    detail: str


# ── 1. MinIO ──────────────────────────────────────────────────────────────────
def test_minio() -> Result:
    _sep(1, "MinIO — Object Storage (E1)")
    try:
        from minio import Minio

        client = Minio(
            MINIO_ENDPOINT,
            access_key=MINIO_ACCESS_KEY,
            secret_key=MINIO_SECRET_KEY,
            secure=False,
        )

        # Crea bucket se non esiste
        if not client.bucket_exists(MINIO_BUCKET):
            client.make_bucket(MINIO_BUCKET)
            _ok(f"Bucket '{MINIO_BUCKET}' creato")
        else:
            _ok(f"Bucket '{MINIO_BUCKET}' già esistente")

        # Upload PDF in raw/
        doc_id      = str(uuid.uuid4())
        raw_key     = f"raw/{doc_id}.pdf"
        pdf_stream  = io.BytesIO(_MINIMAL_PDF)
        client.put_object(
            MINIO_BUCKET, raw_key, pdf_stream,
            length=len(_MINIMAL_PDF), content_type="application/pdf",
        )
        _ok(f"PDF caricato → {raw_key}")

        # Upload metadati in parsed/
        meta = json.dumps({
            "doc_id": doc_id,
            "pages": 1,
            "language": "it",
            "parsed_at": datetime.now(timezone.utc).isoformat(),
        }).encode()
        meta_key = f"parsed/{doc_id}_meta.json"
        client.put_object(
            MINIO_BUCKET, meta_key, io.BytesIO(meta),
            length=len(meta), content_type="application/json",
        )
        _ok(f"Metadati caricati → {meta_key}")

        # Elenca oggetti nel bucket
        objects = list(client.list_objects(MINIO_BUCKET, recursive=True))
        _ok(f"Oggetti nel bucket: {len(objects)}")

        # Download e verifica integrità
        resp = client.get_object(MINIO_BUCKET, raw_key)
        downloaded = resp.read()
        assert downloaded == _MINIMAL_PDF, "Contenuto PDF non corrisponde all'originale"
        _ok("Integrità verificata: upload == download (byte-per-byte)")

        # Pulizia
        client.remove_object(MINIO_BUCKET, raw_key)
        client.remove_object(MINIO_BUCKET, meta_key)
        _ok("Oggetti di test rimossi")

        return Result("MinIO", True, f"Bucket '{MINIO_BUCKET}' OK · upload/download/integrità OK")

    except Exception as exc:
        _fail(str(exc))
        return Result("MinIO", False, str(exc))


# ── 2. PostgreSQL ─────────────────────────────────────────────────────────────
def test_postgres() -> Result:
    _sep(2, "PostgreSQL 15 — Metadata Store (E4)")
    try:
        import psycopg2

        conn = psycopg2.connect(
            host=PG_HOST, port=PG_PORT,
            user=PG_USER, password=PG_PASSWORD,
            dbname=PG_DB,
        )
        cur = conn.cursor()

        # Schema da architettura §9.2 E4
        cur.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                doc_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                sha256_raw    CHAR(64) UNIQUE NOT NULL,
                source_uri    TEXT,
                source_type   VARCHAR(20),
                title         TEXT,
                author        TEXT[],
                creation_date DATE,
                language      CHAR(2),
                domain        VARCHAR(30),
                doc_type      VARCHAR(30),
                page_count    INTEGER,
                version       INTEGER DEFAULT 1,
                ingested_at   TIMESTAMPTZ DEFAULT NOW(),
                acl           JSONB DEFAULT '[]'
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS chunks (
                chunk_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                doc_id           UUID REFERENCES documents ON DELETE CASCADE,
                page_start       INTEGER,
                page_end         INTEGER,
                section_title    TEXT,
                token_count      INTEGER,
                saliency_score   FLOAT,
                confidence_score FLOAT DEFAULT 1.0
            );
        """)
        conn.commit()
        _ok("Tabelle create: documents, chunks")

        # Inserimento documento di test
        doc_id = str(uuid.uuid4())
        cur.execute("""
            INSERT INTO documents (doc_id, sha256_raw, source_type, title, language, domain, page_count)
            VALUES (%s, %s, 'local', 'GDPR Test Document', 'it', 'Legale', 15)
        """, (doc_id, "a" * 64))

        # Inserimento chunk di test
        cur.execute("""
            INSERT INTO chunks (doc_id, page_start, page_end, section_title, token_count, saliency_score)
            VALUES (%s, 5, 6, 'Art. 5 — Principi', 498, 0.87)
        """, (doc_id,))
        conn.commit()
        _ok(f"Documento inserito: doc_id={doc_id[:8]}…")

        # Query con JOIN
        cur.execute("""
            SELECT d.title, d.domain, d.page_count, c.section_title, c.saliency_score
            FROM documents d JOIN chunks c ON c.doc_id = d.doc_id
            WHERE d.doc_id = %s
        """, (doc_id,))
        row = cur.fetchone()
        assert row[0] == "GDPR Test Document"
        _ok(f"JOIN OK: '{row[0]}' · '{row[3]}' (saliency={row[4]})")

        # Pulizia
        cur.execute("DELETE FROM documents WHERE doc_id = %s", (doc_id,))
        conn.commit()
        cur.close()
        conn.close()
        _ok("Dati di test rimossi")

        return Result("PostgreSQL", True, "Schema OK · insert/JOIN/delete OK")

    except Exception as exc:
        _fail(str(exc))
        return Result("PostgreSQL", False, str(exc))


# ── 3. Redis ──────────────────────────────────────────────────────────────────
def test_redis() -> Result:
    _sep(3, "Redis 7 — Broker Celery + Status Tracker (BB4)")
    try:
        import redis as redis_lib

        r = redis_lib.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
        r.ping()
        _ok("PING → PONG")

        # Simula stato job ingestione online (pattern BB4)
        job_id   = str(uuid.uuid4())
        job_key  = f"ingest:job:{job_id}"
        job_data = {
            "job_id":       job_id,
            "status":       "processing",
            "progress_pct": "65",
            "current_step": "D5_chunking",
            "started_at":   datetime.now(timezone.utc).isoformat(),
        }
        r.hset(job_key, mapping=job_data)
        r.expire(job_key, 86400)          # TTL 24h come da architettura BB4
        _ok(f"Job status salvato: {job_key[:30]}… (TTL=24h)")

        got = r.hgetall(job_key)
        assert got["status"] == "processing"
        assert got["progress_pct"] == "65"
        _ok(f"Job status letto: step={got['current_step']}, progress={got['progress_pct']}%")

        # Simula coda Celery (LPUSH → LLEN)
        queue_name = "ingest_high"
        task_payload = json.dumps({"task": "ingest_pdf", "doc_id": str(uuid.uuid4())})
        r.lpush(queue_name, task_payload)
        queue_len = r.llen(queue_name)
        _ok(f"Task accodato in '{queue_name}' (lunghezza coda: {queue_len})")

        # Pulizia
        r.delete(job_key)
        r.delete(queue_name)
        _ok("Chiavi di test rimosse")

        return Result("Redis", True, "PING OK · hash set/get/TTL OK · LPUSH/LLEN OK")

    except Exception as exc:
        _fail(str(exc))
        return Result("Redis", False, str(exc))


# ── 4. Qdrant ─────────────────────────────────────────────────────────────────
def test_qdrant() -> Result:
    _sep(4, "Qdrant — Vector DB (E2)")
    try:
        import random
        from qdrant_client import QdrantClient
        from qdrant_client.models import (
            Distance,
            FieldCondition,
            Filter,
            MatchValue,
            PointStruct,
            VectorParams,
        )

        client     = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
        coll_name  = "pdf_chunks_test"
        vector_dim = 128   # ridotto per dev locale (prod: 3072 o 1024)

        # Ricrea collection
        existing = {c.name for c in client.get_collections().collections}
        if coll_name in existing:
            client.delete_collection(coll_name)
        client.create_collection(
            collection_name=coll_name,
            vectors_config=VectorParams(size=vector_dim, distance=Distance.COSINE),
        )
        _ok(f"Collection '{coll_name}' creata (dim={vector_dim}, cosine)")

        # Inserisci 5 vettori con payload
        rng    = random.Random(42)
        points = [
            PointStruct(
                id=str(uuid.uuid4()),
                vector=[rng.random() for _ in range(vector_dim)],
                payload={
                    "chunk_id":        str(uuid.uuid4()),
                    "doc_id":          str(uuid.uuid4()),
                    "page_start":      i + 1,
                    "page_end":        i + 2,
                    "domain":          "Legale",
                    "section_title":   f"Art. {i + 1} — GDPR",
                    "confidence_score": round(0.85 + i * 0.02, 2),
                    "token_count":     480 + i * 10,
                },
            )
            for i in range(5)
        ]
        client.upsert(collection_name=coll_name, points=points)
        _ok("5 vettori inseriti con payload metadata")

        # Ricerca con payload filter (domain='Legale')
        query_vec = [rng.random() for _ in range(vector_dim)]
        results   = client.search(
            collection_name=coll_name,
            query_vector=query_vec,
            query_filter=Filter(
                must=[FieldCondition(key="domain", match=MatchValue(value="Legale"))]
            ),
            limit=3,
            with_payload=True,
        )
        assert len(results) > 0
        _ok(f"Ricerca vettoriale OK: {len(results)} risultati · domain='Legale' · "
            f"top score={results[0].score:.4f}")
        _ok(f"Top chunk: '{results[0].payload['section_title']}' "
            f"(conf={results[0].payload['confidence_score']})")

        # Info collection
        info = client.get_collection(coll_name)
        _ok(f"Vettori nella collection: {info.vectors_count}")

        # Pulizia
        client.delete_collection(coll_name)
        _ok(f"Collection '{coll_name}' rimossa")

        return Result("Qdrant", True,
                      f"Collection OK · 5 vettori upsert · search con filter OK")

    except Exception as exc:
        _fail(str(exc))
        return Result("Qdrant", False, str(exc))


# ── 5. OpenSearch ─────────────────────────────────────────────────────────────
def test_opensearch() -> Result:
    _sep(5, "OpenSearch 2.x — Keyword Index BM25 (E3)")
    try:
        from opensearchpy import OpenSearch

        client = OpenSearch(
            hosts=[{"host": OS_HOST, "port": OS_PORT}],
            http_compress=True,
            use_ssl=False,
            verify_certs=False,
            ssl_assert_hostname=False,
            ssl_show_warn=False,
        )

        info = client.info()
        _ok(f"Connesso: OpenSearch {info['version']['number']}")

        index_name = "pdf_chunks_test"

        # Ricrea index
        if client.indices.exists(index=index_name):
            client.indices.delete(index=index_name)

        # Settings BM25 con parametri da architettura §9.2 E3 (k1=1.5, b=0.75)
        client.indices.create(index=index_name, body={
            "settings": {
                "number_of_shards":   1,
                "number_of_replicas": 0,
                "similarity": {
                    "bm25_rag": {"type": "BM25", "k1": 1.5, "b": 0.75},
                },
            },
            "mappings": {
                "properties": {
                    "text_content":  {"type": "text",    "similarity": "bm25_rag"},
                    "section_title": {"type": "text",    "similarity": "bm25_rag"},
                    "topic_tags":    {"type": "keyword"},
                    "domain":        {"type": "keyword"},
                    "doc_id":        {"type": "keyword"},
                    "chunk_id":      {"type": "keyword"},
                    "page_start":    {"type": "integer"},
                    "confidence":    {"type": "float"},
                },
            },
        })
        _ok(f"Index '{index_name}' creato (BM25 k1=1.5 b=0.75)")

        # Indicizza 3 chunk di test
        docs = [
            {
                "chunk_id":     str(uuid.uuid4()),
                "doc_id":       str(uuid.uuid4()),
                "text_content": "Il GDPR prevede la notifica delle violazioni dei dati personali "
                                "entro 72 ore dalla scoperta.",
                "section_title": "Art. 33 — Notifica all'autorità di controllo",
                "topic_tags":   ["GDPR", "data breach", "notifica", "72 ore"],
                "domain":       "Legale",
                "page_start":   12,
                "confidence":   0.95,
            },
            {
                "chunk_id":     str(uuid.uuid4()),
                "doc_id":       str(uuid.uuid4()),
                "text_content": "La NIS2 impone la notifica degli incidenti significativi "
                                "entro 24 ore alle autorità competenti.",
                "section_title": "Art. 23 — Obblighi di segnalazione",
                "topic_tags":   ["NIS2", "incidente", "notifica", "24 ore"],
                "domain":       "Legale",
                "page_start":   8,
                "confidence":   0.92,
            },
            {
                "chunk_id":     str(uuid.uuid4()),
                "doc_id":       str(uuid.uuid4()),
                "text_content": "Il manuale tecnico descrive la configurazione del firewall "
                                "e le policy di accesso alla rete.",
                "section_title": "§3.2 — Configurazione sicurezza di rete",
                "topic_tags":   ["firewall", "rete", "sicurezza"],
                "domain":       "Tecnico",
                "page_start":   5,
                "confidence":   0.88,
            },
        ]
        for doc in docs:
            client.index(index=index_name, id=doc["chunk_id"], body=doc)
        client.indices.refresh(index=index_name)
        _ok(f"{len(docs)} chunk indicizzati")

        # Multi-field BM25 search (pattern da §9.2 E3)
        results = client.search(index=index_name, body={
            "query": {
                "multi_match": {
                    "query":  "notifica violazione GDPR",
                    "fields": ["text_content^2", "section_title^3", "topic_tags^1.5"],
                },
            },
            "size": 3,
        })
        hits = results["hits"]["hits"]
        assert len(hits) > 0
        _ok(f"Ricerca BM25 OK: {len(hits)} hit(s)")
        _ok(f"Top hit: '{hits[0]['_source']['section_title']}' "
            f"(score={hits[0]['_score']:.3f})")

        # Metadata filter: solo documenti 'Legale'
        results_filtered = client.search(index=index_name, body={
            "query": {
                "bool": {
                    "must":   [{"match": {"text_content": "notifica"}}],
                    "filter": [{"term": {"domain": "Legale"}}],
                },
            },
        })
        _ok(f"Filter domain='Legale': {results_filtered['hits']['total']['value']} doc(s)")

        # Pulizia
        client.indices.delete(index=index_name)
        _ok(f"Index '{index_name}' rimosso")

        return Result("OpenSearch", True,
                      f"Index OK · {len(docs)} docs · multi-field BM25 · filter OK")

    except Exception as exc:
        _fail(str(exc))
        return Result("OpenSearch", False, str(exc))


# ── 6. Neo4j ──────────────────────────────────────────────────────────────────
def test_neo4j() -> Result:
    _sep(6, "Neo4j 5.x — Knowledge Graph (C5 / E5)")
    try:
        from neo4j import GraphDatabase

        driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        driver.verify_connectivity()
        _ok("Connesso via Bolt")

        doc_id = str(uuid.uuid4())

        with driver.session() as session:
            # Crea Document + Concept + relazione :MENTIONS
            # Struttura da architettura §7.2 C5 (triple RDF mappate in Cypher)
            result = session.run("""
                CREATE (d:Document {
                    doc_id: $doc_id,
                    title:  'GDPR - Regolamento UE 2016/679',
                    domain: 'Legale',
                    language: 'it'
                })
                CREATE (c1:Concept {name: 'GDPR',  type: 'Regulation'})
                CREATE (c2:Concept {name: 'notifica_violazione', type: 'Concept'})
                CREATE (d)-[:MENTIONS {page: 12, confidence: 0.95}]->(c1)
                CREATE (d)-[:MENTIONS {page: 12, confidence: 0.91}]->(c2)
                CREATE (c1)-[:RELATED_TO {weight: 0.88}]->(c2)
                RETURN d.title AS doc, count(*) AS nodes_created
            """, doc_id=doc_id)
            record = result.single()
            _ok(f"Nodi creati: Document '{record['doc']}' + 2 Concept")

            # Query Cypher: trova concetti collegati al documento
            result = session.run("""
                MATCH (d:Document {doc_id: $doc_id})-[r:MENTIONS]->(c:Concept)
                RETURN c.name AS concept, c.type AS type, r.confidence AS conf
                ORDER BY r.confidence DESC
            """, doc_id=doc_id)
            rows = result.data()
            assert len(rows) == 2
            _ok(f"Relazioni :MENTIONS trovate: {len(rows)}")
            for row in rows:
                _ok(f"  → '{row['concept']}' ({row['type']}) conf={row['conf']}")

            # Query path: concetti correlati al GDPR via RELATED_TO
            result = session.run("""
                MATCH (c1:Concept {name: 'GDPR'})-[r:RELATED_TO]->(c2:Concept)
                RETURN c2.name AS related, r.weight AS weight
            """)
            rel_row = result.single()
            _ok(f"Path GDPR -[:RELATED_TO]→ '{rel_row['related']}' (weight={rel_row['weight']})")

            # Pulizia
            session.run("""
                MATCH (d:Document {doc_id: $doc_id})
                OPTIONAL MATCH (d)-[:MENTIONS]->(c)
                DETACH DELETE d, c
            """, doc_id=doc_id)
            _ok("Nodi di test rimossi (DETACH DELETE)")

        driver.close()
        return Result("Neo4j", True,
                      "Bolt OK · Document+Concept creati · :MENTIONS/:RELATED_TO · path query OK")

    except Exception as exc:
        _fail(str(exc))
        return Result("Neo4j", False, str(exc))


# ── Main ──────────────────────────────────────────────────────────────────────
def main() -> int:
    print("=" * 64)
    print(" Semantic RAG Engine — Local Stack Integration Test")
    print(f" {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 64)

    tests   = [test_minio, test_postgres, test_redis,
               test_qdrant, test_opensearch, test_neo4j]
    results = []

    for fn in tests:
        try:
            results.append(fn())
        except Exception as exc:
            name = fn.__name__.replace("test_", "").capitalize()
            results.append(Result(name, False, f"Errore imprevisto: {exc}"))

    # Riepilogo
    print("\n" + "=" * 64)
    print(" RIEPILOGO")
    print("=" * 64)
    passed = sum(1 for r in results if r.passed)
    for r in results:
        color  = "\033[32m" if r.passed else "\033[31m"
        status = "PASS" if r.passed else "FAIL"
        reset  = "\033[0m"
        print(f"  {color}[{status}]{reset} {r.service:<14} {r.detail[:55]}")

    print(f"\n  {passed}/{len(results)} servizi OK")
    print("=" * 64)

    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
