#!/usr/bin/env python3
"""
test_retrieval.py — Metriche di retrieval su 5 scenari enterprise
=================================================================
Ogni classe di test è parametrizzata sui 5 scenari definiti in pipeline.py.
Per ogni scenario vengono calcolate: P@K, R@K, MRR, NDCG@K, MAP.

Struttura comune degli scenari:
  rank-1 = rilevante  rank-2 = rumore  rank-3 = rilevante
  rank-4 = rumore     rank-5 = rilevante
  → P@3=0.667  P@5=0.600  R@3=0.667  R@5=1.000
    MRR=1.000  NDCG@3≈0.704  NDCG@5≈0.885  MAP≈0.756

Target operativi (RAGAS arXiv:2309.15217):
  P@K ≥ 0.80   R@K ≥ 0.80   MRR ≥ 0.85   NDCG@5 ≥ 0.80

Ref:
  [RAGAS]  arXiv:2309.15217  Es et al. (2023)         §3.2
  [ARES]   arXiv:2311.09476  Saad-Falcon et al. (2024) §2
  [RGB]    arXiv:2309.01431  Chen et al. (AAAI 2024)   §2
"""

import math
import pytest
from pipeline import (
    ALL_SCENARIOS, Scenario,
    precision_at_k, recall_at_k, mrr, ndcg_at_k, average_precision,
)

_IDS = [s.id for s in ALL_SCENARIOS]


# ═══════════════════════════════════════════════════════════════════════════════
# PRECISION@K — 5 scenari × 3 valori di K
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("sc", ALL_SCENARIOS, ids=_IDS)
class TestPrecisionAtK:
    """Context Precision @K. Ref: RAGAS §3.2. Target ≥ 0.80."""

    def test_precision_at_1_is_1(self, sc: Scenario):
        """Il primo risultato è sempre rilevante in tutti gli scenari."""
        p = precision_at_k(sc.retrieved, sc.relevant, k=1)
        assert abs(p - 1.0) < 0.001, f"[{sc.id}] P@1 atteso 1.000, ottenuto {p:.3f}"

    def test_precision_at_3(self, sc: Scenario):
        """P@3 = 2 rilevanti su 3 → 0.667."""
        p = precision_at_k(sc.retrieved, sc.relevant, k=3)
        assert abs(p - 2/3) < 0.001, f"[{sc.id}] P@3 atteso 0.667, ottenuto {p:.3f}"

    def test_precision_at_5(self, sc: Scenario):
        """P@5 = 3 rilevanti su 5 → 0.600."""
        p = precision_at_k(sc.retrieved, sc.relevant, k=5)
        assert abs(p - 3/5) < 0.001, f"[{sc.id}] P@5 atteso 0.600, ottenuto {p:.3f}"

    def test_precision_decreases_from_1_to_5(self, sc: Scenario):
        """Con rumore a rank-2 e rank-4, P@5 < P@1."""
        p1 = precision_at_k(sc.retrieved, sc.relevant, k=1)
        p5 = precision_at_k(sc.retrieved, sc.relevant, k=5)
        assert p5 <= p1, f"[{sc.id}] P@5 non può superare P@1"


# ═══════════════════════════════════════════════════════════════════════════════
# RECALL@K
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("sc", ALL_SCENARIOS, ids=_IDS)
class TestRecallAtK:
    """Context Recall @K. Ref: RAGAS §3.2. Target R@5 ≥ 0.80."""

    def test_recall_at_3(self, sc: Scenario):
        """R@3 = 2 dei 3 rilevanti trovati → 0.667."""
        r = recall_at_k(sc.retrieved, sc.relevant, k=3)
        assert abs(r - 2/3) < 0.001, f"[{sc.id}] R@3 atteso 0.667, ottenuto {r:.3f}"

    def test_recall_at_5_full(self, sc: Scenario):
        """R@5 = tutti e 3 i rilevanti trovati → 1.000."""
        r = recall_at_k(sc.retrieved, sc.relevant, k=5)
        assert abs(r - 1.0) < 0.001, f"[{sc.id}] R@5 atteso 1.000, ottenuto {r:.3f}"

    def test_recall_monotone(self, sc: Scenario):
        """Recall non può diminuire all'aumentare di K."""
        r3 = recall_at_k(sc.retrieved, sc.relevant, k=3)
        r5 = recall_at_k(sc.retrieved, sc.relevant, k=5)
        assert r5 >= r3 - 1e-9, f"[{sc.id}] Recall non monotona: R@3={r3:.3f}, R@5={r5:.3f}"


