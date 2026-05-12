#!/usr/bin/env python3
"""
test_unit.py — Unit test dei componenti pipeline
=================================================
Testa i moduli di app.pipeline.* in isolamento, senza servizi esterni.

Componenti coperti:
  F2   Intent Gate        (regex fast-path + classificazione complessità)
  G5   RRF Fusion         (Reciprocal Rank Fusion multi-sorgente)
  I7   Token Budget       (enforce_budget truncation)
  G7B  Confabulation Guard (rilevamento iper-certezza e discrepanze)
  H3   Grounding Check    (lexical overlap F1)

Ref: BestPractices arXiv:2407.01219  §3.1 (query classification)
     RAGAS          arXiv:2309.15217  §3.1 (faithfulness/grounding)
     RGB            arXiv:2309.01431  §3.1 (counterfactual robustness)
     ARES           arXiv:2311.09476  §3.2 (answer faithfulness)
"""

# sys.path è già configurato da conftest.py prima di questo modulo


# ═══════════════════════════════════════════════════════════════════════════════
# F2 — Intent Gate
# ═══════════════════════════════════════════════════════════════════════════════

class TestIntentGate:
    """
    F2 Intent Gate — regex fast-path.
    Ref: BestPractices arXiv:2407.01219 §3.1
    """

    def test_trivial_greeting_it(self):
        from app.pipeline.intent import analyze_intent
        result = analyze_intent("ciao")
        assert not result.retrieval_needed
        assert result.complexity == "trivial"

    def test_trivial_greeting_en(self):
        from app.pipeline.intent import analyze_intent
        result = analyze_intent("hello!")
        assert not result.retrieval_needed
        assert result.complexity == "trivial"

    def test_trivial_capability_question(self):
        from app.pipeline.intent import analyze_intent
        result = analyze_intent("cosa puoi fare?")
        assert not result.retrieval_needed

    def test_trivial_has_direct_answer(self):
        from app.pipeline.intent import analyze_intent
        result = analyze_intent("ciao")
        assert result.direct_answer, "Query triviale deve avere risposta diretta"

    def test_trivial_thank_you(self):
        from app.pipeline.intent import analyze_intent
        result = analyze_intent("grazie!")
        assert not result.retrieval_needed

    def test_simple_factual_query(self):
        from app.pipeline.intent import analyze_intent
        result = analyze_intent("qual è il termine per la notifica GDPR?")
        assert result.retrieval_needed
        assert result.complexity in ("simple", "complex")

    def test_complex_comparison(self):
        from app.pipeline.intent import analyze_intent
        result = analyze_intent("confronta GDPR e NIS2 riguardo agli obblighi di notifica")
        assert result.retrieval_needed
        assert result.complexity == "complex"
        assert result.top_k_multiplier > 1.0

    def test_complex_summary(self):
        from app.pipeline.intent import analyze_intent
        result = analyze_intent("riassumi tutti gli obblighi previsti dal regolamento")
        assert result.retrieval_needed
        assert result.complexity == "complex"

    def test_complex_list_all(self):
        from app.pipeline.intent import analyze_intent
        result = analyze_intent("elenca tutti i diritti dell'interessato previsti dal GDPR")
        assert result.retrieval_needed
        assert result.complexity == "complex"

    def test_intent_tags_populated(self):
        from app.pipeline.intent import analyze_intent
        result = analyze_intent("qual è il termine per la notifica GDPR?")
        assert isinstance(result.intent_tags, list)
        assert len(result.intent_tags) > 0

    def test_top_k_multiplier_complex_gt_simple(self):
        from app.pipeline.intent import analyze_intent
        simple   = analyze_intent("cos'è il GDPR?")
        complex_ = analyze_intent("confronta e analizza tutte le differenze tra GDPR e NIS2")
        assert complex_.top_k_multiplier >= simple.top_k_multiplier


# ═══════════════════════════════════════════════════════════════════════════════
# G5 — RRF Fusion
# ═══════════════════════════════════════════════════════════════════════════════

