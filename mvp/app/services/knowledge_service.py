"""
KnowledgeService — incapsula estrazione entità, relazioni e KG.

Uso:
  svc = KnowledgeService()
  entities = await svc.extract_entities(text, doc_id, chunk_id, page)
  triples  = await svc.extract_relations(text, entities, doc_id, chunk_id, page)
  context  = svc.get_entity_context(entity_text)
"""

import json
import logging
import re
from typing import Optional

from app.core import ollama
from app.models.knowledge import EntityModel, TripleModel
from app.prompts.knowledge import NER, RELATION
from app.storage import db as pg
from app.storage import kg

logger = logging.getLogger(__name__)

_VALID_PREDICATES = {
    "defines", "uses", "improves", "extends", "contradicts",
    "requires", "produces", "evaluates_on", "part_of", "related_to",
}

_VALID_ENTITY_TYPES = {
    "PERSON", "ORGANIZATION", "LOCATION", "DATE", "REGULATION",
    "CONCEPT", "AMOUNT", "PRODUCT", "METHOD", "DATASET",
}


class KnowledgeService:

    # ── Parsing ──────────────────────────────────────────────────────────────

    @staticmethod
    def _parse_entities(raw: str) -> list[dict]:
        raw = raw.strip()
        raw = re.sub(r"```(?:json)?\s*", "", raw)
        raw = re.sub(r"```\s*$", "", raw)
        match = re.search(r"\[.*\]", raw, re.DOTALL)
        if not match:
            return []
        try:
            items = json.loads(match.group(0))
            return [
                e for e in items
                if isinstance(e, dict)
                and e.get("type", "").upper() in _VALID_ENTITY_TYPES
                and float(e.get("confidence", 0)) >= 0.7
            ]
        except (json.JSONDecodeError, ValueError):
            return []

    @staticmethod
    def _parse_triples(raw: str) -> list[dict]:
        raw = raw.strip()
        raw = re.sub(r"```(?:json)?\s*", "", raw)
        raw = re.sub(r"```\s*$", "", raw)
        match = re.search(r"\[.*\]", raw, re.DOTALL)
        if not match:
            return []
        try:
            items = json.loads(match.group(0))
            result = []
            for t in items:
                if not isinstance(t, dict):
                    continue
                if (t.get("predicate", "").lower() in _VALID_PREDICATES
                        and float(t.get("confidence", 0)) >= 0.7):
                    result.append(t)
            return result
        except (json.JSONDecodeError, ValueError):
            return []

    # ── Entity extraction ────────────────────────────────────────────────────

    async def extract_entities(
        self,
        text: str,
        doc_id: str,
        chunk_id: str,
        page: int,
    ) -> list[dict]:
        text_excerpt = text[:2000]
        raw = await ollama.generate(NER.format(text=text_excerpt), num_predict=2048, num_ctx=8192)
        entities = self._parse_entities(raw)
        if entities:
            pg.insert_entities(entities, doc_id, chunk_id, page)
        return entities

    # ── Relation extraction ──────────────────────────────────────────────────

    async def extract_relations(
        self,
        text: str,
        entities: list[dict],
        doc_id: str,
        chunk_id: str,
        page: int,
    ) -> list[dict]:
        if not entities:
            return []
        entity_list = ", ".join(e["text"] for e in entities[:20])
        raw = await ollama.generate(
            RELATION.format(entities=entity_list, text=text[:2000]),
            num_predict=2048, num_ctx=8192,
        )
        triples = self._parse_triples(raw)
        if triples:
            pg.insert_triples(triples, doc_id, chunk_id, page)
        return triples

    # ── KG context ───────────────────────────────────────────────────────────

    def get_entity_context(self, entity_text: str) -> str:
        return kg.get_entity_context(entity_text)

    def query_graph(self, entity_text: str, max_hops: int = 2) -> list[dict]:
        return kg.query_graph(entity_text, max_hops=max_hops)
