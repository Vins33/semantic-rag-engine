"""
F4 — Query Expansion

Espande la query originale usando:
  - C1 (Vocabulary): normalizzazione acronimi e alias
  - C3 (Thesaurus): aggiunta sinonimi e termini correlati

Strategia "soft expansion":
  - I termini espansi aumentano il recall BM25 senza sostituire la query originale
  - Il vettore query originale (HyDE) non viene modificato
  - L'espansione agisce SOLO sulla query BM25/FTS, non sull'embedding

Output: QueryExpansion con
  - original_query: str
  - expanded_query: str      (per BM25/FTS — aggiunte parole chiave)
  - normalized_query: str    (acronimi espansi, es. "RAG" → "retrieval augmented generation RAG")
  - expansion_terms: list[str]  (termini aggiunti)
"""

import json
import os
import re
from dataclasses import dataclass, field
from functools import lru_cache

# ── Caricamento dati C1 e C3 ─────────────────────────────────────────────────

_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data")

@lru_cache(maxsize=1)
def _load_vocabulary() -> dict:
    path = os.path.join(_DATA_DIR, "vocabulary.json")
    with open(path, encoding="utf-8") as f:
        return json.load(f)

@lru_cache(maxsize=1)
def _load_thesaurus() -> dict:
    path = os.path.join(_DATA_DIR, "thesaurus.json")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _build_alias_map() -> dict[str, str]:
    """Costruisce mappa alias → termine preferito dal vocabolario C1."""
    vocab = _load_vocabulary()
    alias_map: dict[str, str] = {}
    for term in vocab.get("terms", []):
        preferred = term["preferred"]
        for alias in term.get("aliases", []):
            alias_map[alias.lower()] = preferred
    return alias_map

def _build_synonym_map() -> dict[str, list[str]]:
    """Costruisce mappa termine → [sinonimi + termini correlati] dal thesaurus C3."""
    thesaurus = _load_thesaurus()
    synonym_map: dict[str, list[str]] = {}
    for entry in thesaurus.get("entries", []):
        term = entry["term"].lower()
        expansions = (
            entry.get("synonyms", []) +
            entry.get("related", [])[:3]  # max 3 termini correlati
        )
        synonym_map[term] = [e.lower() for e in expansions]
    return synonym_map


@dataclass
class QueryExpansion:
    original_query: str
    expanded_query: str
    normalized_query: str
    expansion_terms: list[str] = field(default_factory=list)


def expand_query(query: str) -> QueryExpansion:
    """
    Espande la query per BM25/FTS.
    Sincrono, nessuna chiamata LLM, latenza < 1ms.
    
    Args:
        query: query originale dell'utente
    
    Returns:
        QueryExpansion con query espansa e termini aggiunti
    """
    alias_map = _build_alias_map()
    synonym_map = _build_synonym_map()

    query_lower = query.lower()
    expansion_terms: list[str] = []

    # 1. Normalizzazione acronimi (C1)
    # Espandi acronimi noti nella query (es. "RAG" → "retrieval augmented generation")
    normalized_query = query
    for alias, preferred in alias_map.items():
        # Cerca alias come parola intera (case-insensitive)
        pattern = re.compile(r'\b' + re.escape(alias) + r'\b', re.I)
        if pattern.search(query):
            # Aggiungi forma espansa se diversa dall'alias
            if alias.lower() != preferred.lower():
                expansion_terms.append(preferred)

    # 2. Espansione sinonimi (C3)
    # Per ogni token della query, cerca sinonimi nel thesaurus
    query_tokens = re.findall(r'\b\w+\b', query_lower)
    seen_expansions: set[str] = set(expansion_terms)

    for token in query_tokens:
        if len(token) < 3:
            continue
        if token in synonym_map:
            for syn in synonym_map[token]:
                if syn not in seen_expansions and syn not in query_lower:
                    expansion_terms.append(syn)
                    seen_expansions.add(syn)

    # 3. Cerca corrispondenze parziali nel thesaurus (frasi multi-parola)
    for term, synonyms in synonym_map.items():
        if term in query_lower and len(term) > 4:
            for syn in synonyms[:2]:  # max 2 sinonimi per termine multi-parola
                if syn not in seen_expansions and syn not in query_lower:
                    expansion_terms.append(syn)
                    seen_expansions.add(syn)

    # 4. Costruisci query espansa (originale + termini aggiuntivi)
    # Limita a max 8 termini di espansione per non diluire troppo
    expansion_terms = expansion_terms[:8]

    if expansion_terms:
        expanded_query = query + " " + " ".join(expansion_terms)
    else:
        expanded_query = query

    # Normalizzazione: sostituisce acronimi nella query con "acronimo forma_estesa"
    normalized_query = query
    for alias, preferred in alias_map.items():
        if len(alias) <= 6:  # Solo per acronimi corti
            pattern = re.compile(r'\b' + re.escape(alias) + r'\b', re.I)
            if pattern.search(normalized_query):
                normalized_query = pattern.sub(f"{alias} {preferred}", normalized_query)

    return QueryExpansion(
        original_query=query,
        expanded_query=expanded_query,
        normalized_query=normalized_query,
        expansion_terms=expansion_terms,
    )
