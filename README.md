# Semantic RAG Engine

> Motore di Retrieval-Augmented Generation semantico, full-stack, con pipeline ibrida (vector + BM25 + graph) su documenti PDF/enterprise. Architettura evolutiva documentata in 7 versioni, dalla baseline alla multi-modale con knowledge graph causale.

---

## Struttura del repository

```
semantic-rag-engine/
├── mvp/                 # Applicazione deployabile (FastAPI + NiceGUI + Docker)
├── local-dev/           # Stack dati locale per test E-layer (no LLM)
├── architetture/        # Diagrammi Mermaid e documentazione architetturale (v1→v7)
├── papers/              # Paper di ricerca suddivisi per topic
├── .env.example         # Template variabili d'ambiente (nella cartella mvp/)
├── .gitignore
└── README.md
```

---

## Moduli

### `mvp/` — Applicazione MVP

Stack completo containerizzato. Tutto quello che serve per interrogare documenti con RAG avanzato.

| Componente | Tecnologia | Porta |
|---|---|---|
| Backend API | FastAPI + Python 3.12 | 8000 |
| Frontend | NiceGUI (dark UI) | 8080 |
| Vector store | Qdrant 1.10 | 6333 |
| Keyword index | OpenSearch 2.13 | 9200 |
| Metadata store | PostgreSQL 15 | 5432 |
| Knowledge graph | Neo4j 5 | 7474 / 7687 |
| Semantic cache | Redis 7 | 6379 |
| Object storage | MinIO | 9000 / 9001 |
| LLM + Embedding | Ollama (`gemma4`, `nomic-embed-text`) | 11434 |

**Avvio rapido:**
```bash
cd mvp
cp .env.example .env          # personalizza i valori se necessario
make up                        # avvia tutti i servizi Docker
make pull-models               # scarica i modelli Ollama (solo al primo avvio)
```

UI disponibile su → `http://localhost:8080`

Per i dettagli completi: [`mvp/README.md`](mvp/README.md)

---

### `local-dev/` — Stack dati locale

Docker Compose leggero per testare il **data layer** (MinIO, PostgreSQL, Redis, Qdrant, OpenSearch, Neo4j) senza avviare LLM e backend. Utile per sviluppo e integrazione.

```bash
cd local-dev
make up      # avvia i 6 servizi
make test    # esegue la suite di integrazione Python
make down    # ferma e rimuove i container
```

Per i dettagli: [`local-dev/README.md`](local-dev/README.md)

---

### `architetture/` — Evoluzione architetturale

Documentazione dell'architettura in 7 versioni iterative. Ogni versione aggiunge componenti basati su paper recenti (arXiv 2024-2026).

| Versione | Novità principali |
|---|---|
| v1 | Baseline RAG: vector + BM25 + rerank |
| v2 | Knowledge Graph, entity/relation extraction (GraphRAG) |
| v3 | Ontologia con SHACL, Tree Index, Bitemporal GraphDB, auto-ontology LLM |
| v4 | Multimodale (immagini, audio, tabelle), Thinking Traces Store, 3-Pass Pyramid Parser |
| v5 | Intent scoring (SURE-RAG), S2G iterative controller, SAGE chunking, semantic plan cache, EvoRAG KG backpropagation |
| v6 | Event-Causal RAG (streaming video), Parametric RAG (LoRA), FT-RAG (tabelle), Composable PRAG |
| v7 | Architettura completa unificata — diagramma Mermaid full-stack |

Documento tecnico completo: [`architetture/DOC_TECNICO_ARCHITETTURA_RAG_PDF.md`](architetture/DOC_TECNICO_ARCHITETTURA_RAG_PDF.md)

---

### `papers/` — Letteratura di riferimento

Paper arXiv e conference organizzati per area tematica:

```
01_rag_foundation/       Lewis et al. 2020 — RAG originale (NeurIPS)
02_rag_survey/           Survey panoramici su RAG
03_graph_rag/            GraphRAG, Edge et al. 2404.16130
04_advanced_rag/         HyDE, Self-RAG, CRAG, Step-Back
05_best_practices/       Wang et al. — chunking e best practices
06_agentic_rag/          RouteRAG, S2G-RAG, AutoSearch
07_embeddings_memory/    SmartVector, QuOTE, Thinking Traces
08_indexing_retrieval/   Ψ-RAG Tree Index, FT-RAG, SAGE
09_ontology_semantic/    Bitemporal Graph, Order-Aware Hypergraph
10_security/             CleanBase, TruthfulRAG, prompt injection defence
```

---

## Pipeline query (alto livello)

```
User Query
    │
    ├─► Intent & Complexity Scoring (SURE-RAG)
    │        └─► Semantic Plan Cache hit? → risposta immediata
    │
    ├─► Query Rewriting (HyDE / Step-back)
    ├─► Query Expansion (thesaurus + taxonomy)
    │
    ├─► Hybrid Retrieval
    │       ├── Vector (Qdrant) — cosine similarity
    │       ├── Keyword (OpenSearch) — BM25
    │       └── Graph Traversal (Neo4j) — entity/relation
    │
    ├─► Iterative Controller (S2G) — evidence sufficient?
    │       └─► Sub-query decomposition se insufficiente
    │
    ├─► Reranking + Context Compression
    ├─► Confabulation / Grounding check
    │
    └─► Generation (Ollama) + Citation → Response
```

---

## Requisiti

- Docker ≥ 24 + Docker Compose v2
- ~16 GB RAM (stack completo con Ollama)
- ~30 GB disco (modelli + indici)
- Python 3.12+ (opzionale, per script di sviluppo)

---

## Sicurezza

- Autenticazione JWT su tutte le API
- Input validation con Pydantic v2
- `.env` mai committato (vedi `.gitignore`)
- Audit log su ogni operazione di ingestione
- CleanBase pre-index gate (anomaly detection su embeddings)
