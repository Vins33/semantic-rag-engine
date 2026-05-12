"""
Semantic RAG Engine — MVP
FastAPI app con due endpoint principali:
  POST /api/v1/ingest   → carica un PDF o Markdown e lo indicizza
  POST /api/v1/query    → interroga il corpus in linguaggio naturale
"""

import asyncio
import json as _json
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, UploadFile, File, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.routing import Mount
from pydantic import BaseModel

from app.ingestion import ingest
from app.core import ollama
from app.core.auth import (
    TokenPayload, create_access_token,
    require_reader, require_writer, require_admin,
)
from app.core.cache import cache_clear
from app.models import (
    IngestResponse, QueryRequest, QueryResponse, Source, GroundingInfo,
    ConfabulationInfo, CitationInfo, IntentInfo, ControllerInfo, TreeRetrievalInfo,
)
from app.core.monitoring import metrics_app, ingest_total
from app.services.rag_query import RagQueryService
from app.services.eval_service import EvalService
from app.storage import db, object as obj_store, vector as vec_store

_rag_service  = RagQueryService()
_eval_service = EvalService()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Inizializza schema PostgreSQL
    db.init_schema()
    # Assicura bucket MinIO
    obj_store.ensure_bucket()
    # Assicura collection Qdrant
    vec_store.ensure_collection()
    # E3 — OpenSearch: crea indice BM25 se non esiste
    from app.storage import opensearch as os_store
    os_store.create_index_if_not_exists()
    # C5 — Neo4j: crea constraint/indici se non esistono
    from app.storage import kg
    kg.init_kg()
    yield


app = FastAPI(
    title="Semantic RAG Engine — MVP",
    version="0.1.0",
    description="RAG verticale su PDF: ingestione + query in linguaggio naturale.",
    lifespan=lifespan,
)

# CORS — permette al frontend NiceGUI/Streamlit (porta diversa) di chiamare le API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # restringere in produzione
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# I3 — Prometheus metrics endpoint
app.mount("/metrics", metrics_app)


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/api/v1/health", tags=["infra"])
async def health():
    """Verifica che tutti i servizi siano raggiungibili."""
    import httpx
    import redis as _redis

    results: dict[str, str] = {}

    # Ollama
    results["ollama"] = "ok" if await ollama.health_check() else "unreachable"

    # Qdrant
    try:
        vec_store.get_client().get_collections()
        results["qdrant"] = "ok"
    except Exception as e:
        results["qdrant"] = f"unreachable: {e}"

    # PostgreSQL
    try:
        db.get_pool().getconn()
        results["postgres"] = "ok"
    except Exception as e:
        results["postgres"] = f"unreachable: {e}"

    # Redis
    try:
        from app.core.config import settings as _cfg
        r = _redis.Redis(host=_cfg.redis_host, port=_cfg.redis_port,
                         socket_connect_timeout=2, socket_timeout=2)
        r.ping()
        results["redis"] = "ok"
    except Exception as e:
        results["redis"] = f"unreachable: {e}"

    # OpenSearch
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(f"{_cfg.opensearch_url}/_cluster/health")
            results["opensearch"] = "ok" if resp.status_code == 200 else f"status {resp.status_code}"
    except Exception as e:
        results["opensearch"] = f"unreachable: {e}"

    # Neo4j
    try:
        from app.storage import kg
        driver = kg._get_driver()
        if driver:
            driver.verify_connectivity()
            results["neo4j"] = "ok"
        else:
            results["neo4j"] = "unreachable"
    except Exception as e:
        results["neo4j"] = f"unreachable: {e}"

    # MinIO
    try:
        obj_store.get_client().bucket_exists("_healthcheck_probe_")
        results["minio"] = "ok"
    except Exception as e:
        results["minio"] = "ok" if "NoSuchBucket" in str(e) or "does not exist" in str(e) else f"unreachable: {e}"

    overall = "ok" if all(v == "ok" for v in results.values()) else "degraded"
    return {"status": overall, **results}


