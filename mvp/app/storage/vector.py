"""
Qdrant — Vector DB (E2).
Gestisce la collection pdf_chunks con ricerca ANN.
"""

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    Range,
    VectorParams,
)

from app.core.config import settings

_client: QdrantClient | None = None


def get_client() -> QdrantClient:
    global _client
    if _client is None:
        _client = QdrantClient(
            host=settings.qdrant_host,
            port=settings.qdrant_port,
            check_compatibility=False,
        )
    return _client


def ensure_collection(client: QdrantClient | None = None) -> None:
    c = client or get_client()
    existing = {col.name for col in c.get_collections().collections}
    if settings.qdrant_collection not in existing:
        c.create_collection(
            collection_name=settings.qdrant_collection,
            vectors_config=VectorParams(
                size=settings.embed_dim,
                distance=Distance.COSINE,
            ),
        )


def upsert_points(points: list[PointStruct]) -> None:
    get_client().upsert(
        collection_name=settings.qdrant_collection,
        points=points,
    )


def build_qdrant_filter(
    domain: str | None = None,
    language: str | None = None,
    doc_type: str | None = None,
    year_from: int | None = None,
    year_to: int | None = None,
) -> Filter | None:
    """Costruisce un Qdrant Filter per G3 metadata filtering. Ritorna None se nessun filtro."""
    must = []
    if domain:
        must.append(FieldCondition(key="domain", match=MatchValue(value=domain)))
    if language:
        must.append(FieldCondition(key="language", match=MatchValue(value=language)))
    if doc_type:
        must.append(FieldCondition(key="doc_type", match=MatchValue(value=doc_type)))
    year_range: dict = {}
    if year_from is not None:
        year_range["gte"] = year_from
    if year_to is not None:
        year_range["lte"] = year_to
    if year_range:
        must.append(FieldCondition(key="year", range=Range(**year_range)))
    return Filter(must=must) if must else None


def vector_search(
    query_vector: list[float],
    limit: int,
    filt: Filter | None = None,
) -> list:
    results = get_client().query_points(
        collection_name=settings.qdrant_collection,
        query=query_vector,
        limit=limit,
        with_payload=True,
        query_filter=filt,
    )
    return results.points


def update_doc_payload(doc_id: str, payload_update: dict) -> int:
    """
    Aggiorna campi payload per tutti i punti Qdrant di un documento.
    Usato dal migration script per aggiungere metadata D3+D4 ai punti esistenti.
    Ritorna il numero di punti aggiornati.
    """
    client = get_client()
    doc_filter = Filter(
        must=[FieldCondition(key="doc_id", match=MatchValue(value=doc_id))]
    )
    total = 0
    offset = None
    while True:
        results, next_offset = client.scroll(
            collection_name=settings.qdrant_collection,
            scroll_filter=doc_filter,
            limit=100,
            offset=offset,
            with_payload=False,
        )
        if not results:
            break
        point_ids = [p.id for p in results]
        client.set_payload(
            collection_name=settings.qdrant_collection,
            payload=payload_update,
            points=point_ids,
        )
        total += len(point_ids)
        if next_offset is None:
            break
        offset = next_offset
    return total