# ═══════════════════════════════════════════════════════════════════════════════
# MRR — Mean Reciprocal Rank
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("sc", ALL_SCENARIOS, ids=_IDS)
class TestMRR:
    """Mean Reciprocal Rank. Ref: ARES arXiv:2311.09476 §2. Target ≥ 0.85."""

    def test_mrr_is_one(self, sc: Scenario):
        """Con il documento rilevante al rank-1, MRR = 1.000."""
        score = mrr(sc.retrieved, sc.relevant)
        assert abs(score - 1.0) < 0.001, f"[{sc.id}] MRR atteso 1.000, ottenuto {score:.3f}"

    def test_mrr_above_target(self, sc: Scenario):
        target = 0.85
        score  = mrr(sc.retrieved, sc.relevant)
        assert score >= target, f"[{sc.id}] MRR={score:.3f} sotto target {target}"


# ═══════════════════════════════════════════════════════════════════════════════
# NDCG@K
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("sc", ALL_SCENARIOS, ids=_IDS)
class TestNDCG:
    """NDCG@K con binary relevance. Ref: RAGAS §3.2. Target NDCG@5 ≥ 0.80."""

    def test_ndcg_at_3_in_range(self, sc: Scenario):
        n = ndcg_at_k(sc.retrieved, sc.relevant, k=3)
        assert 0.60 < n <= 1.0, f"[{sc.id}] NDCG@3 fuori range (0.60, 1.0]: {n:.3f}"

    def test_ndcg_at_5_above_target(self, sc: Scenario):
        n = ndcg_at_k(sc.retrieved, sc.relevant, k=5)
        assert n >= 0.80, f"[{sc.id}] NDCG@5={n:.3f} sotto target 0.80"

    def test_ndcg_at_5_ge_at_3(self, sc: Scenario):
        """Con rilevanti a rank-5, NDCG@5 ≥ NDCG@3."""
        n3 = ndcg_at_k(sc.retrieved, sc.relevant, k=3)
        n5 = ndcg_at_k(sc.retrieved, sc.relevant, k=5)
        assert n5 >= n3 - 1e-9, f"[{sc.id}] NDCG@5={n5:.3f} < NDCG@3={n3:.3f}"


# ═══════════════════════════════════════════════════════════════════════════════
# MAP — Mean Average Precision
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("sc", ALL_SCENARIOS, ids=_IDS)
class TestMAP:
    """Mean Average Precision. Ref: RGB arXiv:2309.01431 §2."""

    def test_map_range(self, sc: Scenario):
        ap = average_precision(sc.retrieved, sc.relevant)
        # AP = (1/1 + 2/3 + 3/5) / 3 ≈ 0.756
        assert 0.70 < ap < 0.90, f"[{sc.id}] MAP={ap:.3f} fuori range atteso (0.70, 0.90)"

    def test_map_value(self, sc: Scenario):
        ap = average_precision(sc.retrieved, sc.relevant)
        assert abs(ap - 0.756) < 0.01, f"[{sc.id}] MAP atteso ≈0.756, ottenuto {ap:.3f}"


# ═══════════════════════════════════════════════════════════════════════════════
# EDGE CASES — retrieval perfetto / retrieval pessimo / liste vuote
# ═══════════════════════════════════════════════════════════════════════════════

class TestRetrievalEdgeCases:
    """Test di limite per le funzioni metriche."""

    _RELEVANT = frozenset({"a", "b", "c"})

    def test_perfect_retrieval_all_ones(self):
        perfect = ["a", "b", "c", "noise"]
        assert precision_at_k(perfect, self._RELEVANT, k=3) == 1.0
        assert recall_at_k(perfect, self._RELEVANT, k=3)    == 1.0
        assert mrr(perfect, self._RELEVANT)                  == 1.0
        assert ndcg_at_k(perfect, self._RELEVANT, k=3)       == 1.0

    def test_worst_retrieval_all_zeros(self):
        worst = ["noise_1", "noise_2", "noise_3"]
        assert precision_at_k(worst, self._RELEVANT, k=3) == 0.0
        assert recall_at_k(worst, self._RELEVANT, k=3)    == 0.0
        assert mrr(worst, self._RELEVANT)                  == 0.0

    def test_empty_relevant_set(self):
        assert recall_at_k(["a", "b"], frozenset(), k=2)    == 0.0
        assert average_precision(["a", "b"], frozenset())   == 0.0

    def test_single_relevant_mrr_rank1(self):
        assert mrr(["rel", "noise_1", "noise_2"], frozenset({"rel"})) == 1.0

    def test_single_relevant_mrr_rank3(self):
        score = mrr(["noise_1", "noise_2", "rel"], frozenset({"rel"}))
        assert abs(score - 1/3) < 0.001

    def test_ndcg_perfect_ideal_case(self):
        """Retrieval ideale: NDCG = 1.0."""
        docs = ["a", "b", "c"]
        rel  = frozenset({"a", "b", "c"})
        assert abs(ndcg_at_k(docs, rel, k=3) - 1.0) < 1e-9

    def test_precision_k_equals_len(self):
        docs = ["a", "noise", "b"]
        rel  = frozenset({"a", "b"})
        p = precision_at_k(docs, rel, k=3)
        assert abs(p - 2/3) < 0.001
