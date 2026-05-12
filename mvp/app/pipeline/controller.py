"""
F6B-D — Iterative Controller.

F6B: Decision gate    — se s2g_score < threshold, itera (max 3 round)
F6C: Sub-query decomposer — spezza query complesse in 2-3 sub-query
F6D: Contradiction detector — individua affermazioni contrastanti nel contesto

Funzione principale:
  run(query, context, retrieval_fn, s2g_score, max_iterations=3) -> ControllerResult
"""

import logging
import re
from dataclasses import dataclass, field

from app.core import ollama
from app.pipeline import s2g as s2g_mod

logger = logging.getLogger(__name__)

_MAX_ITERATIONS = 3


@dataclass
class ControllerResult:
    iterations:       int
    final_context:    str
    sub_queries:      list[str]
    contradictions:   list[str]
    s2g_scores:       list[float]
    used_decomposer:  bool
    used_iterations:  bool


# ── F6C: Sub-query decomposer ─────────────────────────────────────────────────

from app.prompts.rag import CONTROLLER_DECOMPOSE as _DECOMPOSE_PROMPT


async def decompose_query(query: str) -> list[str]:
    """
    F6C — Spezza la query in 2-3 sotto-query indipendenti.
    Ritorna la lista originale [query] in caso di errore.
    """
    prompt = _DECOMPOSE_PROMPT.format(query=query)
    try:
        raw = await ollama.generate(prompt, num_predict=2048, num_ctx=8192)
        sub_queries = _parse_json_list(raw)
        if sub_queries and len(sub_queries) >= 2:
            logger.info("F6C: decomposed into %d sub-queries", len(sub_queries))
            return sub_queries[:3]
    except Exception as exc:
        logger.warning("F6C decompose error: %s", exc)
    return [query]


def _parse_json_list(raw: str) -> list[str]:
    import json
    # Cerca array JSON
    match = re.search(r'\[.*?\]', raw, re.DOTALL)
    if match:
        try:
            items = json.loads(match.group())
            return [str(x).strip() for x in items if str(x).strip()]
        except json.JSONDecodeError:
            pass
    # Fallback: linee con bullet
    lines = [
        re.sub(r'^[\-\*\d\.\)]+\s*', '', ln).strip()
        for ln in raw.splitlines()
        if ln.strip() and not ln.strip().startswith('{')
    ]
    return [l for l in lines if len(l) > 5][:3]


# ── F6D: Contradiction detector ───────────────────────────────────────────────

from app.prompts.rag import CONTROLLER_CONTRADICT as _CONTRADICT_PROMPT


async def detect_contradictions(context: str) -> list[str]:
    """
    F6D — Rileva contraddizioni nel contesto recuperato.
    Ritorna lista di stringhe con le contraddizioni trovate (vuota se nessuna).
    """
    if len(context) < 200:
        return []
    prompt = _CONTRADICT_PROMPT.format(context=context[:3000])
    try:
        raw = await ollama.generate(prompt, num_predict=2048, num_ctx=8192)
        return _parse_contradictions(raw)
    except Exception as exc:
        logger.warning("F6D contradiction error: %s", exc)
        return []


def _parse_contradictions(raw: str) -> list[str]:
    lower = raw.lower()
    if "nessuna contraddizione" in lower or "no contradiction" in lower:
        return []
    lines = [
        re.sub(r'^[\-\*\d\.\)]+\s*', '', ln).strip()
        for ln in raw.splitlines()
        if ln.strip() and len(ln.strip()) > 10
    ]
    return lines[:3]


# ── F6B: Decision gate + iterative loop ──────────────────────────────────────

async def run(
    query: str,
    initial_context: str,
    retrieval_fn,            # async callable(sub_query: str) -> str (context string)
    initial_s2g_score: float,
    max_iterations: int = _MAX_ITERATIONS,
) -> ControllerResult:
    """
    F6B — Iterative Controller.

    Se il contesto iniziale è sufficiente (s2g >= threshold), ritorna subito.
    Altrimenti:
      1. Decompone la query in sub-query (F6C)
      2. Recupera contesto aggiuntivo per ogni sub-query
      3. Rivaluta con S2G (max max_iterations tentativi)
    Infine rileva contraddizioni (F6D) sul contesto finale.
    """
    s2g_scores = [initial_s2g_score]
    current_context = initial_context
    sub_queries: list[str] = [query]
    used_decomposer = False
    used_iterations = False
    iterations = 0

    # F6B — Decision gate
    if initial_s2g_score >= s2g_mod._THRESHOLD:
        # Contesto già sufficiente — solo contradiction check
        contradictions = await detect_contradictions(current_context)
        return ControllerResult(
            iterations=0,
            final_context=current_context,
            sub_queries=sub_queries,
            contradictions=contradictions,
            s2g_scores=s2g_scores,
            used_decomposer=False,
            used_iterations=False,
        )

    # Contesto insufficiente → decomponi + re-retrieve
    sub_queries = await decompose_query(query)
    used_decomposer = len(sub_queries) > 1

    for iteration in range(1, max_iterations + 1):
        iterations = iteration
        used_iterations = True

        extra_parts: list[str] = []
        for sq in sub_queries:
            try:
                extra_ctx = await retrieval_fn(sq)
                if extra_ctx:
                    extra_parts.append(f"[Sub-query: {sq}]\n{extra_ctx}")
            except Exception as exc:
                logger.warning("F6B: retrieval_fn error for sub-query '%s': %s", sq, exc)

        if extra_parts:
            current_context = current_context + "\n\n---\n\n" + "\n\n".join(extra_parts)

        # Rivaluta S2G
        eval_result = await s2g_mod.evaluate(query, current_context)
        new_score = eval_result["score"]
        s2g_scores.append(new_score)
        logger.info("F6B: iteration %d — s2g_score=%.3f", iteration, new_score)

        if new_score >= s2g_mod._THRESHOLD:
            break

    # F6D — Contradiction detection sul contesto finale
    contradictions = await detect_contradictions(current_context)

    return ControllerResult(
        iterations=iterations,
        final_context=current_context,
        sub_queries=sub_queries,
        contradictions=contradictions,
        s2g_scores=s2g_scores,
        used_decomposer=used_decomposer,
        used_iterations=used_iterations,
    )