@app.post(
    "/api/v1/ingest",
    response_model=IngestResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["ingestione"],
    summary="Carica e indicizza un PDF o un file Markdown (.md)",
)
async def ingest_endpoint(
    file: UploadFile = File(...),
    _user: TokenPayload = Depends(require_writer),
):
    fname = (file.filename or "").lower()
    is_pdf = fname.endswith(".pdf")
    is_md  = fname.endswith(".md") or fname.endswith(".markdown")

    if not (is_pdf or is_md):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Sono accettati solo file PDF (.pdf) o Markdown (.md).",
        )

    file_bytes = await file.read()
    if len(file_bytes) > 50 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File troppo grande. Limite: 50 MB.",
        )
    try:
        if is_pdf:
            result = await ingest.ingest_pdf(file.filename, file_bytes)
        else:
            result = await ingest.ingest_markdown(file.filename, file_bytes)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Errore ingestione: {exc}",
        )
    # I3 — increment ingest counter
    ingest_total.labels(doc_type="pdf" if is_pdf else "markdown").inc()
    return IngestResponse(**result)


@app.get(
    "/api/v1/documents",
    tags=["ingestione"],
    summary="Lista tutti i documenti indicizzati con metadati",
)
async def list_documents(_user: TokenPayload = Depends(require_reader)):
    """Ritorna tutti i documenti presenti nel corpus con i loro metadati D3+D4."""
    docs = db.get_all_documents()
    return {"total": len(docs), "documents": docs}


@app.delete(
    "/api/v1/documents/{doc_id}",
    tags=["ingestione"],
    summary="Rimuove un documento da tutti gli store (Qdrant, PG, OpenSearch, MinIO)",
)
async def delete_document(
    doc_id: str,
    _user: TokenPayload = Depends(require_admin),
):
    """
    Purge completo di un documento:
      - Qdrant: delete points by doc_id payload filter
      - OpenSearch: delete chunks by doc_id query
      - PostgreSQL: DELETE CASCADE (chunks, entities, triples, tree_nodes)
      - MinIO: rimuove raw/{doc_id}.pdf e parsed/{doc_id}.md
    """
    from app.storage import opensearch as os_store
    from qdrant_client.models import Filter, FieldCondition, MatchValue
    from app.core.audit import log_event
    from app.core.config import settings as _cfg

    # Verify document exists
    docs = db.get_all_documents()
    doc = next((d for d in docs if d["doc_id"] == doc_id), None)
    if doc is None:
        raise HTTPException(status_code=404, detail=f"Documento {doc_id} non trovato.")

    errors: list[str] = []

    # 1. Qdrant — delete all points with doc_id
    try:
        vec_store.get_client().delete(
            collection_name=_cfg.qdrant_collection,
            points_selector=Filter(
                must=[FieldCondition(key="doc_id", match=MatchValue(value=doc_id))]
            ),
        )
    except Exception as e:
        errors.append(f"qdrant: {e}")

    # 2. OpenSearch — delete by doc_id query
    try:
        os_store.delete_by_doc(doc_id)
    except Exception as e:
        errors.append(f"opensearch: {e}")

    # 3. PostgreSQL — CASCADE deletes chunks, entities, triples, tree_nodes
    try:
        db.delete_document(doc_id)
    except Exception as e:
        errors.append(f"postgres: {e}")

    # 4. MinIO — raw + parsed objects
    try:
        c = obj_store.get_client()
        for key in [f"raw/{doc_id}.pdf", f"parsed/{doc_id}.md"]:
            try:
                c.remove_object(_cfg.minio_bucket, key)
            except Exception:
                pass
    except Exception as e:
        errors.append(f"minio: {e}")

    log_event("delete", doc_id, {"filename": doc.get("filename", ""), "errors": errors})
    return {
        "doc_id":  doc_id,
        "deleted": True,
        "errors":  errors,
    }


