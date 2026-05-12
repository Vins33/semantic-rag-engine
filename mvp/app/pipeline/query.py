"""
Pipeline di query.

Flusso:
  0. [F2] Intent Gate — bypass retrieval per query triviali; scala top_k per query complesse
  1. Embedding della query → Ollama
  2. [F3] HyDE — media query embedding + hypothetical document embedding
  3. [F5B] Cache semantica — se hit, ritorna risposta cached
  4. Vector search → Qdrant (top 4×K candidati)
  5. FTS ibrida → PostgreSQL (top 4×K candidati)
  6. Reciprocal Rank Fusion → top 2×K candidati fusi
  7. Cross-encoder re-ranking → top K chunk
  8. Build prompt con contesto
  9. Generazione → Ollama
  10. [H3] Grounding check — verifica claim vs contesto
  11. [G7B] Confabulation Guard — rileva numeri/date/citazioni non nel contesto
  12. [H4] Citation Validator — verifica citazioni doc/pagina nella risposta
  13. Risposta con sources citate + grounding + confabulation + citation info
"""

import time

from app.core import ollama
from app.core.audit import log_event
from app.core.cache import cache_get, cache_set
from app.pipeline.citation import validate_citations
from app.pipeline.compress import compress_chunks
from app.pipeline.confabulation import check_confabulation
from app.core.config import settings
from app.pipeline.controller import run as controller_run
from app.pipeline.expansion import expand_query
from app.pipeline.grounding import check_grounding
from app.pipeline.hyde import hyde_embedding
from app.pipeline.intent import analyze_intent
from app.core.monitoring import (
    cache_hits_total, confabulation_total, query_latency,
    retrieval_count, token_budget_cuts_total,
)
from app.pipeline.rerank import rerank
from app.pipeline.s2g import evaluate as s2g_evaluate
from app.storage import db, vector as vec_store
from app.storage import opensearch as os_store
from app.pipeline.token_budget import enforce_budget
from app.indexing.tree_retrieval import retrieve_tree

# ── Prompt template ───────────────────────────────────────────────────────────

from app.prompts.rag import RAG_ANSWER as _PROMPT


# ── RRF ───────────────────────────────────────────────────────────────────────

def _reciprocal_rank_fusion(
    vector_hits: list,
    fts_hits: list[dict],
    k: int = 60,
    tree_hits: list[tuple] | None = None,
) -> list[tuple[str, dict, float]]:
    """
    Combina i ranking vettoriale, BM25 e Tree con Reciprocal Rank Fusion.
    Ritorna [(chunk_id, payload_dict, rrf_score), ...] in ordine decrescente.
    """
    scores: dict[str, float] = {}
    data:   dict[str, dict]  = {}

    for rank, hit in enumerate(vector_hits):
        cid = hit.payload["chunk_id"]
        scores[cid] = scores.get(cid, 0.0) + 1.0 / (k + rank + 1)
        data[cid] = {
            "chunk_id":   cid,
            "doc_id":     hit.payload["doc_id"],
            "filename":   hit.payload.get("filename", ""),
            "text":       hit.payload.get("text", ""),
            "page_start": hit.payload.get("page_start", 0),
        }

    for rank, row in enumerate(fts_hits):
        cid = row["chunk_id"]
        scores[cid] = scores.get(cid, 0.0) + 1.0 / (k + rank + 1)
        if cid not in data:
            data[cid] = {
                "chunk_id":    cid,
                "doc_id":      row["doc_id"],
                "filename":    row["filename"],
                "text":        row["text"],
                "page_start":  row["page_start"],
                "bm25_source": row.get("bm25_source", "postgres"),
            }

    # G4 — Tree hits (opzionale)
    if tree_hits:
        for rank, (cid, payload, _) in enumerate(tree_hits):
            scores[cid] = scores.get(cid, 0.0) + 1.0 / (k + rank + 1)
            if cid not in data:
                data[cid] = payload

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return [(cid, data[cid], score) for cid, score in ranked]


def _add_tree_hits_to_rrf(
    scores: dict, data: dict, tree_hits: list[tuple], k: int
) -> None:
    """Aggiunge i tree hit allo score/data dict dell'RRF (in-place)."""
    for rank, (cid, payload, _) in enumerate(tree_hits):
        scores[cid] = scores.get(cid, 0.0) + 1.0 / (k + rank + 1)
        if cid not in data:
            data[cid] = payload


