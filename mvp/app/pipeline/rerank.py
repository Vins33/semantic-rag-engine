"""
Re-ranking cross-encoder post RRF.

Modello HuggingFace: cross-encoder/ms-marco-MiniLM-L-6-v2
  - 6 layer MiniLM fine-tuned su MS MARCO passage ranking
  - Input: (query, passage) → score di rilevanza
  - ~22M parametri, inferenza rapida su CPU/GPU

Caricamento lazy al primo utilizzo.
"""

import logging

logger = logging.getLogger(__name__)

_MODEL_ID = "cross-encoder/ms-marco-MiniLM-L-6-v2"
_encoder  = None


def _load() -> None:
    global _encoder
    if _encoder is not None:
        return
    from sentence_transformers import CrossEncoder
    logger.info(f"[Rerank] Caricamento {_MODEL_ID} …")
    _encoder = CrossEncoder(_MODEL_ID, max_length=512)
    logger.info("[Rerank] Cross-encoder pronto.")


def rerank(
    query: str,
    candidates: list[tuple],
) -> list[tuple]:
    """
    Ri-ordina i candidati usando il cross-encoder.

    Args:
        query:      stringa di ricerca
        candidates: [(chunk_id, payload_dict, rrf_score), ...]

    Returns:
        Lista riordinata per score cross-encoder decrescente.
        Il terzo elemento della tupla è sostituito con lo score cross-encoder.
    """
    if not candidates:
        return candidates

    _load()

    pairs  = [(query, c[1]["text"]) for c in candidates]
    scores = _encoder.predict(pairs)

    ranked = sorted(
        zip(candidates, scores),
        key=lambda x: float(x[1]),
        reverse=True,
    )

    return [(cid, payload, float(score)) for (cid, payload, _), score in ranked]