@app.post(
    "/api/v1/query",
    response_model=QueryResponse,
    tags=["query"],
    summary="Interroga il corpus in linguaggio naturale",
)
async def query_endpoint(
    req: QueryRequest,
    _user: TokenPayload = Depends(require_reader),
):
    if not req.query.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La query non può essere vuota.",
        )
    try:
        result = await _rag_service.answer(req.query, req.top_k, req.filters)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Errore query: {exc}",
        )
    return QueryResponse(
        answer=result["answer"],
        sources=[Source(**s) for s in result["sources"]],
        model=result["model"],
        cache_hit=result.get("cache_hit", False),
        grounding=GroundingInfo(**result["grounding"]) if result.get("grounding") else None,
        confabulation=ConfabulationInfo(**result["confabulation"]) if result.get("confabulation") else None,
        citation=CitationInfo(**result["citation"]) if result.get("citation") else None,
        intent=IntentInfo(**result["intent"]) if result.get("intent") else None,
        controller=ControllerInfo(**result["controller"]) if result.get("controller") else None,
        tree_retrieval=TreeRetrievalInfo(**result["tree_retrieval"]) if result.get("tree_retrieval") else None,
    )


@app.post(
    "/api/v1/query/stream",
    tags=["query"],
    summary="Streaming SSE: interroga il corpus e riceve la risposta token per token",
)
async def query_stream_endpoint(
    req: QueryRequest,
    _user: TokenPayload = Depends(require_reader),
):
    """
    Streaming response via Server-Sent Events (SSE).
    Emette eventi:
      data: {"type": "token",  "text": "<token>"}
      data: {"type": "sources","sources": [...]}
      data: {"type": "done",   "grounding": {...}, "confabulation": {...}}
    """
    if not req.query.strip():
        raise HTTPException(status_code=400, detail="La query non può essere vuota.")

    async def _event_generator() -> AsyncGenerator[str, None]:
        from app.pipeline.hyde import hyde_embedding
        from app.pipeline.intent import analyze_intent
        from app.core.cache import cache_get, cache_set
        from app.pipeline.expansion import expand_query
        from app.pipeline.rerank import rerank
        from app.pipeline.compress import compress_chunks
        from app.pipeline.token_budget import enforce_budget
        from app.pipeline.grounding import check_grounding
        from app.pipeline.confabulation import check_confabulation
        from app.pipeline.s2g import evaluate as s2g_evaluate
        from app.pipeline.controller import run as controller_run
        from app.storage import opensearch as os_store
        from app.indexing.tree_retrieval import retrieve_tree
        from app.storage import kg as kg_store
        from app.prompts.rag import RAG_ANSWER
        import httpx

        k = req.top_k or 6
        intent = analyze_intent(req.query)
        if not intent.retrieval_needed:
            yield f"data: {_json.dumps({'type': 'token', 'text': intent.direct_answer})}\n\n"
            yield f"data: {_json.dumps({'type': 'done', 'grounding': {'grounded': True, 'score': 1.0}})}\n\n"
            return

        k = int(k * intent.top_k_multiplier)
        query_vector = await hyde_embedding(req.query)

        # Cache check
        cached = cache_get(query_vector)
        if cached is not None:
            yield f"data: {_json.dumps({'type': 'token', 'text': cached['answer']})}\n\n"
            yield f"data: {_json.dumps({'type': 'sources', 'sources': cached.get('sources', [])})}\n\n"
            yield f"data: {_json.dumps({'type': 'done', 'cache_hit': True})}\n\n"
            return

        # Retrieval
        qdrant_filter = None
        os_filters: dict = {}
        if req.filters:
            qdrant_filter = vec_store.build_qdrant_filter(
                domain=req.filters.domain, language=req.filters.language,
                doc_type=req.filters.doc_type, year_from=req.filters.year_from,
                year_to=req.filters.year_to,
            )
            if req.filters.domain:  os_filters["domain"]   = req.filters.domain
            if req.filters.language: os_filters["language"] = req.filters.language
            if req.filters.doc_type: os_filters["doc_type"] = req.filters.doc_type

        vector_hits = vec_store.vector_search(query_vector, limit=k * 4, filt=qdrant_filter)
        expansion   = expand_query(req.query)
        fts_hits    = os_store.search_bm25(expansion.expanded_query, k=k * 4,
                                           filters=os_filters if os_filters else None)
        if not fts_hits:
            fts_hits = db.fts_search(expansion.expanded_query, limit=k * 4)
        tree_hits   = retrieve_tree(req.query, k=k * 2)

        rrf = _rag_service._rrf(vector_hits, fts_hits, tree_hits=tree_hits)[:k * 2]
        ranked = rerank(req.query, rrf)[:k]

        if not ranked:
            yield f"data: {_json.dumps({'type': 'token', 'text': 'Nessun documento pertinente trovato.'})}\n\n"
            yield f"data: {_json.dumps({'type': 'done'})}\n\n"
            return

        compressed = compress_chunks(req.query, ranked)
        context_parts, sources = [], []
        for (cid, orig, score), (_, comp, _) in zip(ranked, compressed):
            context_parts.append(f"[{orig['filename']} | pag. {orig['page_start']}]\n{comp['text']}")
            sources.append({
                "chunk_id": cid, "doc_id": orig["doc_id"],
                "filename": orig["filename"], "page": orig["page_start"],
                "text_preview": orig["text"][:200], "score": round(score, 4),
                "bm25_source": orig.get("bm25_source", "vector"),
            })

        context = "\n\n---\n\n".join(context_parts)
        try:
            kg_ctx = kg_store.get_entity_context(req.query)
            if kg_ctx:
                context = f"[Knowledge Graph Context]\n{kg_ctx}\n\n---\n\n{context}"
        except Exception:
            pass

        context, _ = enforce_budget(context, req.query)
        s2g_result  = await s2g_evaluate(req.query, context)
        ctrl = await controller_run(
            query=req.query, initial_context=context,
            retrieval_fn=_rag_service._make_retrieval_fn(k, qdrant_filter, os_filters),
            initial_s2g_score=s2g_result["score"],
        )
        context = ctrl.final_context

        # Emit sources before streaming tokens
        yield f"data: {_json.dumps({'type': 'sources', 'sources': sources})}\n\n"

        # Streaming generation via Ollama stream=true
        prompt = RAG_ANSWER.format(context=context, query=req.query)
        from app.core.config import settings as _cfg
        full_answer = ""
        try:
            async with httpx.AsyncClient(timeout=180.0) as client:
                async with client.stream(
                    "POST",
                    f"{_cfg.ollama_base_url}/api/generate",
                    json={"model": _cfg.chat_model, "prompt": prompt,
                          "stream": True, "options": {"temperature": 0.1, "num_predict": 1024}},
                ) as resp:
                    async for line in resp.aiter_lines():
                        if not line.strip():
                            continue
                        try:
                            chunk_data = _json.loads(line)
                            token = chunk_data.get("response", "")
                            if token:
                                full_answer += token
                                yield f"data: {_json.dumps({'type': 'token', 'text': token})}\n\n"
                            if chunk_data.get("done"):
                                break
                        except Exception:
                            continue
        except Exception as e:
            yield f"data: {_json.dumps({'type': 'error', 'detail': str(e)})}\n\n"
            return

        grounding = check_grounding(full_answer, [p["text"] for _, p, _ in compressed])
        confab    = check_confabulation(full_answer, [p["text"] for _, p, _ in compressed])
        yield f"data: {_json.dumps({'type': 'done', 'grounding': grounding, 'confabulation': {'has_confabulation': confab.has_confabulation, 'confidence': confab.confidence}})}\n\n"

    return StreamingResponse(
        _event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.delete(
    "/api/v1/admin/cache",
    tags=["admin"],
    summary="Svuota la semantic cache Redis",
)
async def clear_cache(_user: TokenPayload = Depends(require_admin)):
    n = cache_clear()
    return {"cleared_entries": n}


@app.get(
    "/api/v1/admin/audit",
    tags=["admin"],
    summary="Verifica integrità Merkle chain dell'audit log (E6)",
)
async def audit_verify(_user: TokenPayload = Depends(require_admin)):
    from app.core.audit import verify_chain
    return verify_chain(limit=200)


# ── D1/D2 — Entity & Relation Extraction endpoints ───────────────────────────

@app.post(
    "/api/v1/entities/extract/{doc_id}",
    tags=["knowledge"],
    summary="D1+D2 — Estrae entità e relazioni dai chunk di un documento",
)
async def extract_doc_entities(doc_id: str, top_chunks: int = 5, background_tasks: BackgroundTasks = None):
    """Esegue NER (D1) e Relation Extraction (D2) sui primi N chunk del documento."""
    from app.services.knowledge_service import KnowledgeService
    from app.storage import db as storage_db

    chunks = storage_db.get_chunks_for_doc(doc_id, limit=top_chunks)
    if not chunks:
        raise HTTPException(status_code=404, detail=f"Documento {doc_id} non trovato o senza chunk.")

    svc = KnowledgeService()
    all_entities: list[dict] = []
    all_triples: list[dict] = []

    for chunk in chunks:
        entities = await svc.extract_entities(
            text=chunk["text"], doc_id=doc_id,
            chunk_id=chunk["chunk_id"], page=chunk["page_start"],
        )
        all_entities.extend(entities)
        if entities:
            triples = await svc.extract_relations(
                text=chunk["text"], entities=entities,
                doc_id=doc_id, chunk_id=chunk["chunk_id"], page=chunk["page_start"],
            )
            all_triples.extend(triples)

    if background_tasks is not None:
        from app.knowledge import kg_builder
        background_tasks.add_task(kg_builder.build_from_doc, doc_id)

    return {
        "doc_id":           doc_id,
        "chunks_processed": len(chunks),
        "entities_found":   len(all_entities),
        "triples_found":    len(all_triples),
        "entities":         all_entities[:50],
        "triples":          all_triples[:50],
        "kg_build":         "enqueued" if background_tasks else "skipped",
    }


@app.get(
    "/api/v1/entities/{doc_id}",
    tags=["knowledge"],
    summary="Ritorna entità estratte da un documento",
)
async def get_entities(doc_id: str):
    from app.storage import db as storage_db
    entities = storage_db.get_entities_for_doc(doc_id)
    triples  = storage_db.get_triples_for_doc(doc_id)
    return {"doc_id": doc_id, "entities": entities, "triples": triples}


@app.get(
    "/api/v1/entities/search/{query}",
    tags=["knowledge"],
    summary="Cerca entità per nome nel knowledge base",
)
async def search_entities(query: str, entity_type: str | None = None):
    from app.storage import db as storage_db
    results = storage_db.search_entities(query, entity_type)
    return {"query": query, "results": results}


# ── C5/C6 — Knowledge Graph endpoints ────────────────────────────────────────

@app.get(
    "/api/v1/kg/context/{entity}",
    tags=["knowledge"],
    summary="C5 — Ritorna subgraph Neo4j per un'entità (max 2 hop)",
)
async def kg_context(entity: str, max_hops: int = 2):
    """Ritorna il subgraph attorno all'entità specificata in Neo4j."""
    from app.storage import kg
    entity = entity.strip()
    if not entity:
        raise HTTPException(status_code=400, detail="entity non può essere vuota.")
    triples  = kg.query_graph(entity, max_hops=min(max_hops, 3))
    context  = kg.get_entity_context(entity)
    return {
        "entity":     entity,
        "max_hops":   max_hops,
        "triples":    triples,
        "context_text": context,
    }


@app.post(
    "/api/v1/kg/build/{doc_id}",
    tags=["knowledge"],
    summary="C6 — Costruisce subgraph Neo4j dalle triple PostgreSQL di un documento",
)
async def kg_build_doc(doc_id: str, background_tasks: BackgroundTasks):
    from app.knowledge import kg_builder
    background_tasks.add_task(kg_builder.build_from_doc, doc_id)
    return {"doc_id": doc_id, "status": "kg_build enqueued"}


@app.post(
    "/api/v1/kg/build_all",
    tags=["knowledge"],
    summary="C6 — Costruisce Knowledge Graph completo da tutte le triple in PostgreSQL",
)
async def kg_build_all(background_tasks: BackgroundTasks):
    from app.knowledge import kg_builder
    background_tasks.add_task(kg_builder.build_all)
    return {"status": "kg_build_all enqueued"}


# ── E5/G4 — Tree Index endpoints ──────────────────────────────────────────────

@app.post(
    "/api/v1/tree/build/{doc_id}",
    tags=["knowledge"],
    summary="E5 — Costruisce tree index LTREE per un documento",
)
async def tree_build_doc(doc_id: str, background_tasks: BackgroundTasks):
    from app.indexing import tree_index
    background_tasks.add_task(tree_index.build_tree, doc_id)
    return {"doc_id": doc_id, "status": "tree_build enqueued"}


@app.get(
    "/api/v1/tree/node",
    tags=["knowledge"],
    summary="E5 — Ritorna un nodo dell'albero per path LTREE",
)
async def tree_get_node(path: str):
    from app.indexing.tree_index import get_node, get_children, get_ancestors
    node = get_node(path)
    if node is None:
        raise HTTPException(status_code=404, detail=f"Nodo '{path}' non trovato.")
    return {
        "node": node,
        "children":  get_children(path),
        "ancestors": get_ancestors(path),
    }


# ── I1 — Auth: token generation (sviluppo) ─────────────────────────────────────────

import os as _os
from fastapi import Header

_TOKEN_ADMIN_SECRET = _os.environ.get("TOKEN_ADMIN_SECRET", "")

class _TokenRequest(BaseModel):
    sub:  str
    role: str = "reader"   # reader | writer | admin
    expires_minutes: int = 60


@app.post(
    "/api/v1/auth/token",
    tags=["auth"],
    summary="I1 — Genera JWT per test/sviluppo (richiede X-Admin-Secret header)",
)
async def generate_token(
    req: _TokenRequest,
    x_admin_secret: str = Header(default="", alias="X-Admin-Secret"),
):
    """
    Genera un JWT firmato. Richiede l'header X-Admin-Secret uguale alla
    variabile d'ambiente TOKEN_ADMIN_SECRET (se non impostata, endpoint disabilitato).
    """
    if not _TOKEN_ADMIN_SECRET:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Token generation disabled: set TOKEN_ADMIN_SECRET env var to enable.",
        )
    if x_admin_secret != _TOKEN_ADMIN_SECRET:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid X-Admin-Secret.",
            headers={"WWW-Authenticate": "X-Admin-Secret"},
        )
    if req.role not in ("reader", "writer", "admin"):
        raise HTTPException(status_code=400, detail="role deve essere reader | writer | admin")
    token = create_access_token(
        {"sub": req.sub, "role": req.role},
        expires_minutes=req.expires_minutes,
    )
    return {"access_token": token, "token_type": "bearer", "role": req.role}


