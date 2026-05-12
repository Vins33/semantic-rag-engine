"""
F6A — S2G: Sufficiency-to-Generate evaluator (SURE-RAG style).

Valuta se il contesto recuperato è sufficiente per rispondere alla query.
Score 0.0–1.0; threshold di default 0.6.

Usa gemma4 con prompt breve per velocità.
"""

import logging
import re

from app.core import ollama

logger = logging.getLogger(__name__)

_THRESHOLD = 0.6

from app.prompts.rag import S2G_SUFFICIENCY as _PROMPT


async def evaluate(query: str, context: str) -> dict:
    """
    Valuta la sufficienza del contesto per la query.

    Ritorna:
      {
        "score": float,           # 0.0–1.0
        "sufficient": bool,       # score >= threshold
        "reason": str,
        "threshold": float,
      }
    """
    context_excerpt = context[:1500]

    prompt = _PROMPT.format(query=query, context_excerpt=context_excerpt)

    try:
        raw = await ollama.generate(prompt, num_predict=2048, num_ctx=8192)
        score, reason = _parse_response(raw)
    except Exception as exc:
        logger.warning("S2G evaluate error: %s — default score=0.5", exc)
        score, reason = 0.5, "evaluation failed"

    return {
        "score":      round(score, 3),
        "sufficient": score >= _THRESHOLD,
        "reason":     reason,
        "threshold":  _THRESHOLD,
    }


def _parse_response(raw: str) -> tuple[float, str]:
    """Estrae score e reason dal JSON di gemma4 (tollera testo extra)."""
    import json

    # Cerca il blocco JSON nella risposta (gemma4 reasoning model può avere testo prima)
    json_match = re.search(r'\{[^{}]*"score"[^{}]*\}', raw, re.DOTALL)
    if json_match:
        try:
            data = json.loads(json_match.group())
            score = float(data.get("score", 0.5))
            score = max(0.0, min(1.0, score))
            reason = str(data.get("reason", ""))[:200]
            return score, reason
        except (json.JSONDecodeError, ValueError):
            pass

    # Fallback: cerca pattern numerico
    num_match = re.search(r'"score"\s*:\s*([0-9.]+)', raw)
    if num_match:
        try:
            score = float(num_match.group(1))
            return max(0.0, min(1.0, score)), "parsed from text"
        except ValueError:
            pass

    logger.debug("S2G: risposta non parsabile: %s", raw[:200])
    return 0.5, "parse error"