# ── Pipeline principale ───────────────────────────────────────────────────────

async def answer_query(query: str, top_k: int | None = None, filters=None) -> dict:
    k = top_k or settings.top_k
    _t0 = time.monotonic()

    # 0. F2 — Intent Gate
    intent = analyze_intent(query)
    if not intent.retrieval_needed:
        return {
            "answer":        intent.direct_answer,
            "sources":       [],
            "model":         "intent_gate",
            "cache_hit":     False,
            "grounding":     {"grounded": True, "score": 1.0, "ungrounded_count": 0},
            "confabulation": {"has_confabulation": False, "confidence": 1.0, "flags": []},
            "citation":      {"valid_citations": [], "invalid_citations": [], "citation_coverage": 1.0, "all_valid": True},
            "intent":        {"complexity": intent.complexity, "tags": intent.intent_tags},
        }

    # Scala top_k in base alla complessità (1.5x per query complesse)
    k = int(k * intent.top_k_multiplier)

    # 1. Embedding query (+ HyDE per migliorare recall)
    query_vector = await hyde_embedding(query)

    # 2. Cache check — se risposta simile in cache, ritorna subito
    cached = cache_get(query_vector)
    if cached is not None:
        cache_hits_total.inc()
        query_latency.observe(time.monotonic() - _t0)
        cached["cache_hit"] = True
        return cached

    # 3. G3 — Costruisci filtri metadata (se presenti nella request)
    qdrant_filter = None
    fts_domain = fts_lang = fts_doctype = None
    if filters is not None:
        qdrant_filter = vec_store.build_qdrant_filter(
            domain=getattr(filters, "domain", None),
            language=getattr(filters, "language", None),
            doc_type=getattr(filters, "doc_type", None),
            year_from=getattr(filters, "year_from", None),
            year_to=getattr(filters, "year_to", None),
        )
        fts_domain  = getattr(filters, "domain",   None)
        fts_lang    = getattr(filters, "language", None)
        fts_doctype = getattr(filters, "doc_type", None)

    # 4. Vector search (candidati = k * 4, poi RRF riduce a k)
    vector_hits = vec_store.vector_search(query_vector, limit=k * 4, filt=qdrant_filter)
    retrieval_count.labels(source="vector").inc(len(vector_hits))

    # 5. F4 — Query Expansion per BM25/FTS
    expansion = expand_query(query)
    fts_query = expansion.expanded_query  # query arricchita con sinonimi

    # 6. G2 — BM25 search via OpenSearch (con query espansa + filtri)
    os_filters: dict = {}
    if fts_domain:  os_filters["domain"]   = fts_domain
    if fts_lang:    os_filters["language"] = fts_lang
    if fts_doctype: os_filters["doc_type"] = fts_doctype

    fts_hits = os_store.search_bm25(
        fts_query, k=k * 4,
        filters=os_filters if os_filters else None,
    )
    # Fallback a PostgreSQL FTS se OpenSearch non risponde
    if not fts_hits:
        fts_hits = db.fts_search(
            fts_query, limit=k * 4,
            domain=fts_domain, language=fts_lang, doc_type=fts_doctype,
        )
    retrieval_count.labels(source="bm25").inc(len(fts_hits))

    # 5. RRF fusion (vector + BM25 + Tree) → 2×K candidati pre-reranking
    tree_hits = retrieve_tree(query, k=k * 2)
    retrieval_count.labels(source="tree").inc(len(tree_hits))
    rrf_candidates = _reciprocal_rank_fusion(
        vector_hits, fts_hits, tree_hits=tree_hits
    )[:k * 2]

    # 6. Cross-encoder re-ranking → top K definitivi
    ranked = rerank(query, rrf_candidates)[:k]

    if not ranked:
        return {
            "answer":         "Nessun documento pertinente trovato nel corpus indicizzato.",
            "sources":        [],
            "model":          settings.chat_model,
            "cache_hit":      False,
            "grounding":      {"grounded": True, "score": 1.0, "ungrounded_count": 0},
        }

    # 7. G7A — Context compression query-conditioned
    compressed = compress_chunks(query, ranked)

    # 8. Build contesto (testo compresso) + sources (testo originale per preview)
    context_parts: list[str] = []
    sources: list[dict] = []

    for (cid, orig_payload, score), (_, comp_payload, _) in zip(ranked, compressed):
        orig_text = orig_payload["text"]
        comp_text = comp_payload["text"]
        context_parts.append(
            f"[{orig_payload['filename']} | pag. {orig_payload['page_start']}]\n{comp_text}"
        )
        sources.append({
            "chunk_id":     cid,
            "doc_id":       orig_payload["doc_id"],
            "filename":     orig_payload["filename"],
            "page":         orig_payload["page_start"],
            "text_preview": orig_text[:200] + ("…" if len(orig_text) > 200 else ""),
            "score":        round(score, 4),
            "bm25_source":  orig_payload.get("bm25_source", "vector"),
        })

    context = "\n\n---\n\n".join(context_parts)

    # I7 — Token Budget: comprimi contesto se supera il limite
    context, _budget_cut = enforce_budget(context, query)
    if _budget_cut:
        token_budget_cuts_total.inc()

    # F6A-D — Iterative Controller: S2G quality gate + sub-query decomposer + contradiction check
    s2g_result = await s2g_evaluate(query, context)

    async def _retrieval_fn(sub_query: str) -> str:
        """Closure usata dal controller per re-retrieve contesto aggiuntivo."""
        sub_vec = await hyde_embedding(sub_query)
        sub_vec_hits  = vec_store.vector_search(sub_vec, limit=k * 2, filt=qdrant_filter)
        sub_bm25_hits = os_store.search_bm25(sub_query, k=k * 2, filters=os_filters if os_filters else None)
        sub_rrf = _reciprocal_rank_fusion(sub_vec_hits, sub_bm25_hits)[:k]
        return "\n\n".join(
            f"[{p['filename']} | pag. {p['page_start']}]\n{p['text'][:300]}"
            for _, p, _ in sub_rrf
        )

    ctrl = await controller_run(
        query=query,
        initial_context=context,
        retrieval_fn=_retrieval_fn,
        initial_s2g_score=s2g_result["score"],
    )
    # Usa il contesto (potenzialmente arricchito) del controller
    context = ctrl.final_context

    prompt  = _PROMPT.format(context=context, query=query)

    # 9. Generazione
    answer = await ollama.generate(prompt)

    # 10. Grounding check — verifica vs testo compresso (ciò che ha ricevuto il LLM)
    grounding = check_grounding(answer, [p["text"] for _, p, _ in compressed])

    # 11. G7B — Confabulation Guard
    confab = check_confabulation(answer, [p["text"] for _, p, _ in compressed])
    final_answer = confab.filtered_answer  # aggiunge warning se confabulato
    if confab.has_confabulation:
        confabulation_total.inc()

    # 12. H4 — Citation Validator
    citation_result = validate_citations(final_answer, sources)

    result = {
        "answer":        final_answer.strip(),
        "sources":       sources,
        "model":         settings.chat_model,
        "cache_hit":     False,
        "grounding":     grounding,
        "confabulation": {
            "has_confabulation": confab.has_confabulation,
            "confidence":        confab.confidence,
            "flags":             confab.flags,
        },
        "citation": {
            "valid_citations":   citation_result.valid_citations,
            "invalid_citations": citation_result.invalid_citations,
            "uncited_sources":   citation_result.uncited_sources,
            "citation_coverage": citation_result.citation_coverage,
            "all_valid":         citation_result.all_valid,
        },
        "intent": {
            "complexity":       intent.complexity,
            "tags":             intent.intent_tags,
            "expansion_terms":  expansion.expansion_terms,
        },
        "controller": {
            "iterations":       ctrl.iterations,
            "s2g_scores":       ctrl.s2g_scores,
            "used_decomposer":  ctrl.used_decomposer,
            "sub_queries":      ctrl.sub_queries,
            "contradictions":   ctrl.contradictions,
        },
        "tree_retrieval": {
            "nodes_traversed": len(tree_hits),
        },
    }

    # I3 — registra latenza query
    query_latency.observe(time.monotonic() - _t0)

    # 11. Salva in cache semantica
    cache_set(query, query_vector, result)

    # 13. E6 — Audit log query
    log_event("query", None, {
        "query":          query[:200],
        "k":              len(ranked),
        "doc_ids":        list({p["doc_id"] for _, p, _ in ranked}),
        "grounded":       grounding["grounded"],
        "confabulated":   confab.has_confabulation,
        "intent":         intent.complexity,
        "filters":        str(filters) if filters else None,
    })

    return result