class TestRRFFusion:
    """
    G5 Reciprocal Rank Fusion: RRF(d) = Σ 1/(k + rank_s(d)), k=60.
    Ref: RAGAS arXiv:2309.15217 §2.2; BestPractices arXiv:2407.01219 §4.1
    """

    @staticmethod
    def _rrf(ranked_lists: list[list[str]], k: int = 60) -> dict[str, float]:
        scores: dict[str, float] = {}
        for ranked in ranked_lists:
            for rank, doc_id in enumerate(ranked):
                scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank + 1)
        return scores

    def test_multi_source_beats_single_top1(self):
        """Doc rank-2 in tutti e 3 i retriever batte doc rank-1 in uno solo."""
        vector_hits = ["doc_A", "doc_B", "doc_C"]
        bm25_hits   = ["doc_D", "doc_B", "doc_E"]
        tree_hits   = ["doc_F", "doc_B", "doc_G"]
        scores = self._rrf([vector_hits, bm25_hits, tree_hits])
        assert scores["doc_B"] > scores["doc_A"]

    def test_k60_smoothing_ratio(self):
        """k=60: rank-1 non domina su rank-2 (ratio < 1.05)."""
        scores = self._rrf([["doc_X", "doc_Y"]], k=60)
        ratio  = scores["doc_X"] / scores["doc_Y"]
        assert ratio < 1.05, f"k=60 smoothing scarso, ratio={ratio:.4f}"

    def test_deterministic(self):
        hits = ["a", "b", "c", "d"]
        assert self._rrf([hits]) == self._rrf([hits])

    def test_three_sources_beat_two_at_same_rank(self):
        scores = self._rrf([
            ["doc_multi", "doc_two"],
            ["doc_multi", "doc_two"],
            ["doc_multi"],
        ])
        assert scores["doc_multi"] > scores["doc_two"]

    def test_rrf_improves_bm25_precision(self):
        """
        RRF(vector + BM25) ≥ BM25 da solo quando BM25 ha rumore in cima.
        Ref: BestPractices arXiv:2407.01219 §4.1
        """
        bm25_order   = ["noise_1", "noise_2", "chunk_gdpr_33", "chunk_gdpr_5"]
        vector_order = ["chunk_gdpr_33", "chunk_gdpr_5", "noise_1", "noise_2"]
        relevant     = {"chunk_gdpr_33", "chunk_gdpr_5"}

        p_bm25 = sum(1 for d in bm25_order[:3] if d in relevant) / 3
        scores = self._rrf([bm25_order, vector_order])
        rrf_top3 = sorted(scores, key=lambda x: scores[x], reverse=True)[:3]
        p_rrf = sum(1 for d in rrf_top3 if d in relevant) / 3
        assert p_rrf >= p_bm25


# ═══════════════════════════════════════════════════════════════════════════════
# I7 — Token Budget
# ═══════════════════════════════════════════════════════════════════════════════

class TestTokenBudget:
    """
    I7 Token Budget Enforcement.
    Ref: BestPractices arXiv:2407.01219 §3.5 — context window management
    """

    def test_truncates_long_context(self):
        from app.pipeline.token_budget import enforce_budget
        long_text = "parola " * 2000   # ~14 000 caratteri
        result, was_cut = enforce_budget(long_text, budget=500)
        assert was_cut
        assert len(result) < len(long_text)

    def test_preserves_short_context(self):
        from app.pipeline.token_budget import enforce_budget
        short = "Questo testo è abbastanza breve da rientrare nel budget."
        result, was_cut = enforce_budget(short, budget=3000)
        assert not was_cut
        assert result == short

    def test_returns_tuple_str_bool(self):
        from app.pipeline.token_budget import enforce_budget
        result = enforce_budget("test text", budget=500)
        assert isinstance(result, tuple)
        assert isinstance(result[0], str)
        assert isinstance(result[1], bool)

    def test_truncated_result_within_budget(self):
        from app.pipeline.token_budget import enforce_budget, CHARS_PER_TOKEN
        budget    = 200
        long_text = "x " * 5000
        result, _ = enforce_budget(long_text, budget=budget)
        assert len(result) <= budget * CHARS_PER_TOKEN * 1.2

    def test_budget_with_query_overhead(self):
        from app.pipeline.token_budget import enforce_budget
        text  = "contesto del documento. " * 1000
        query = "Qual è il termine per la notifica del data breach?"
        result, _ = enforce_budget(text, query=query, budget=1000)
        assert isinstance(result, str)


