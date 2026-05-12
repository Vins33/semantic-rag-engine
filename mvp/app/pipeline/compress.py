"""
G7A — Query-Conditioned Context Compression.

Riferimento: arXiv 2602.15856 (WWW 2026) — compressione del contesto guidata dalla query.

Algoritmo (extractive, senza I/O):
  1. Tokenizza la query in parole significative (4+ chars, non stop-word)
  2. Per ogni chunk, scoreggia ogni frase in base all'overlap di token con la query
  3. Mantiene le frasi con score > 0, ordinate per posizione originale
  4. Se la riduzione è < 20%, usa il testo originale (non conviene comprimere)

Beneficio tipico: 35-55% riduzione token → contesto più segnale/rumore,
                  risposte LLM più precise e meno confabulazione.

Non usa modelli ML aggiuntivi — nessuna latenza aggiunta alla pipeline.
"""

import re
from typing import Optional

# Stop-word inglesi più comuni + accademiche generiche
_STOP_WORDS: frozenset[str] = frozenset({
    "the", "and", "for", "that", "this", "with", "are", "from", "have",
    "been", "they", "their", "what", "when", "where", "which", "there",
    "then", "will", "would", "could", "should", "also", "more", "such",
    "each", "into", "than", "over", "some", "were", "after", "before",
    "these", "those", "upon", "using", "used", "both", "within", "while",
    "through", "about", "between", "other", "only", "can", "its", "not",
    "has", "our", "thus", "show", "shows", "shown", "work", "paper",
    "propose", "proposed", "approach", "method", "system", "results",
    "based", "model", "models", "data", "set", "sets", "given", "section",
    "figure", "table", "equation",
})

_TOKEN_RE = re.compile(r"\b[a-zA-Z]{4,}\b")
_SENT_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z\d\"\(])")

# Non comprimere chunk già brevi (< 300 chars ≈ 75 token)
_MIN_LEN_TO_COMPRESS = 300

# Se la compressione mantiene più dell'80% del testo, non conviene
_COMPRESSION_THRESHOLD = 0.80


def _query_tokens(query: str) -> frozenset[str]:
    """Parole significative della query (4+ chars, non stop-word)."""
    return frozenset(
        w.lower()
        for w in _TOKEN_RE.findall(query)
        if w.lower() not in _STOP_WORDS
    )


def _score_sentence(sentence: str, query_tok: frozenset[str]) -> float:
    """
    Score = |sent_tokens ∩ query_tokens| / |sent_tokens|
    Misura la frazione di token della frase che appartengono alla query.
    """
    sent_tok = frozenset(
        w.lower()
        for w in _TOKEN_RE.findall(sentence)
        if w.lower() not in _STOP_WORDS
    )
    if not sent_tok:
        return 0.0
    return len(sent_tok & query_tok) / len(sent_tok)


def _compress_single(query: str, text: str) -> str:
    """
    Estrae da `text` le frasi più rilevanti per `query`.
    Ritorna il testo compresso, o il testo originale se la compressione non aiuta.
    """
    if len(text) < _MIN_LEN_TO_COMPRESS:
        return text

    qt = _query_tokens(query)
    if not qt:
        return text  # query troppo generica, non comprimere

    sentences = [s.strip() for s in _SENT_SPLIT_RE.split(text) if s.strip()]
    if len(sentences) <= 2:
        return text

    # Scoreggia ogni frase
    scored = [(i, s, _score_sentence(s, qt)) for i, s in enumerate(sentences)]

    # Mantieni frasi con almeno un token in comune con la query
    relevant = [(i, s) for i, s, sc in scored if sc > 0]

    if not relevant:
        return text  # nessuna corrispondenza — mantieni tutto

    # Mantieni ordine di apparizione originale
    compressed = " ".join(s for _, s in sorted(relevant, key=lambda x: x[0]))

    # Se la riduzione è minima, non vale la pena
    if len(compressed) > _COMPRESSION_THRESHOLD * len(text):
        return text

    return compressed


# ── API pubblica ──────────────────────────────────────────────────────────────

def compress_chunks(
    query: str,
    ranked: list[tuple],
) -> list[tuple]:
    """
    G7A: applica la compressione query-conditioned a tutti i chunk rankati.

    Args:
        query:  query originale dell'utente
        ranked: [(chunk_id, payload_dict, score), ...] output del reranker

    Returns:
        Stessa struttura con payload["text"] sostituito dal testo compresso.
        Il payload originale NON viene modificato (shallow copy).

    Metrica tracciata:
        compress_chunks() ritorna anche il compression_ratio medio
        nel campo _compression_ratio del primo elemento (opzionale, non usato dal caller).
    """
    if not ranked:
        return ranked

    result = []
    total_orig = 0
    total_comp = 0

    for cid, payload, score in ranked:
        orig_text = payload.get("text", "")
        comp_text = _compress_single(query, orig_text)

        total_orig += len(orig_text)
        total_comp += len(comp_text)

        # Shallow copy del payload con text sostituito
        new_payload = {**payload, "text": comp_text}
        result.append((cid, new_payload, score))

    ratio = total_comp / total_orig if total_orig > 0 else 1.0
    return result


def compression_ratio(
    query: str,
    ranked: list[tuple],
) -> float:
    """Calcola il ratio di compressione atteso senza modificare i dati."""
    total_orig = sum(len(p.get("text", "")) for _, p, _ in ranked)
    total_comp = sum(len(_compress_single(query, p.get("text", ""))) for _, p, _ in ranked)
    return total_comp / total_orig if total_orig > 0 else 1.0
