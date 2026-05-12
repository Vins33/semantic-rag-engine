"""
I4 — RAGAS-style Evaluation via LLM (gemma4).

Metriche implementate localmente (no dipendenza ragas library):
  - faithfulness       : la risposta è supportata dal contesto?
  - answer_relevancy   : la risposta è rilevante alla domanda?
  - context_recall     : il contesto copre le informazioni del ground_truth?

Endpoint: POST /api/v1/eval
Input:
  {
    "query":        "...",
    "answer":       "...",
    "context":      "...",
    "ground_truth": "..."  (opzionale)
  }

Ogni metrica è calcolata con un prompt LLM separato; il risultato è
uno score float [0.0, 1.0] + una breve spiegazione.
"""

import json
import logging
import re
from typing import Optional

from app.core.ollama import generate

logger = logging.getLogger(__name__)

# ── Prompt templates ───────────────────────────────────────────────────────────

from app.prompts.governance import EVAL_FAITHFULNESS as _FAITHFULNESS_PROMPT

from app.prompts.governance import EVAL_RELEVANCY as _RELEVANCY_PROMPT

from app.prompts.governance import EVAL_RECALL as _RECALL_PROMPT


# ── Parsing helper ─────────────────────────────────────────────────────────────

def _parse_score(text: str) -> dict:
    """Estrae {score, reason} dal testo LLM; fallback a 0.5 se non parsabile."""
    # Prova JSON diretto
    match = re.search(r'\{[^{}]*"score"\s*:\s*[\d.]+[^{}]*\}', text, re.DOTALL)
    if match:
        try:
            obj = json.loads(match.group())
            score = float(obj.get("score", 0.5))
            score = max(0.0, min(1.0, score))
            return {"score": score, "reason": obj.get("reason", "")}
        except (json.JSONDecodeError, ValueError):
            pass
    # Prova a estrarre solo il numero
    num = re.search(r'"score"\s*:\s*([\d.]+)', text)
    if num:
        try:
            score = max(0.0, min(1.0, float(num.group(1))))
            return {"score": score, "reason": text[:200]}
        except ValueError:
            pass
    logger.warning("eval: impossibile parsare score dal testo: %s", text[:200])
    return {"score": 0.5, "reason": "parse error"}


# ── Metrica principale ─────────────────────────────────────────────────────────

async def evaluate(
    query: str,
    answer: str,
    context: str,
    ground_truth: Optional[str] = None,
) -> dict:
    """
    Calcola faithfulness, answer_relevancy (e context_recall se ground_truth fornito).

    Returns:
      {
        "faithfulness":    {"score": float, "reason": str},
        "answer_relevancy": {"score": float, "reason": str},
        "context_recall":  {"score": float, "reason": str} | None,
        "overall":         float   # media delle metriche disponibili
      }
    """
    # 1. Faithfulness
    faith_raw = await generate(
        _FAITHFULNESS_PROMPT.format(context=context[:3000], answer=answer[:1500]),
        num_predict=512,
        num_ctx=4096,
    )
    faithfulness = _parse_score(faith_raw)

    # 2. Answer Relevancy
    relev_raw = await generate(
        _RELEVANCY_PROMPT.format(query=query, answer=answer[:1500]),
        num_predict=512,
        num_ctx=2048,
    )
    relevancy = _parse_score(relev_raw)

    # 3. Context Recall (opzionale)
    recall: Optional[dict] = None
    if ground_truth:
        recall_raw = await generate(
            _RECALL_PROMPT.format(ground_truth=ground_truth[:1500], context=context[:3000]),
            num_predict=512,
            num_ctx=4096,
        )
        recall = _parse_score(recall_raw)

    scores = [faithfulness["score"], relevancy["score"]]
    if recall:
        scores.append(recall["score"])
    overall = sum(scores) / len(scores)

    return {
        "faithfulness":     faithfulness,
        "answer_relevancy": relevancy,
        "context_recall":   recall,
        "overall":          round(overall, 3),
    }
