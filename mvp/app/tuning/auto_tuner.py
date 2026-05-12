"""
I8 — AutoRAGTuner.

Ottimizza gli iperparametri del sistema RAG basandosi sulle metriche RAGAS
accumulate nel tempo. Usa una ricerca a griglia semplice con esplorazione bayesiana
leggera (UCB1 — Upper Confidence Bound) sullo spazio degli iperparametri.

Iperparametri gestiti:
  top_k             : numero chunk recuperati (default 6, range 4-16)
  rerank_threshold  : soglia minima punteggio re-ranker (default 0.3, range 0.1-0.7)
  token_budget      : token massimi per contesto (default 3000, range 2000-6000)
  controller_iters  : iterazioni massime controller (default 3, range 1-5)

Endpoint: GET  /api/v1/tuner/params   → iperparametri attivi
          POST /api/v1/tuner/record   → registra metriche nuova osservazione
          POST /api/v1/tuner/optimize → ricalcola best config
"""

import json
import logging
import math
import os
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ── Storage in-memory + file JSON ─────────────────────────────────────────────
_HISTORY_PATH = os.environ.get(
    "TUNER_HISTORY_PATH",
    os.path.join(os.path.dirname(__file__), "..", "..", "data", "tuner_history.json"),
)

_history: list[dict] = []


def _load_history():
    global _history
    try:
        with open(_HISTORY_PATH) as f:
            _history = json.load(f)
        logger.info("tuner: caricata storia da %s (%d voci)", _HISTORY_PATH, len(_history))
    except FileNotFoundError:
        _history = []
    except Exception as exc:
        logger.warning("tuner: impossibile caricare storia: %s", exc)
        _history = []


def _save_history():
    try:
        os.makedirs(os.path.dirname(_HISTORY_PATH), exist_ok=True)
        with open(_HISTORY_PATH, "w") as f:
            json.dump(_history, f, indent=2)
    except Exception as exc:
        logger.warning("tuner: impossibile salvare storia: %s", exc)


_load_history()


# ── Spazio degli iperparametri ─────────────────────────────────────────────────
_PARAM_SPACE: dict[str, list[Any]] = {
    "top_k":            [4, 6, 8, 12, 16],
    "rerank_threshold": [0.1, 0.2, 0.3, 0.4, 0.5, 0.7],
    "token_budget":     [2000, 3000, 4000, 6000],
    "controller_iters": [1, 2, 3, 5],
}

# Configurazione di default
_DEFAULT_PARAMS: dict[str, Any] = {
    "top_k":            6,
    "rerank_threshold": 0.3,
    "token_budget":     3000,
    "controller_iters": 3,
}

# Configurazione attiva (modificata da optimize())
_active_params: dict[str, Any] = _DEFAULT_PARAMS.copy()


# ── UCB1 per singolo parametro ─────────────────────────────────────────────────
def _ucb1_best(param_name: str, observations: list[dict]) -> Any:
    """
    Seleziona il valore migliore per un parametro con UCB1.
    Ogni opzione ha un reward medio + bonus esplorazione.
    """
    options = _PARAM_SPACE[param_name]
    n_total = max(1, len(observations))

    counts: dict = {v: 0 for v in options}
    rewards: dict = {v: 0.0 for v in options}

    for obs in observations:
        val = obs.get("params", {}).get(param_name)
        if val in counts:
            counts[val] += 1
            rewards[val] += obs.get("overall_score", 0.5)

    # UCB1: reward_medio + sqrt(2 * ln(N) / n_i)
    best_val = None
    best_ucb = -1.0
    for v in options:
        n_i = counts[v]
        if n_i == 0:
            ucb = float("inf")  # esplora mai viste prima
        else:
            avg = rewards[v] / n_i
            exploration = math.sqrt(2 * math.log(n_total) / n_i)
            ucb = avg + exploration
        if ucb > best_ucb:
            best_ucb = ucb
            best_val = v

    return best_val


# ── API pubblica ───────────────────────────────────────────────────────────────

def get_active_params() -> dict[str, Any]:
    """Restituisce gli iperparametri attualmente attivi."""
    return _active_params.copy()


def record_observation(
    params: dict[str, Any],
    faithfulness: float,
    relevancy: float,
    recall: Optional[float] = None,
    latency_seconds: Optional[float] = None,
) -> dict:
    """
    Registra un'osservazione con i parametri usati e i risultati RAGAS.
    Salva su disco.
    """
    scores = [faithfulness, relevancy]
    if recall is not None:
        scores.append(recall)
    overall = sum(scores) / len(scores)

    obs = {
        "timestamp":     datetime.now(timezone.utc).isoformat(),
        "params":        params,
        "faithfulness":  faithfulness,
        "relevancy":     relevancy,
        "recall":        recall,
        "latency":       latency_seconds,
        "overall_score": overall,
    }
    _history.append(obs)
    _save_history()
    return obs


def optimize() -> dict[str, Any]:
    """
    Ricalcola i best iperparametri usando UCB1 sulla storia disponibile.
    Ritorna la configurazione ottimizzata.
    """
    global _active_params

    if len(_history) < 3:
        logger.info("tuner: storia insufficiente (%d obs), uso default", len(_history))
        return _active_params.copy()

    new_params: dict[str, Any] = {}
    for param_name in _PARAM_SPACE:
        new_params[param_name] = _ucb1_best(param_name, _history)

    _active_params = new_params
    logger.info("tuner: parametri ottimizzati → %s", new_params)
    return new_params.copy()


def history_summary() -> dict:
    """Statistiche riassuntive sulla storia delle osservazioni."""
    if not _history:
        return {"count": 0, "avg_overall": None, "best_params": None}

    best = max(_history, key=lambda o: o["overall_score"])
    avg = sum(o["overall_score"] for o in _history) / len(_history)
    return {
        "count":       len(_history),
        "avg_overall": round(avg, 3),
        "best_params": best["params"],
        "best_score":  round(best["overall_score"], 3),
    }
