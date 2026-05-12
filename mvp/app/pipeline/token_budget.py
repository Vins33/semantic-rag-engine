"""
I7 — Token Budget.

Stima i token totali di una richiesta (prompt + contesto + risposta attesa).
Se il totale supera il budget, comprime il contesto fino a rientrare nel limite.

Approssimazione: 1 token ≈ 4 caratteri (euristica comune per modelli europei/inglese).

Utilizzo in query.py:
  from app.pipeline.token_budget import enforce_budget
  context, was_cut = enforce_budget(context, query, budget=3000)
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# ── Configurazione ─────────────────────────────────────────────────────────────
DEFAULT_BUDGET       = 3000   # token massimi per prompt+contesto
QUERY_TOKEN_OVERHEAD = 200    # stima overhead per prompt template + query
RESPONSE_RESERVE     = 512    # token riservati per la risposta del LLM
CHARS_PER_TOKEN      = 4      # euristica


def _count_tokens(text: str) -> int:
    return max(1, len(text) // CHARS_PER_TOKEN)


def available_context_tokens(budget: int = DEFAULT_BUDGET, query: str = "") -> int:
    """Token disponibili per il contesto dopo aver sottratto overhead."""
    query_tokens = _count_tokens(query)
    return max(0, budget - query_tokens - QUERY_TOKEN_OVERHEAD - RESPONSE_RESERVE)


def enforce_budget(
    context: str,
    query: str = "",
    budget: int = DEFAULT_BUDGET,
) -> tuple[str, bool]:
    """
    Se il contesto supera il budget disponibile, lo tronca al limite.

    Returns:
      (context_possibly_truncated, was_cut: bool)
    """
    available = available_context_tokens(budget, query)
    available_chars = available * CHARS_PER_TOKEN

    if len(context) <= available_chars:
        return context, False

    # Tronca al limite di caratteri conservando frasi complete
    truncated = context[:available_chars]
    # Prova a tagliare all'ultimo punto/a-capo per non spezzare frasi
    last_period = max(
        truncated.rfind(". "),
        truncated.rfind("\n"),
    )
    if last_period > available_chars * 0.7:
        truncated = truncated[: last_period + 1]

    logger.info(
        "token_budget: contesto ridotto %d→%d chars (budget=%d token)",
        len(context), len(truncated), budget,
    )
    return truncated, True


def budget_info(context: str, query: str = "", budget: int = DEFAULT_BUDGET) -> dict:
    """Info diagnostiche sul budget attuale."""
    total_chars = len(context) + len(query) + QUERY_TOKEN_OVERHEAD * CHARS_PER_TOKEN
    estimated_tokens = _count_tokens(context) + _count_tokens(query) + QUERY_TOKEN_OVERHEAD
    return {
        "estimated_tokens": estimated_tokens,
        "budget":           budget,
        "over_budget":      estimated_tokens > (budget - RESPONSE_RESERVE),
        "context_chars":    len(context),
        "query_chars":      len(query),
    }
