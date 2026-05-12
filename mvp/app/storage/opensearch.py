"""
E3 — OpenSearch BM25 client.

Client HTTP asincrono (httpx) per OpenSearch 2.13 senza security plugin.
Index: rag_chunks  — multi-field mappings per BM25 + metadata filtering.

Funzioni pubbliche:
  create_index_if_not_exists()       → crea indice se non esiste
  index_chunk(chunk)                 → indicizza singolo chunk
  index_chunks_bulk(chunks)          → bulk indicizzazione
  search_bm25(query, k, filters)    → BM25 search → list[dict]
  delete_chunk(chunk_id)             → rimuove chunk dall'indice
"""

import json
import logging
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

_INDEX = "rag_chunks"

_MAPPINGS = {
    "settings": {
        "number_of_shards": 1,
        "number_of_replicas": 0,
        "analysis": {
            "analyzer": {
                "text_analyzer": {
                    "type": "custom",
                    "tokenizer": "standard",
                    "filter": ["lowercase", "stop", "porter_stem"],
                }
            }
        },
    },
    "mappings": {
        "properties": {
            "chunk_id":  {"type": "keyword"},
            "doc_id":    {"type": "keyword"},
            "filename":  {"type": "keyword"},
            "page":      {"type": "integer"},
            "domain":    {"type": "keyword"},
            "language":  {"type": "keyword"},
            "doc_type":  {"type": "keyword"},
            "text": {
                "type": "text",
                "analyzer": "text_analyzer",
                "fields": {
                    "raw": {"type": "keyword", "ignore_above": 256},
                    "english": {"type": "text", "analyzer": "english"},
                },
            },
            "title": {
                "type": "text",
                "analyzer": "text_analyzer",
                "fields": {
                    "english": {"type": "text", "analyzer": "english"}
                },
            },
        }
    },
}


def _base_url() -> str:
    return settings.opensearch_url.rstrip("/")


def create_index_if_not_exists() -> None:
    """Crea l'indice rag_chunks se non esiste già."""
    url = f"{_base_url()}/{_INDEX}"
    try:
        with httpx.Client(timeout=15.0) as client:
            resp = client.head(url)
            if resp.status_code == 200:
                logger.debug("OpenSearch index '%s' già esistente.", _INDEX)
                return
            # 404 → crea
            resp = client.put(url, json=_MAPPINGS)
            resp.raise_for_status()
            logger.info("OpenSearch index '%s' creato.", _INDEX)
    except httpx.ConnectError as exc:
        logger.warning("OpenSearch non raggiungibile: %s — BM25 disabilitato.", exc)


def index_chunk(chunk: dict) -> bool:
    """
    Indicizza un singolo chunk.
    chunk deve avere: chunk_id, doc_id, text, page_start (o page), filename.
    Ritorna True se successo.
    """
    doc = {
        "chunk_id": chunk["chunk_id"],
        "doc_id":   chunk["doc_id"],
        "filename": chunk.get("filename", ""),
        "page":     chunk.get("page_start") or chunk.get("page", 0),
        "domain":   chunk.get("domain", ""),
        "language": chunk.get("language", ""),
        "doc_type": chunk.get("doc_type", ""),
        "text":     chunk.get("text") or chunk.get("text_content", ""),
        "title":    chunk.get("title", ""),
    }
    url = f"{_base_url()}/{_INDEX}/_doc/{doc['chunk_id']}"
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.put(url, json=doc)
            resp.raise_for_status()
        return True
    except Exception as exc:
        logger.warning("OpenSearch index_chunk error: %s", exc)
        return False


def index_chunks_bulk(chunks: list[dict]) -> int:
    """
    Bulk indicizzazione.  Ritorna numero di chunk indicizzati con successo.
    """
    if not chunks:
        return 0

    lines: list[str] = []
    for chunk in chunks:
        meta = {"index": {"_index": _INDEX, "_id": chunk["chunk_id"]}}
        doc = {
            "chunk_id": chunk["chunk_id"],
            "doc_id":   chunk["doc_id"],
            "filename": chunk.get("filename", ""),
            "page":     chunk.get("page_start") or chunk.get("page", 0),
            "domain":   chunk.get("domain", ""),
            "language": chunk.get("language", ""),
            "doc_type": chunk.get("doc_type", ""),
            "text":     chunk.get("text") or chunk.get("text_content", ""),
            "title":    chunk.get("title", ""),
        }
        lines.append(json.dumps(meta))
        lines.append(json.dumps(doc))

    body = "\n".join(lines) + "\n"
    url = f"{_base_url()}/_bulk"
    try:
        with httpx.Client(timeout=60.0) as client:
            resp = client.post(
                url,
                content=body.encode(),
                headers={"Content-Type": "application/x-ndjson"},
            )
            resp.raise_for_status()
            data = resp.json()
            errors = [i for i in data.get("items", []) if "error" in i.get("index", {})]
            if errors:
                logger.warning("OpenSearch bulk: %d errori su %d chunk", len(errors), len(chunks))
            return len(chunks) - len(errors)
    except Exception as exc:
        logger.warning("OpenSearch bulk error: %s", exc)
        return 0


def search_bm25(
    query: str,
    k: int = 10,
    filters: dict[str, Any] | None = None,
) -> list[dict]:
    """
    BM25 search su OpenSearch.

    filters: dict opzionale con chiavi domain, language, doc_type.
    Ritorna list[dict] compatibile con db.fts_search():
      chunk_id, doc_id, text, page_start, page_end, filename, bm25_score
    """
    must_clauses: list[dict] = [
        {
            "multi_match": {
                "query": query,
                "fields": ["text^3", "text.english^2", "title^1"],
                "type":   "best_fields",
                "tie_breaker": 0.3,
            }
        }
    ]

    filter_clauses: list[dict] = []
    if filters:
        for field in ("domain", "language", "doc_type"):
            val = filters.get(field)
            if val:
                filter_clauses.append({"term": {field: val}})

    body: dict = {
        "size": k,
        "query": {
            "bool": {
                "must":   must_clauses,
                "filter": filter_clauses,
            }
        },
        "_source": ["chunk_id", "doc_id", "filename", "page", "text"],
    }

    url = f"{_base_url()}/{_INDEX}/_search"
    try:
        with httpx.Client(timeout=15.0) as client:
            resp = client.post(url, json=body)
            resp.raise_for_status()
            hits = resp.json().get("hits", {}).get("hits", [])
    except Exception as exc:
        logger.warning("OpenSearch search_bm25 error: %s — fallback a lista vuota", exc)
        return []

    results: list[dict] = []
    for h in hits:
        src = h["_source"]
        results.append(
            {
                "chunk_id":     src.get("chunk_id", h["_id"]),
                "doc_id":       src.get("doc_id", ""),
                "text":         src.get("text", ""),
                "page_start":   src.get("page", 0),
                "page_end":     src.get("page", 0),
                "filename":     src.get("filename", ""),
                "bm25_score":   float(h.get("_score", 0.0)),
                "bm25_source":  "opensearch",
            }
        )
    return results


def delete_chunk(chunk_id: str) -> bool:
    url = f"{_base_url()}/{_INDEX}/_doc/{chunk_id}"
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.delete(url)
            return resp.status_code in (200, 404)
    except Exception as exc:
        logger.warning("OpenSearch delete_chunk error: %s", exc)
        return False
