"""
I3 — Prometheus Metrics.

Metriche esposte:
  rag_query_latency_seconds    — histogram latenza query end-to-end
  rag_retrieval_count_total    — counter recuperi per sorgente (vector/bm25/tree)
  rag_confabulation_total      — counter confabulazioni rilevate
  rag_cache_hits_total         — counter cache hit (Redis semantic)
  rag_ingest_total             — counter documenti ingestiti
  rag_token_budget_cuts_total  — counter compressionie extra da token budget
  rag_eval_faithfulness        — gauge faithfulness media (RAGAS)
  rag_eval_relevancy           — gauge answer relevancy media (RAGAS)
  rag_eval_recall              — gauge context recall media (RAGAS)

Endpoint: GET /metrics  (montato in main.py via make_asgi_app)
"""

from prometheus_client import (
    Counter,
    Gauge,
    Histogram,
    make_asgi_app,
    REGISTRY,
)
import time
import functools
from typing import Callable

# ── Definizioni metriche ───────────────────────────────────────────────────────

query_latency = Histogram(
    "rag_query_latency_seconds",
    "Latenza end-to-end delle query RAG (secondi)",
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0],
)

retrieval_count = Counter(
    "rag_retrieval_count_total",
    "Numero di chunk recuperati per sorgente",
    labelnames=["source"],   # vector | bm25 | tree
)

confabulation_total = Counter(
    "rag_confabulation_total",
    "Numero di risposte con confabulazione rilevata",
)

cache_hits_total = Counter(
    "rag_cache_hits_total",
    "Numero di risposte servite dalla cache semantica Redis",
)

ingest_total = Counter(
    "rag_ingest_total",
    "Numero di documenti ingestiti con successo",
    labelnames=["doc_type"],  # pdf | markdown
)

token_budget_cuts_total = Counter(
    "rag_token_budget_cuts_total",
    "Numero di richieste compresse dal token budget",
)

eval_faithfulness = Gauge(
    "rag_eval_faithfulness",
    "Faithfulness media RAGAS (rolling average)",
)

eval_relevancy = Gauge(
    "rag_eval_relevancy",
    "Answer relevancy media RAGAS (rolling average)",
)

eval_recall = Gauge(
    "rag_eval_recall",
    "Context recall media RAGAS (rolling average)",
)

# ── Rolling average helper ─────────────────────────────────────────────────────
_eval_state: dict = {
    "faithfulness": [], "relevancy": [], "recall": [],
}
_MAX_WINDOW = 100


def record_eval(faithfulness: float, relevancy: float, recall: float):
    """Aggiorna le Gauge RAGAS con rolling average."""
    for key, val in [("faithfulness", faithfulness), ("relevancy", relevancy), ("recall", recall)]:
        _eval_state[key].append(val)
        if len(_eval_state[key]) > _MAX_WINDOW:
            _eval_state[key].pop(0)

    avg_f = sum(_eval_state["faithfulness"]) / len(_eval_state["faithfulness"])
    avg_r = sum(_eval_state["relevancy"]) / len(_eval_state["relevancy"])
    avg_c = sum(_eval_state["recall"]) / len(_eval_state["recall"])

    eval_faithfulness.set(avg_f)
    eval_relevancy.set(avg_r)
    eval_recall.set(avg_c)


# ── ASGI app per /metrics ──────────────────────────────────────────────────────
metrics_app = make_asgi_app()
