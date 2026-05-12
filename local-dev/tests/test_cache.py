#!/usr/bin/env python3
"""
test_cache.py — Logica del semantic cache (F5B)
================================================
Testa il comportamento hit/miss della cache semantica senza Redis live.
Simula: cosine_similarity(query_embedding, cached_embedding) ≥ 0.92 → HIT.

Ref: BestPractices arXiv:2407.01219 §3.3 — caching strategies
"""

import math
import random
import pytest
from pipeline import cosine_sim, CACHE_THRESHOLD


# ═══════════════════════════════════════════════════════════════════════════════
# F5B — Semantic Cache Logic
# ═══════════════════════════════════════════════════════════════════════════════

class TestSemanticCacheLogic:
    """
    Verifica che la logica di threshold 0.92 separi correttamente HIT e MISS.
    """

    def test_identical_vectors_hit(self):
        vec = [0.1, 0.9, 0.3, 0.7, 0.5]
        assert cosine_sim(vec, vec) >= CACHE_THRESHOLD

    def test_orthogonal_vectors_miss(self):
        v1 = [1.0, 0.0, 0.0]
        v2 = [0.0, 1.0, 0.0]
        assert cosine_sim(v1, v2) < CACHE_THRESHOLD

    def test_near_duplicate_query_hits(self):
        """Parafasi della stessa domanda → vettori vicinissimi → cache HIT."""
        rng  = random.Random(7)
        base = [rng.random() for _ in range(128)]
        norm = math.sqrt(sum(x * x for x in base))
        base = [x / norm for x in base]

        perturbed = [v + rng.gauss(0, 0.005) for v in base]
        norm2 = math.sqrt(sum(x * x for x in perturbed))
        perturbed = [x / norm2 for x in perturbed]

        sim = cosine_sim(base, perturbed)
        assert sim > 0.99, f"Near-duplicate sim troppo bassa: {sim:.4f}"

    def test_different_topic_queries_miss(self):
        """Query su argomenti diversi → sim bassa → cache MISS."""
        v_gdpr    = [0.9, 0.1, 0.05, 0.8, 0.2, 0.3]
        v_finance = [0.1, 0.8, 0.90, 0.1, 0.7, 0.6]
        assert cosine_sim(v_gdpr, v_finance) < CACHE_THRESHOLD

    def test_cosine_symmetry(self):
        v1 = [0.3, 0.7, 0.5, 0.2, 0.8]
        v2 = [0.5, 0.4, 0.9, 0.1, 0.6]
        assert abs(cosine_sim(v1, v2) - cosine_sim(v2, v1)) < 1e-9

    def test_self_similarity_is_one(self):
        v = [0.3, 0.7, 0.5, 0.2]
        assert abs(cosine_sim(v, v) - 1.0) < 1e-9

    def test_threshold_separates_hit_from_miss(self):
        """0.92 separa correttamente query identica (HIT) da query distante (MISS)."""
        rng = random.Random(42)
        base = [rng.random() for _ in range(64)]
        norm = math.sqrt(sum(x * x for x in base))
        base = [x / norm for x in base]

        # Identica → HIT
        assert cosine_sim(base, base) >= CACHE_THRESHOLD

        # Casuale → MISS
        other = [rng.random() for _ in range(64)]
        norm2 = math.sqrt(sum(x * x for x in other))
        other = [x / norm2 for x in other]
        assert cosine_sim(base, other) < CACHE_THRESHOLD

    def test_768dim_cosine_correctness(self):
        """Verifica cosine su vettori 768-dim (dimensione nomic-embed-text)."""
        rng = random.Random(99)
        v1 = [rng.random() for _ in range(768)]
        v2 = [rng.random() for _ in range(768)]

        # Calcolo di riferimento via dot product diretto
        dot   = sum(a * b for a, b in zip(v1, v2))
        n1    = math.sqrt(sum(a * a for a in v1))
        n2    = math.sqrt(sum(b * b for b in v2))
        expected = dot / (n1 * n2)

        assert abs(cosine_sim(v1, v2) - expected) < 1e-9


class TestCacheThreshold:
    """Test sul valore della soglia e i suoi effetti sul trade-off hit-rate / precision."""

    def test_threshold_is_0_92(self):
        assert CACHE_THRESHOLD == 0.92

    def test_below_threshold_is_miss(self):
        """sim = 0.91 < 0.92 → MISS."""
        # Costruiamo due vettori con sim controllata
        # v1 = (1, 0), v2 = (cos θ, sin θ) con θ tale che cos θ = 0.91
        import math as _m
        theta = _m.acos(0.91)
        v1 = [1.0, 0.0]
        v2 = [_m.cos(theta), _m.sin(theta)]
        sim = cosine_sim(v1, v2)
        assert abs(sim - 0.91) < 0.001
        assert sim < CACHE_THRESHOLD

    def test_above_threshold_is_hit(self):
        """sim = 0.95 > 0.92 → HIT."""
        import math as _m
        theta = _m.acos(0.95)
        v1 = [1.0, 0.0]
        v2 = [_m.cos(theta), _m.sin(theta)]
        sim = cosine_sim(v1, v2)
        assert abs(sim - 0.95) < 0.001
        assert sim >= CACHE_THRESHOLD
