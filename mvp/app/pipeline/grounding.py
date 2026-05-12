"""
H3 — Grounding Check (Self-RAG style).

Verifica che le affermazioni nella risposta generata siano supportate
dal contesto recuperato. Usa overlap lessicale pesato (F1 su token
significativi) — nessun modello aggiuntivo, bassa latenza.

Algoritmo:
  1. Split risposta in frasi significative (> 15 caratteri)
  2. Per ogni frase: calcola overlap token con il contesto completo
  3. Frase "non groundata" se overlap < GROUNDING_THRESHOLD
  4. Score globale = % frasi groundate

Riferimento: Self-RAG — Asai et al. arXiv:2310.11511
"""

import re
from typing import Optional

# Token significativi: parole di 4+ caratteri (escluse stop-word banali)
_TOKEN_RE = re.compile(r"\b[a-zA-ZàèéìòùÀÈÉÌÒÙ]{4,}\b")

# Soglia overlap per considerare una frase "groundata"
_OVERLAP_THRESHOLD = 0.25  # almeno 25% dei token della frase presenti nel contesto

# Soglia per considerare la risposta complessivamente groundata
_GROUNDED_RATIO_THRESHOLD = 0.65


def _extract_tokens(text: str) -> set[str]:
    return {t.lower() for t in _TOKEN_RE.findall(text)}


def _split_sentences(text: str) -> list[str]:
    """Divide il testo in frasi su . ! ? evitando abbreviazioni comuni."""
    raw = re.split(r"(?<=[.!?])\s+(?=[A-ZÀÈÉÌÒÙ\d])", text)
    return [s.strip() for s in raw if len(s.strip()) > 15]


def check_grounding(answer: str, context_chunks: list[str]) -> dict:
    """
    Controlla il grounding della risposta rispetto ai chunk di contesto.

    Args:
        answer:         Testo della risposta generata dal LLM.
        context_chunks: Lista di testi dei chunk usati come contesto.

    Returns:
        {
          "grounded":           bool,     # True se score >= soglia
          "score":              float,    # % frasi groundate (0–1)
          "ungrounded_count":   int,      # numero frasi non supportate
          "ungrounded_preview": list[str] # prime 3 frasi non supportate
        }
    """
    if not answer or not context_chunks:
        return {
            "grounded": True,
            "score": 1.0,
            "ungrounded_count": 0,
            "ungrounded_preview": [],
        }

    context_tokens = _extract_tokens(" ".join(context_chunks))
    sentences = _split_sentences(answer)

    if not sentences:
        return {
            "grounded": True,
            "score": 1.0,
            "ungrounded_count": 0,
            "ungrounded_preview": [],
        }

    ungrounded: list[str] = []

    for sent in sentences:
        sent_tokens = _extract_tokens(sent)
        if not sent_tokens:
            continue
        overlap = sent_tokens & context_tokens
        ratio = len(overlap) / len(sent_tokens)
        if ratio < _OVERLAP_THRESHOLD:
            ungrounded.append(sent)

    grounded_count = len(sentences) - len(ungrounded)
    score = grounded_count / len(sentences)

    return {
        "grounded":           score >= _GROUNDED_RATIO_THRESHOLD,
        "score":              round(score, 3),
        "ungrounded_count":   len(ungrounded),
        "ungrounded_preview": ungrounded[:3],
    }