# ── I4 — RAGAS Evaluation endpoint ───────────────────────────────────────────────

class _EvalRequest(BaseModel):
    query:        str
    answer:       str
    context:      str
    ground_truth: Optional[str] = None


@app.post(
    "/api/v1/eval",
    tags=["governance"],
    summary="I4 — Valutazione RAGAS: faithfulness, answer_relevancy, context_recall",
)
async def eval_endpoint(
    req: _EvalRequest,
    _user: TokenPayload = Depends(require_reader),
):
    from app.core.monitoring import record_eval

    result = await _eval_service.evaluate(
        query=req.query,
        answer=req.answer,
        context=req.context,
        ground_truth=req.ground_truth,
    )
    # Aggiorna Prometheus Gauge con rolling average
    recall_score = result.context_recall.score if result.context_recall else result.overall
    record_eval(
        faithfulness=result.faithfulness.score,
        relevancy=result.answer_relevancy.score,
        recall=recall_score,
    )
    # Registra osservazione nel tuner
    from app.tuning import auto_tuner
    auto_tuner.record_observation(
        params=auto_tuner.get_active_params(),
        faithfulness=result.faithfulness.score,
        relevancy=result.answer_relevancy.score,
        recall=result.context_recall.score if result.context_recall else None,
    )
    return result


