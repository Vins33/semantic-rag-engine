"""
F5B — Semantic Cache (Redis-backed).

Memorizza le risposte alle query recenti indexate per embedding semantico.
Su una nuova query, calcola la similarità coseno con le query in cache:
se sim >= threshold restituisce la risposta cached senza toccare retrieval/LLM.

Struttura Redis:
  cache:index          → SET di UUID (chiavi entrata)
  cache:entry:{uuid}   → JSON {query, embedding, response, timestamp}

TTL: ogni entry ha un expire time configurabile (default 1h).
Cleanup automatico: le chiavi scadute vengono saltate durante la ricerca.
"""

import json
import logging
import math
import uuid as _uuid
from typing import Optional

import redis

from app.core.config import settings

logger = logging.getLogger(__name__)

_redis_client: Optional[redis.Redis] = None


def _get_client() -> Optional[redis.Redis]:
    """Ritorna il client Redis, None se non raggiungibile (graceful degradation)."""
    global _redis_client
    if _redis_client is None:
        try:
            r = redis.Redis(
                host=settings.redis_host,
                port=settings.redis_port,
                decode_responses=True,
                socket_connect_timeout=2,
                socket_timeout=2,
            )
            r.ping()
            _redis_client = r
            logger.info("Cache Redis connessa su %s:%d", settings.redis_host, settings.redis_port)
        except Exception as exc:
            logger.warning("Redis non raggiungibile — cache disabilitata: %s", exc)
            return None
    return _redis_client


def _cosine_sim(a: list[float], b: list[float]) -> float:
    """Similarità coseno tra due vettori."""
    dot = sum(x * y for x, y in zip(a, b))
    na  = math.sqrt(sum(x * x for x in a))
    nb  = math.sqrt(sum(x * x for x in b))
    return dot / (na * nb) if na * nb > 0.0 else 0.0


def cache_get(query_embedding: list[float]) -> Optional[dict]:
    """
    Cerca nella cache una risposta semanticamente simile.
    Ritorna il dict risposta se trovato (sim >= threshold), altrimenti None.
    """
    r = _get_client()
    if r is None:
        return None

    threshold = settings.cache_similarity_threshold

    try:
        all_keys = r.smembers("cache:index")
    except Exception as exc:
        logger.warning("Cache read error: %s", exc)
        return None

    best_sim = 0.0
    best_response: Optional[dict] = None

    for key in all_keys:
        raw = r.get(f"cache:entry:{key}")
        if not raw:
            # Chiave scaduta — rimuovi dall'indice
            r.srem("cache:index", key)
            continue
        try:
            data = json.loads(raw)
            sim = _cosine_sim(query_embedding, data["embedding"])
            if sim > best_sim:
                best_sim = sim
                best_response = data["response"]
        except Exception:
            continue

    if best_sim >= threshold:
        logger.info("Cache HIT (sim=%.4f >= %.4f)", best_sim, threshold)
        return best_response

    return None


def cache_set(query: str, query_embedding: list[float], response: dict) -> None:
    """
    Salva una risposta in cache con TTL configurabile.
    Fallisce silenziosamente se Redis non è disponibile.
    """
    r = _get_client()
    if r is None:
        return

    key = str(_uuid.uuid4())
    entry = json.dumps({
        "query":     query,
        "embedding": query_embedding,
        "response":  response,
    })

    try:
        r.set(f"cache:entry:{key}", entry, ex=settings.cache_ttl_seconds)
        r.sadd("cache:index", key)
    except Exception as exc:
        logger.warning("Cache write error: %s", exc)


def cache_clear() -> int:
    """Svuota tutta la cache. Ritorna il numero di entry cancellate."""
    r = _get_client()
    if r is None:
        return 0
    try:
        keys = r.smembers("cache:index")
        for k in keys:
            r.delete(f"cache:entry:{k}")
        r.delete("cache:index")
        return len(keys)
    except Exception as exc:
        logger.warning("Cache clear error: %s", exc)
        return 0
