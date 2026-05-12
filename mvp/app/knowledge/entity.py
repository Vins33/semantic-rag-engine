"""
D1 — Entity Extraction (GraphRAG style, Edge et al. arXiv 2404.16130)

Estrae entità nominate da un testo tramite gemma4 con prompt strutturato.
Salva i risultati in PostgreSQL (tabella entities).

Tipi supportati: PERSON, ORGANIZATION, LOCATION, DATE, REGULATION,
                 CONCEPT, AMOUNT, PRODUCT, METHOD, DATASET

Output per entità:
  {text, type, confidence, offset_start, offset_end, doc_id, chunk_id, page}
"""

import json
import re

from app.core import ollama
from app.prompts.knowledge import NER as _NER_PROMPT
from app.storage import db as pg


# ── Parsing risposta LLM ──────────────────────────────────────────────────────

def _parse_entities(raw: str) -> list[dict]:
    """Estrae JSON array dalla risposta del LLM, tollerante a rumore."""
    raw = raw.strip()

    # Rimuovi markdown code blocks
    raw = re.sub(r"```(?:json)?\s*", "", raw)
    raw = re.sub(r"```\s*$", "", raw)

    # Cerca il primo [ ... ] nella risposta
    match = re.search(r"\[.*\]", raw, re.DOTALL)
    if not match:
        return []

    try:
        entities = json.loads(match.group(0))
        if not isinstance(entities, list):
            return []
        # Valida e filtra
        result = []
        for e in entities:
            if not isinstance(e, dict):
                continue
            text = str(e.get("text", "")).strip()
            etype = str(e.get("type", "")).upper().strip()
            conf = float(e.get("confidence", 0.0))
            if text and etype and conf >= 0.7:
                result.append({
                    "text":       text,
                    "type":       etype,
                    "confidence": round(conf, 3),
                })
        return result
    except (json.JSONDecodeError, ValueError):
        return []


# ── Funzione principale ───────────────────────────────────────────────────────

async def extract_entities(
    text: str,
    doc_id: str,
    chunk_id: str,
    page: int,
) -> list[dict]:
    """
    Estrae entità da un testo e le salva in PostgreSQL.
    
    Args:
        text:     testo del chunk
        doc_id:   ID del documento
        chunk_id: ID del chunk
        page:     numero pagina
    
    Returns:
        Lista di entità estratte e salvate
    """
    if not text or len(text.strip()) < 50:
        return []

    # Tronca testo lungo per contenere i token (max ~400 char per l'output JSON)
    text_excerpt = text[:400]

    prompt = _NER_PROMPT.format(text=text_excerpt)
    raw_response = await ollama.generate(prompt, num_predict=2048, num_ctx=8192)

    entities = _parse_entities(raw_response)

    if entities:
        pg.insert_entities(entities, doc_id, chunk_id, page)

    return entities


async def extract_entities_from_doc(doc_id: str, top_chunks: int = 10) -> list[dict]:
    """
    Estrae entità dai top chunk di un documento già ingestato.
    Usa il testo dei chunk già in PostgreSQL.
    
    Args:
        doc_id:     ID del documento
        top_chunks: numero massimo di chunk da processare
    
    Returns:
        Tutte le entità estratte dal documento
    """
    chunks = pg.get_chunks_for_doc(doc_id, limit=top_chunks)
    all_entities: list[dict] = []

    for chunk in chunks:
        entities = await extract_entities(
            text=chunk["text"],
            doc_id=doc_id,
            chunk_id=chunk["chunk_id"],
            page=chunk["page_start"],
        )
        all_entities.extend(entities)

    return all_entities
