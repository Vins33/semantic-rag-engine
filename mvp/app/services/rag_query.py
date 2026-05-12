"""
RagQueryService — incapsula l'intero pipeline di query RAG.

Responsabilità:
  - orchestrazione dei passi (intent, embed, cache, search, rerank, generate)
  - RRF fusion multi-sorgente
  - integrazione token budget + controller iterativo
  - Prometheus monitoring

Uso:
  service = RagQueryService()
  result = await service.answer(query, top_k=6, filters=None)
"""

import logging
import time
from typing import Optional

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
from app.core import ollama
from app.core.monitoring import (
    cache_hits_total, confabulation_total, query_latency,
    retrieval_count, token_budget_cuts_total,
)
from app.prompts.rag import RAG_ANSWER
from app.pipeline.rerank import rerank
from app.pipeline.s2g import evaluate as s2g_evaluate
from app.storage import db, vector as vec_store
from app.storage import opensearch as os_store
from app.pipeline.token_budget import enforce_budget
from app.indexing.tree_retrieval import retrieve_tree

logger = logging.getLogger(__name__)


class RagQueryService:
    """
    Orchestrates the full RAG query pipeline.

    Pipeline steps:
      0. Intent Gate (F2)
      1. HyDE embedding
      2. Semantic cache (F5B)
      3. Metadata filters (G3)
      4. Vector search
      5. Query expansion (F4) + BM25 (E3)
      6. Tree retrieval (G4)
      7. RRF fusion
      8. Cross-encoder rerank
      9. Context compression (G7A)
      10. Token budget (I7)
      11. Iterative controller (F6)
      12. Generation
      13. Grounding (H3), confabulation guard (G7B), citation validator (H4)
    """

    # ── RRF ──────────────────────────────────────────────────────────────────

    @staticmethod
    def _rrf(
        vector_hits: list,
        fts_hits: list[dict],
        k: int = 60,
        tree_hits: Optional[list[tuple]] = None,
    ) -> list[tuple[str, dict, float]]:
        """Reciprocal Rank Fusion across vector, BM25 and tree sources."""
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

        if tree_hits:
            for rank, (cid, payload, _) in enumerate(tree_hits):
                scores[cid] = scores.get(cid, 0.0) + 1.0 / (k + rank + 1)
                if cid not in data:
                    data[cid] = payload

        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return [(cid, data[cid], score) for cid, score in ranked]

    # ── Re-retrieval closure (for controller) ────────────────────────────────

    def _make_retrieval_fn(self, k: int, qdrant_filter, os_filters: dict):
        async def _retrieval_fn(sub_query: str) -> str:
            sub_vec = await hyde_embedding(sub_query)
            sub_vec_hits  = vec_store.vector_search(sub_vec, limit=k * 2, filt=qdrant_filter)
            sub_bm25_hits = os_store.search_bm25(
                sub_query, k=k * 2,
                filters=os_filters if os_filters else None,
            )
            sub_rrf = self._rrf(sub_vec_hits, sub_bm25_hits)[:k]
            return "\n\n".join(
                f"[{p['filename']} | pag. {p['page_start']}]\n{p['text'][:300]}"
                for _, p, _ in sub_rrf
            )
        return _retrieval_fn

    # ── Main entrypoint ──────────────────────────────────────────────────────

    async def answer(
        self,
        query: str,
        top_k: Optional[int] = None,
        filters=None,
    ) -> dict:
        k = top_k or settings.top_k
        t0 = time.monotonic()

        # 0. Intent Gate
        intent = analyze_intent(query)
        if not intent.retrieval_needed:
            query_latency.observe(time.monotonic() - t0)
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

        k = int(k * intent.top_k_multiplier)

        # 1. HyDE embedding
        query_vector = await hyde_embedding(query)

        # 2. Semantic cache
        cached = cache_get(query_vector)
        if cached is not None:
            cache_hits_total.inc()
            query_latency.observe(time.monotonic() - t0)
            cached["cache_hit"] = True
            return cached

        # 3. Metadata filters
        qdrant_filter = None
        fts_domain = fts_lang = fts_doctype = None
        os_filters: dict = {}
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
            if fts_domain:  os_filters["domain"]   = fts_domain
            if fts_lang:    os_filters["language"] = fts_lang
            if fts_doctype: os_filters["doc_type"] = fts_doctype

        # 4. Vector search
        vector_hits = vec_store.vector_search(query_vector, limit=k * 4, filt=qdrant_filter)
        retrieval_count.labels(source="vector").inc(len(vector_hits))

        # 5. BM25 search (+ query expansion)
        expansion  = expand_query(query)
        fts_query  = expansion.expanded_query
        fts_hits   = os_store.search_bm25(fts_query, k=k * 4, filters=os_filters if os_filters else None)
        if not fts_hits:
            fts_hits = db.fts_search(fts_query, limit=k * 4,
                                     domain=fts_domain, language=fts_lang, doc_type=fts_doctype)
        retrieval_count.labels(source="bm25").inc(len(fts_hits))

        # 6. Tree retrieval
        tree_hits = retrieve_tree(query, k=k * 2)
        retrieval_count.labels(source="tree").inc(len(tree_hits))

        # 7. RRF fusion → top 2×K
        rrf_candidates = self._rrf(vector_hits, fts_hits, tree_hits=tree_hits)[:k * 2]

        # 8. Cross-encoder rerank → top K
        ranked = rerank(query, rrf_candidates)[:k]
        if not ranked:
            query_latency.observe(time.monotonic() - t0)
            return {
                "answer":    "Nessun documento pertinente trovato nel corpus indicizzato.",
                "sources":   [],
                "model":     settings.chat_model,
                "cache_hit": False,
                "grounding": {"grounded": True, "score": 1.0, "ungrounded_count": 0},
            }

        # 9. Context compression
        compressed = compress_chunks(query, ranked)

        # Build context + sources
        context_parts: list[str] = []
        sources: list[dict] = []
        for (cid, orig, score), (_, comp, _) in zip(ranked, compressed):
            context_parts.append(
                f"[{orig['filename']} | pag. {orig['page_start']}]\n{comp['text']}"
            )
            sources.append({
                "chunk_id":     cid,
                "doc_id":       orig["doc_id"],
                "filename":     orig["filename"],
                "page":         orig["page_start"],
                "text_preview": orig["text"][:200] + ("…" if len(orig["text"]) > 200 else ""),
                "score":        round(score, 4),
                "bm25_source":  orig.get("bm25_source", "vector"),
            })

        context = "\n\n---\n\n".join(context_parts)

        # 10. Token budget
        context, was_cut = enforce_budget(context, query)
        if was_cut:
            token_budget_cuts_total.inc()

        # 11. Iterative controller (S2G + decomposer + contradiction check)
        s2g_result   = await s2g_evaluate(query, context)
        retrieval_fn = self._make_retrieval_fn(k, qdrant_filter, os_filters)
        ctrl = await controller_run(
            query=query,
            initial_context=context,
            retrieval_fn=retrieval_fn,
            initial_s2g_score=s2g_result["score"],
        )
        context = ctrl.final_context

        # 12. Generation
        prompt = RAG_ANSWER.format(context=context, query=query)
        answer = await ollama.generate(prompt)

        # 13. Grounding, confabulation, citation
        grounding = check_grounding(answer, [p["text"] for _, p, _ in compressed])
        confab    = check_confabulation(answer, [p["text"] for _, p, _ in compressed])
        final_answer = confab.filtered_answer
        if confab.has_confabulation:
            confabulation_total.inc()
        citation_result = validate_citations(final_answer, sources)

        query_latency.observe(time.monotonic() - t0)

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
                "complexity":      intent.complexity,
                "tags":            intent.intent_tags,
                "expansion_terms": expansion.expansion_terms,
            },
            "controller": {
                "iterations":      ctrl.iterations,
                "s2g_scores":      ctrl.s2g_scores,
                "used_decomposer": ctrl.used_decomposer,
                "sub_queries":     ctrl.sub_queries,
                "contradictions":  ctrl.contradictions,
            },
            "tree_retrieval": {
                "nodes_traversed": len(tree_hits),
            },
        }

        cache_set(query, query_vector, result)
        log_event("query", None, {
            "query":        query[:200],
            "k":            len(ranked),
            "doc_ids":      list({p["doc_id"] for _, p, _ in ranked}),
            "grounded":     grounding["grounded"],
            "confabulated": confab.has_confabulation,
            "intent":       intent.complexity,
            "filters":      str(filters) if filters else None,
        })

        return result
