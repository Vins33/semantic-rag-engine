#!/usr/bin/env python3
"""
conftest.py — Fixtures pytest per il Semantic RAG Engine test suite
====================================================================
Caricato automaticamente da pytest prima di qualsiasi file di test.

Responsabilità:
  • sys.path setup (mvp/ + tests/) — deve avvenire qui, prima degli import
  • Fixtures per i 5 scenari singoli (scope=session)
  • Fixture all_scenarios (scope=session)
  • Metrics report auto-use (scope=session) — stampato dopo tutti i test
"""

import sys
from pathlib import Path

import pytest

# ── sys.path: aggiunto qui (conftest è il primo file caricato da pytest) ──────
_TESTS_PATH = Path(__file__).resolve().parent
_MVP_PATH   = _TESTS_PATH.parent.parent / "mvp"
for _p in (_TESTS_PATH, _MVP_PATH):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from pipeline import (  # noqa: E402
    ALL_SCENARIOS,
    S1_GDPR, S2_NIS2, S3_AIACT, S4_DORA, S5_CCPA,
    precision_at_k, recall_at_k, mrr, ndcg_at_k, average_precision,
    faithfulness_proxy,
)


# ── Fixtures per scenario singolo ─────────────────────────────────────────────
@pytest.fixture(scope="session")
def scenario_gdpr():   return S1_GDPR

@pytest.fixture(scope="session")
def scenario_nis2():   return S2_NIS2

@pytest.fixture(scope="session")
def scenario_aiact():  return S3_AIACT

@pytest.fixture(scope="session")
def scenario_dora():   return S4_DORA

@pytest.fixture(scope="session")
def scenario_ccpa():   return S5_CCPA

@pytest.fixture(scope="session")
def all_scenarios():   return ALL_SCENARIOS


# ═══════════════════════════════════════════════════════════════════════════════
# METRICS REPORT — session-scoped, stampato dopo tutti i test
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture(scope="session", autouse=True)
def _metrics_report():
    """Riepilogo quantitativo metriche RAG per i 5 scenari (visibile con -s)."""
    yield   # ← eseguito DOPO che tutti i test sono completati

    def _ok(v: float, t: float) -> str:
        return "✓" if v >= t else "✗"

    def _warn(v: float, t: float) -> str:
        return f" ← BELOW ({t:.2f})" if v < t else ""

    W = 76
    print()
    print("═" * W)
    print("  SEMANTIC RAG ENGINE — PIPELINE METRICS REPORT  (5 scenari)")
    print("═" * W)

    for sc in ALL_SCENARIOS:
        p1    = precision_at_k(sc.retrieved, sc.relevant, 1)
        p3    = precision_at_k(sc.retrieved, sc.relevant, 3)
        p5    = precision_at_k(sc.retrieved, sc.relevant, 5)
        r3    = recall_at_k(sc.retrieved, sc.relevant, 3)
        r5    = recall_at_k(sc.retrieved, sc.relevant, 5)
        mrr_v = mrr(sc.retrieved, sc.relevant)
        n3    = ndcg_at_k(sc.retrieved, sc.relevant, 3)
        n5    = ndcg_at_k(sc.retrieved, sc.relevant, 5)
        ap    = average_precision(sc.retrieved, sc.relevant)
        # Faithfulness: usa i primi 120 caratteri del context come "risposta fedele"
        faith = faithfulness_proxy(sc.context[:120], sc.context)

        print()
        print(f"  [{sc.id}] {sc.name}")
        print(f"  Query: {sc.query[:68]}")
        print(f"  {'─' * (W - 4)}")
        print(
            f"  P@1={p1:.3f}  P@3={p3:.3f}{_warn(p3, 0.80):<18}"
            f"  P@5={p5:.3f}{_warn(p5, 0.80)}"
        )
        print(
            f"  R@3={r3:.3f}  R@5={r5:.3f}{_warn(r5, 1.00):<18}"
            f"  MRR={mrr_v:.3f}{_warn(mrr_v, 0.85)}"
        )
        print(
            f"  NDCG@3={n3:.3f}  NDCG@5={n5:.3f}{_warn(n5, 0.80):<14}"
            f"  MAP={ap:.3f}  Faith={faith:.3f}{_warn(faith, 0.90)}"
        )

    print()
    print("  ── Target (RAGAS arXiv:2309.15217) ────────────────────────────")
    print("  P@K ≥ 0.80   R@K ≥ 0.80   MRR ≥ 0.85   NDCG@5 ≥ 0.80   Faith ≥ 0.90")
    print()
    print("  ── Paper di riferimento ────────────────────────────────────────")
    print("  [RAGAS]          arXiv:2309.15217  Es et al. (2023)")
    print("  [RGB]            arXiv:2309.01431  Chen et al. (AAAI 2024)")
    print("  [ARES]           arXiv:2311.09476  Saad-Falcon et al. (NAACL 2024)")
    print("  [EnterpriseRAG]  arXiv:2605.05253  Sun et al. (2026)")
    print("  [BestPractices]  arXiv:2407.01219  Wang et al. (2024)")
    print("═" * W)