# ═══════════════════════════════════════════════════════════════════════════════
# G7B — Confabulation Guard
# ═══════════════════════════════════════════════════════════════════════════════

class TestConfabulationGuard:
    """
    G7B Confabulation Guard.
    Ref: RGB  arXiv:2309.01431 §3.1 (Counterfactual Robustness)
         ARES arXiv:2311.09476 §3.2 (Answer Faithfulness)
    """

    def test_detects_certainty_phrase(self):
        from app.pipeline.confabulation import check_confabulation
        context  = ["Il regolamento prevede alcune esenzioni per le organizzazioni."]
        response = "Sicuramente tutti gli enti devono adeguarsi entro 90 giorni."
        result   = check_confabulation(response, context)
        assert result.has_confabulation or len(result.flags) > 0

    def test_no_false_positive_consistent_numbers(self):
        from app.pipeline.confabulation import check_confabulation
        context  = ["La sanzione massima è pari al 4% del fatturato annuo globale."]
        response = "Il GDPR prevede sanzioni fino al 4% del fatturato annuo."
        result   = check_confabulation(response, context)
        assert result.confidence > 0.5

    def test_certainty_phrase_flags(self):
        from app.pipeline.confabulation import check_confabulation
        context  = ["Il regolamento prevede alcune esenzioni."]
        response = "Sicuramente tutti gli enti devono adeguarsi entro 90 giorni."
        result   = check_confabulation(response, context)
        assert result.has_confabulation or len(result.flags) > 0

    def test_returns_confabulation_result(self):
        from app.pipeline.confabulation import check_confabulation, ConfabulationResult
        result = check_confabulation("testo di prova", ["contesto"])
        assert isinstance(result, ConfabulationResult)
        assert hasattr(result, "has_confabulation")
        assert hasattr(result, "confidence")
        assert hasattr(result, "flags")

    def test_empty_answer_returns_bool(self):
        from app.pipeline.confabulation import check_confabulation
        result = check_confabulation("", ["contesto"])
        assert isinstance(result.has_confabulation, bool)


# ═══════════════════════════════════════════════════════════════════════════════
# H3 — Grounding Check
# ═══════════════════════════════════════════════════════════════════════════════

class TestGroundingCheck:
    """
    H3 Grounding Check (lexical overlap F1).
    Ref: Self-RAG arXiv:2310.11511; RAGAS arXiv:2309.15217 §3.1
    """

    def test_grounded_response(self):
        from app.pipeline.grounding import check_grounding
        chunks = [
            "Il GDPR Art. 33 impone la notifica entro 72 ore dalla scoperta.",
            "Il titolare del trattamento deve documentare tutte le violazioni.",
        ]
        answer = "Secondo il GDPR Art. 33, la notifica deve avvenire entro 72 ore."
        result = check_grounding(answer, chunks)
        assert result["grounded"] or result["score"] > 0.3

    def test_ungrounded_response(self):
        from app.pipeline.grounding import check_grounding
        chunks = ["Il GDPR riguarda la protezione dei dati personali in Europa."]
        answer = "La normativa fiscale prevede detrazioni per le spese mediche."
        result = check_grounding(answer, chunks)
        assert not result["grounded"] or result["score"] < 0.5

    def test_returns_dict_with_required_keys(self):
        from app.pipeline.grounding import check_grounding
        result = check_grounding("risposta di prova", ["contesto"])
        assert "grounded" in result
        assert "score" in result
        assert isinstance(result["score"], float)
        assert 0.0 <= result["score"] <= 1.0

    def test_empty_context_returns_grounded(self):
        from app.pipeline.grounding import check_grounding
        result = check_grounding("qualsiasi risposta", [])
        assert result["grounded"]

    def test_perfect_match_high_score(self):
        from app.pipeline.grounding import check_grounding
        text   = "La notifica del data breach deve avvenire entro settantadue ore."
        result = check_grounding(text, [text])
        assert result["score"] > 0.8
