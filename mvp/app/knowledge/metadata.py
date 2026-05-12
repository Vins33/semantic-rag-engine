"""
D3 + D4 — Domain Classification + Metadata Enrichment.

Usa Ollama (llama3.2) per estrarre in modo strutturato:
  - domain:   categoria tematica del documento
  - doc_type: tipo di documento (paper, survey, report)
  - language: lingua principale (en | it | other)
  - year:     anno di pubblicazione stimato
  - topics:   3-5 parole chiave descrittive

Il risultato viene salvato in PostgreSQL (colonne di `documents`)
e nel payload Qdrant (per G3 metadata filtering).

Fallback a euristiche su filename + testo se il LLM non restituisce JSON valido.
"""

import json
import logging
import re
from typing import Optional

from app.core import ollama

logger = logging.getLogger(__name__)

# Vocabolario domini fisso — corrisponde ai folder del corpus
_VALID_DOMAINS = {
    "rag_foundation",
    "graph_rag",
    "agentic_rag",
    "embeddings_memory",
    "indexing_retrieval",
    "ontology_semantic",
    "security",
    "multimodal",
    "survey",
    "advanced_rag",
    "unknown",
}

_VALID_DOC_TYPES = {"research_paper", "survey", "technical_report"}

from app.prompts.knowledge import METADATA_ENRICHMENT as _ENRICHMENT_PROMPT


# ── Euristiche di fallback ────────────────────────────────────────────────────

def _extract_year_heuristic(filename: str) -> Optional[int]:
    """
    Cerca l'anno di pubblicazione nel nome file.
    - arXiv ID YYMM.NNNNN → anno 2000+YY
    - Anno esplicito come 2025, 2026, …
    """
    # arXiv format: 2005.11401 → 2020, 2605.02967 → 2026
    m = re.match(r"^(\d{2})\d{2}\.\d+", filename)
    if m:
        return 2000 + int(m.group(1))
    # Anno esplicito nel filename
    m = re.search(r"\b(202[0-9]|2030)\b", filename)
    if m:
        return int(m.group(1))
    return None


def _infer_domain_heuristic(filename: str, text: str) -> str:
    """Keyword matching su filename + primi 500 chars di testo."""
    combined = (filename + " " + text[:500]).lower()

    if any(w in combined for w in ["graph rag", "graphrag", "graph-rag", "knowledge graph", "kg-rag", "kg rag"]):
        return "graph_rag"
    if any(w in combined for w in ["security", "privacy", "poison", "attack", "malicious", "adversar", "cleanbase"]):
        return "security"
    if any(w in combined for w in ["ontolog", "semantic", "taxonomy", "thesaur", "rdf", "sparql", "owl"]):
        return "ontology_semantic"
    if any(w in combined for w in ["multimodal", "vision", "visual", "image", "video", "cvpr", "spatiotemporal"]):
        return "multimodal"
    if any(w in combined for w in ["embed", "smart vector", "quote", "memory", "nomic"]):
        return "embeddings_memory"
    if any(w in combined for w in ["survey", "review", "overview", "comprehensive"]):
        return "survey"
    if any(w in combined for w in ["agent", "agentic", "iterative", "tool", "self-rag", "crag"]):
        return "agentic_rag"
    if any(w in combined for w in ["index", "bm25", "sparse", "dense", "hybrid retriev", "rerank"]):
        return "indexing_retrieval"
    if any(w in combined for w in ["advanced", "speculative", "chain", "sage", "hyde", "sure"]):
        return "advanced_rag"
    return "rag_foundation"


# ── Parser risposta LLM ───────────────────────────────────────────────────────

def _parse_llm_response(text: str) -> dict:
    """Prova json.loads, poi cerca il primo {...} nel testo (fallback)."""
    text = text.strip()
    # Rimuovi eventuale markdown code block
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"```\s*$", "", text, flags=re.MULTILINE)
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass
    # Cerca il primo oggetto JSON nel testo
    m = re.search(r"\{[^{}]*\}", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group())
        except json.JSONDecodeError:
            pass
    return {}


def _normalize(raw: dict, filename: str, text: str) -> dict:
    """Valida e normalizza i campi; applica euristiche sui campi mancanti."""
    domain = raw.get("domain", "")
    if domain not in _VALID_DOMAINS:
        domain = _infer_domain_heuristic(filename, text)

    doc_type = raw.get("doc_type", "")
    if doc_type not in _VALID_DOC_TYPES:
        combined = (filename + text[:200]).lower()
        doc_type = "survey" if "survey" in combined else "research_paper"

    language = raw.get("language", "en")
    if language not in ("en", "it", "other"):
        language = "en"

    year = raw.get("year")
    if not isinstance(year, int) or year < 2000 or year > 2030:
        year = _extract_year_heuristic(filename)

    topics = raw.get("topics", [])
    if not isinstance(topics, list):
        topics = []
    topics = [str(t) for t in topics if t][:5]

    return {
        "domain":   domain,
        "doc_type": doc_type,
        "language": language,
        "year":     year,
        "topics":   topics,
    }


# ── API pubblica ──────────────────────────────────────────────────────────────

async def enrich_document(filename: str, text_excerpt: str) -> dict:
    """
    D3 + D4: classifica il dominio e arricchisce i metadati del documento.

    Args:
        filename:     nome file originale (es. "2605.02967_AutoRAGTuner.pdf")
        text_excerpt: primi ~1500 caratteri di testo estratto dal PDF

    Returns:
        dict con chiavi: domain, doc_type, language, year, topics
    """
    prompt = _ENRICHMENT_PROMPT.format(
        filename=filename,
        excerpt=text_excerpt[:1500],
    )

    try:
        raw_response = await ollama.generate(prompt, num_predict=200)
        raw_dict = _parse_llm_response(raw_response)
        metadata = _normalize(raw_dict, filename, text_excerpt)
        logger.debug("Metadata LLM OK per '%s': %s", filename, metadata)
    except Exception as exc:
        logger.warning("Metadata enrichment LLM failed per '%s': %s — uso euristiche", filename, exc)
        metadata = _normalize({}, filename, text_excerpt)

    return metadata
