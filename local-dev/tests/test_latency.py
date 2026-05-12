#!/usr/bin/env python3
"""
test_latency.py — Budget temporale dei componenti pipeline (senza servizi)
===========================================================================
Verifica che i componenti sincroni rispettino i budget di latenza.
Target architettura: P95 end-to-end < 5s; componenti leggeri < 5ms/query.

Ref: BestPractices arXiv:2407.01219 §5 — latency / efficiency trade-offs
"""

import time
import random
import pytest
from pipeline import cosine_sim, faithfulness_proxy, S1_GDPR


# ═══════════════════════════════════════════════════════════════════════════════
# Latency budgets
# ═══════════════════════════════════════════════════════════════════════════════

class TestLatencyBudgets:
    """
    Budget per componente (senza servizi):
      Intent Gate regex    < 5ms / query
      RRF Fusion           < 10ms su 100 candidati
      Cosine sim 768-dim   < 1000ms per 10k esecuzioni
      Faithfulness proxy   < 5ms / esecuzione
      Token Budget         < 5ms / esecuzione
    """

    _INTENT_MAX_MS  = 5
    _RRF_MAX_MS     = 10
    _COSINE_TOTAL_MS = 1000   # 10k esecuzioni su 768-dim
    _FAITH_MAX_MS   = 5
    _BUDGET_MAX_MS  = 5

    def test_intent_gate_latency(self):
        """Intent Gate regex: < 5ms / query (media su 100 query)."""
        from app.pipeline.intent import analyze_intent
        queries = [
            "ciao",
            "cos'è il GDPR?",
            "confronta GDPR e NIS2 sugli obblighi di notifica degli incidenti",
            "what is the data breach notification deadline under GDPR?",
            "riassumi tutti gli articoli del regolamento europeo sulla privacy",
            "quali sono i requisiti dell'AI Act per i sistemi ad alto rischio?",
            "elenca tutte le misure di resilienza previste da DORA",
            "hello",
            "grazie",
            "come funziona il sistema?",
        ] * 10  # 100 esecuzioni

        start = time.perf_counter()
        for q in queries:
            analyze_intent(q)
        elapsed_ms = (time.perf_counter() - start) * 1000 / len(queries)

        assert elapsed_ms < self._INTENT_MAX_MS, (
            f"Intent Gate troppo lento: {elapsed_ms:.3f}ms/query (max {self._INTENT_MAX_MS}ms)"
        )

    def test_rrf_fusion_latency(self):
        """RRF su 100 candidati × 2 liste: < 10ms per fusione (media su 1000 run)."""
        rng   = random.Random(0)
        docs  = [f"doc_{i}" for i in range(100)]
        list1 = docs[:]
        list2 = docs[:]
        rng.shuffle(list1)
        rng.shuffle(list2)

        start = time.perf_counter()
        for _ in range(1000):
            scores: dict[str, float] = {}
            for rank, d in enumerate(list1):
                scores[d] = scores.get(d, 0.0) + 1.0 / (60 + rank + 1)
            for rank, d in enumerate(list2):
                scores[d] = scores.get(d, 0.0) + 1.0 / (60 + rank + 1)
            sorted(scores.items(), key=lambda x: x[1], reverse=True)
        elapsed_ms = (time.perf_counter() - start) * 1000 / 1000

        assert elapsed_ms < self._RRF_MAX_MS, (
            f"RRF troppo lento: {elapsed_ms:.3f}ms (max {self._RRF_MAX_MS}ms)"
        )

    def test_cosine_similarity_768dim_latency(self):
        """Cosine sim su vettori 768-dim: < 1000ms per 10k esecuzioni."""
        rng = random.Random(1)
        v1  = [rng.random() for _ in range(768)]
        v2  = [rng.random() for _ in range(768)]

        start = time.perf_counter()
        for _ in range(10_000):
            cosine_sim(v1, v2)
        elapsed_ms = (time.perf_counter() - start) * 1000

        assert elapsed_ms < self._COSINE_TOTAL_MS, (
            f"Cosine sim 768-dim: {elapsed_ms:.0f}ms per 10k (max {self._COSINE_TOTAL_MS}ms)"
        )

    def test_faithfulness_proxy_latency(self):
        """Faithfulness proxy: < 5ms / esecuzione (media su 500)."""
        answer = (
            "Il GDPR Art. 33 prevede la notifica entro 72 ore. "
            "Il titolare deve documentare tutte le violazioni. "
            "Le sanzioni possono arrivare al 4% del fatturato."
        )
        start = time.perf_counter()
        for _ in range(500):
            faithfulness_proxy(answer, S1_GDPR.context)
        elapsed_ms = (time.perf_counter() - start) * 1000 / 500

        assert elapsed_ms < self._FAITH_MAX_MS, (
            f"Faithfulness proxy lenta: {elapsed_ms:.3f}ms/exec (max {self._FAITH_MAX_MS}ms)"
        )

    def test_token_budget_latency(self):
        """Token Budget enforce_budget: < 5ms / esecuzione (media su 500)."""
        from app.pipeline.token_budget import enforce_budget
        text = "contesto del documento con informazioni utili. " * 200  # ~9600 chars

        start = time.perf_counter()
        for _ in range(500):
            enforce_budget(text, budget=1000)
        elapsed_ms = (time.perf_counter() - start) * 1000 / 500

        assert elapsed_ms < self._BUDGET_MAX_MS, (
            f"Token Budget lento: {elapsed_ms:.3f}ms/exec (max {self._BUDGET_MAX_MS}ms)"
        )
