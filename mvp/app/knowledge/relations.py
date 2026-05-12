"""
D2 — Relation Extraction

Estrae triple semantiche (soggetto, predicato, oggetto) dal testo,
usando le entità già estratte da D1 come anchor.

Predicati supportati: defines, uses, improves, extends, contradicts,
                      requires, produces, evaluates_on, part_of, related_to

Output per tripla:
  {subject, predicate, object, confidence, doc_id, chunk_id, page}

Salva in PostgreSQL (tabella triples).
"""

import json
import re

from app.core import ollama
from app.prompts.knowledge import RELATION as _RE_PROMPT
from app.storage import db as pg


# ── Parsing ───────────────────────────────────────────────────────────────────

_VALID_PREDICATES = {
    "defines", "uses", "improves", "extends", "contradicts",
    "requires", "produces", "evaluates_on", "part_of", "related_to",
}


def _parse_triples(raw: str) -> list[dict]:
    raw = raw.strip()
    raw = re.sub(r"```(?:json)?\s*", "", raw)
    raw = re.sub(r"```\s*$", "", raw)

    match = re.search(r"\[.*\]", raw, re.DOTALL)
    if not match:
        return []

    try:
        triples = json.loads(match.group(0))
        if not isinstance(triples, list):
            return []
        result = []
        for t in triples:
            if not isinstance(t, dict):
                continue
            subj = str(t.get("subject", "")).strip()
            pred = str(t.get("predicate", "")).lower().strip()
            obj  = str(t.get("object", "")).strip()
            conf = float(t.get("confidence", 0.0))
            if subj and pred in _VALID_PREDICATES and obj and conf >= 0.7:
                result.append({
                    "subject":    subj,
                    "predicate":  pred,
                    "object":     obj,
                    "confidence": round(conf, 3),
                })
        return result
    except (json.JSONDecodeError, ValueError):
        return []


# ── Funzione principale ───────────────────────────────────────────────────────

async def extract_relations(
    text: str,
    entities: list[dict],
    doc_id: str,
    chunk_id: str,
    page: int,
) -> list[dict]:
    """
    Estrae relazioni semantiche da testo + entità note.
    
    Args:
        text:     testo del chunk
        entities: entità già estratte da D1 per questo chunk
        doc_id:   ID documento
        chunk_id: ID chunk
        page:     numero pagina
    
    Returns:
        Lista di triple estratte e salvate
    """
    if not text or not entities or len(text.strip()) < 50:
        return []

    entity_list = ", ".join(f'"{e["text"]}"' for e in entities[:15])
    text_excerpt = text[:400]

    prompt = _RE_PROMPT.format(entities=entity_list, text=text_excerpt)
    raw_response = await ollama.generate(prompt, num_predict=2048, num_ctx=8192)

    triples = _parse_triples(raw_response)

    if triples:
        pg.insert_triples(triples, doc_id, chunk_id, page)

    return triples