# ── I7 — Token Budget info endpoint ─────────────────────────────────────────────────

@app.post(
    "/api/v1/admin/budget",
    tags=["governance"],
    summary="I7 — Diagnostica token budget per una richiesta ipotetica",
)
async def budget_info(
    context: str,
    query_text: str = "",
    budget: int = 3000,
    _user: TokenPayload = Depends(require_admin),
):
    from app.pipeline.token_budget import budget_info as _budget_info
    return _budget_info(context, query_text, budget)


# ── I8 — AutoRAGTuner endpoints ───────────────────────────────────────────────────

@app.get(
    "/api/v1/tuner/params",
    tags=["governance"],
    summary="I8 — Ritorna gli iperparametri RAG attualmente attivi",
)
async def tuner_params(_user: TokenPayload = Depends(require_reader)):
    from app.tuning import auto_tuner
    return {
        "active_params": auto_tuner.get_active_params(),
        "history":       auto_tuner.history_summary(),
    }


class _TunerObservation(BaseModel):
    params:       dict
    faithfulness: float
    relevancy:    float
    recall:       Optional[float] = None
    latency:      Optional[float] = None


@app.post(
    "/api/v1/tuner/record",
    tags=["governance"],
    summary="I8 — Registra un'osservazione manuale per il tuner",
)
async def tuner_record(
    obs: _TunerObservation,
    _user: TokenPayload = Depends(require_writer),
):
    from app.tuning import auto_tuner
    recorded = auto_tuner.record_observation(
        params=obs.params,
        faithfulness=obs.faithfulness,
        relevancy=obs.relevancy,
        recall=obs.recall,
        latency_seconds=obs.latency,
    )
    return {"recorded": recorded}


