"""
C5 — Neo4j Knowledge Graph storage.

Driver bolt sincrono (neo4j Python driver).  Funzioni pubbliche:
  init_kg()                                          → crea constraint/indici
  store_triple(subject, predicate, object, doc_id, confidence)
  store_triples_bulk(triples)                        → batch write
  query_graph(entity_text, max_hops) -> list[dict]   → subgraph N-hop
  get_entity_context(entity_text)    -> str          → testo per prompt
  entity_exists(entity_text)         -> bool
"""

import logging
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)

# Neo4j driver — lazy init
_driver = None


def _get_driver():
    global _driver
    if _driver is None:
        try:
            from neo4j import GraphDatabase  # type: ignore
            _driver = GraphDatabase.driver(
                settings.neo4j_uri,
                auth=(settings.neo4j_user, settings.neo4j_password),
            )
            logger.info("Neo4j driver connesso a %s", settings.neo4j_uri)
        except Exception as exc:
            logger.warning("Neo4j non raggiungibile: %s", exc)
            _driver = None
    return _driver


def init_kg() -> None:
    """Crea constraint e indici su Neo4j (idempotente)."""
    driver = _get_driver()
    if driver is None:
        return
    try:
        with driver.session() as session:
            # Unique constraint su Entity.text (case-insensitive via lowercased)
            session.run(
                "CREATE CONSTRAINT entity_text_unique IF NOT EXISTS "
                "FOR (e:Entity) REQUIRE e.text IS UNIQUE"
            )
            # Indice su Relation.predicate per hop-query efficienti
            session.run(
                "CREATE INDEX relation_predicate IF NOT EXISTS "
                "FOR ()-[r:RELATION]-() ON (r.predicate)"
            )
        logger.info("Neo4j: constraint e indici inizializzati.")
    except Exception as exc:
        logger.warning("Neo4j init_kg error: %s", exc)


def store_triple(
    subject: str,
    predicate: str,
    object_: str,
    doc_id: str,
    confidence: float = 1.0,
) -> bool:
    """
    Scrive una tripla (subject)-[:RELATION {predicate}]->(object) in Neo4j.
    Usa MERGE per evitare duplicati sui nodi; crea la relazione se non esiste.
    """
    driver = _get_driver()
    if driver is None:
        return False
    subject_clean  = subject.strip().lower()
    object_clean   = object_.strip().lower()
    predicate_clean = predicate.strip().lower()
    if not subject_clean or not predicate_clean or not object_clean:
        return False
    try:
        with driver.session() as session:
            session.run(
                """
                MERGE (s:Entity {text: $subject})
                  ON CREATE SET s.text_raw = $subject_raw
                MERGE (o:Entity {text: $object})
                  ON CREATE SET o.text_raw = $object_raw
                MERGE (s)-[r:RELATION {predicate: $predicate, doc_id: $doc_id}]->(o)
                  ON CREATE SET r.confidence = $confidence, r.created_at = datetime()
                  ON MATCH  SET r.confidence = CASE
                      WHEN $confidence > r.confidence THEN $confidence
                      ELSE r.confidence END
                """,
                subject=subject_clean,
                subject_raw=subject,
                object=object_clean,
                object_raw=object_,
                predicate=predicate_clean,
                doc_id=doc_id,
                confidence=confidence,
            )
        return True
    except Exception as exc:
        logger.warning("Neo4j store_triple error: %s", exc)
        return False


def store_triples_bulk(triples: list[dict]) -> int:
    """
    Batch write di triple. Ogni dict deve avere:
      subject, predicate, object, doc_id, confidence.
    Ritorna numero di triple scritte con successo.
    """
    if not triples:
        return 0
    ok = 0
    for t in triples:
        if store_triple(
            t.get("subject", ""),
            t.get("predicate", ""),
            t.get("object", ""),
            t.get("doc_id", ""),
            t.get("confidence", 1.0),
        ):
            ok += 1
    return ok


def query_graph(entity_text: str, max_hops: int = 2) -> list[dict]:
    """
    Ritorna il subgraph entro max_hops dall'entità specificata.
    Ritorna list[dict] con campi: subject, predicate, object, doc_id, confidence.
    """
    driver = _get_driver()
    if driver is None:
        return []
    entity_clean = entity_text.strip().lower()
    try:
        with driver.session() as session:
            result = session.run(
                f"""
                MATCH (start:Entity {{text: $entity}})
                CALL apoc.path.subgraphAll(start, {{
                    maxLevel: {max_hops},
                    relationshipFilter: 'RELATION>'
                }})
                YIELD relationships
                UNWIND relationships AS rel
                RETURN
                    startNode(rel).text   AS subject,
                    rel.predicate         AS predicate,
                    endNode(rel).text     AS object,
                    rel.doc_id            AS doc_id,
                    rel.confidence        AS confidence
                LIMIT 100
                """,
                entity=entity_clean,
            )
            return [dict(r) for r in result]
    except Exception as exc:
        # APOC potrebbe non essere installato — fallback senza APOC
        logger.warning("Neo4j query_graph (APOC): %s — tentativo fallback", exc)
        return _query_graph_no_apoc(entity_clean, max_hops)


def _query_graph_no_apoc(entity_clean: str, max_hops: int) -> list[dict]:
    """Fallback senza APOC: query Cypher pura fino a 3 hop."""
    driver = _get_driver()
    if driver is None:
        return []
    hops = min(max_hops, 3)
    try:
        with driver.session() as session:
            result = session.run(
                f"""
                MATCH (start:Entity {{text: $entity}})
                MATCH (start)-[r:RELATION*1..{hops}]->(end:Entity)
                UNWIND r AS rel
                RETURN DISTINCT
                    startNode(rel).text   AS subject,
                    rel.predicate         AS predicate,
                    endNode(rel).text     AS object,
                    rel.doc_id            AS doc_id,
                    rel.confidence        AS confidence
                LIMIT 100
                """,
                entity=entity_clean,
            )
            rows = [dict(r) for r in result]
            if not rows:
                # anche relazioni in entrata
                result2 = session.run(
                    """
                    MATCH (e:Entity {text: $entity})-[r:RELATION]-(other:Entity)
                    RETURN
                        startNode(r).text AS subject,
                        r.predicate       AS predicate,
                        endNode(r).text   AS object,
                        r.doc_id          AS doc_id,
                        r.confidence      AS confidence
                    LIMIT 50
                    """,
                    entity=entity_clean,
                )
                rows = [dict(r) for r in result2]
            return rows
    except Exception as exc:
        logger.warning("Neo4j _query_graph_no_apoc error: %s", exc)
        return []


def get_entity_context(entity_text: str) -> str:
    """
    Ritorna un testo leggibile che descrive il subgraph di un'entità
    (per arricchire il contesto del prompt RAG).
    """
    triples = query_graph(entity_text, max_hops=2)
    if not triples:
        return ""
    lines = [f"Knowledge Graph context for '{entity_text}':"]
    seen = set()
    for t in triples:
        line = f"  {t.get('subject', '')} --[{t.get('predicate', '')}]--> {t.get('object', '')}"
        if line not in seen:
            seen.add(line)
            lines.append(line)
    return "\n".join(lines)


def entity_exists(entity_text: str) -> bool:
    driver = _get_driver()
    if driver is None:
        return False
    entity_clean = entity_text.strip().lower()
    try:
        with driver.session() as session:
            result = session.run(
                "MATCH (e:Entity {text: $text}) RETURN count(e) AS n",
                text=entity_clean,
            )
            return result.single()["n"] > 0
    except Exception as exc:
        logger.warning("Neo4j entity_exists error: %s", exc)
        return False