@app.post(
    "/api/v1/tuner/optimize",
    tags=["governance"],
    summary="I8 — Ricalcola iperparametri ottimali (UCB1 su storia RAGAS)",
)
async def tuner_optimize(_user: TokenPayload = Depends(require_admin)):
    from app.tuning import auto_tuner
    optimized = auto_tuner.optimize()
    return {"optimized_params": optimized, "history": auto_tuner.history_summary()}


# ── Chat persistence ───────────────────────────────────────────────────────

class _ChatCreate(BaseModel):
    title: str = "Nuova chat"

class _ChatRename(BaseModel):
    title: str

class _ChatMessage(BaseModel):
    role: str
    content: str
    meta: dict = {}


@app.post("/api/v1/chats", tags=["chat"], summary="Crea una nuova chat")
async def chat_create(
    body: _ChatCreate,
    user: TokenPayload = Depends(require_reader),
):
    chat_id = db.chat_create(user.sub, body.title)
    return {"chat_id": chat_id, "title": body.title}


@app.get("/api/v1/chats", tags=["chat"], summary="Lista chat dell'utente")
async def chat_list(user: TokenPayload = Depends(require_reader)):
    return db.chat_list(user.sub)


@app.patch("/api/v1/chats/{chat_id}", tags=["chat"], summary="Rinomina una chat")
async def chat_rename(
    chat_id: str,
    body: _ChatRename,
    user: TokenPayload = Depends(require_reader),
):
    ok = db.chat_rename(chat_id, user.sub, body.title)
    if not ok:
        raise HTTPException(status_code=404, detail="Chat non trovata")
    return {"ok": True}


@app.delete("/api/v1/chats/{chat_id}", tags=["chat"], summary="Elimina una chat")
async def chat_delete(
    chat_id: str,
    user: TokenPayload = Depends(require_reader),
):
    ok = db.chat_delete(chat_id, user.sub)
    if not ok:
        raise HTTPException(status_code=404, detail="Chat non trovata")
    return {"ok": True}


@app.get("/api/v1/chats/{chat_id}/messages", tags=["chat"], summary="Messaggi di una chat")
async def chat_messages_get(
    chat_id: str,
    user: TokenPayload = Depends(require_reader),
):
    return db.chat_messages_get(chat_id, user.sub)


@app.post("/api/v1/chats/{chat_id}/messages", tags=["chat"], summary="Appendi un messaggio")
async def chat_message_append(
    chat_id: str,
    msg: _ChatMessage,
    user: TokenPayload = Depends(require_reader),
):
    # verify ownership
    chats = db.chat_list(user.sub)
    if not any(c["chat_id"] == chat_id for c in chats):
        raise HTTPException(status_code=404, detail="Chat non trovata")
    db.chat_message_append(chat_id, msg.role, msg.content, msg.meta)
    return {"ok": True}

