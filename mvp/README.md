# Semantic RAG Engine — MVP

Un motore di retrieval-augmented generation (RAG) verticale su documenti PDF/Markdown, con pipeline avanzata, Knowledge Graph, cache semantica e interfaccia web.

---

## Architettura

```
┌─────────────────────────────────────────────────────────────────┐
│  NiceGUI Frontend  :8080                                        │
│  Chat · Dashboard · Documenti · Eval · Entità · Auto Tuner      │
└────────────────────────┬────────────────────────────────────────┘
                         │ HTTP/REST
┌────────────────────────▼────────────────────────────────────────┐
│  FastAPI Backend  :8000                                         │
│  Ingest · Query · Eval · KG · Tuner · Auth (JWT RBAC)           │
└──┬──────────┬──────────┬──────────┬──────────┬──────────────────┘
   │          │          │          │          │
   ▼          ▼          ▼          ▼          ▼
Qdrant    OpenSearch  PostgreSQL  Neo4j     Redis
(vector)  (BM25)      (meta/chat) (KG)      (cache)
   │
   ▼
MinIO          Ollama
(PDF store)    (LLM + Embed)
```

### Componenti del stack

| Servizio       | Ruolo                              | Porta       |
|----------------|------------------------------------|-------------|
| **FastAPI**    | Backend REST + pipeline RAG        | 8000        |
| **NiceGUI**    | Frontend single-page app           | 8080        |
| **PostgreSQL** | Metadati documenti + chat history  | 5432        |
| **Qdrant**     | Vector store (dense retrieval)     | 6333        |
| **OpenSearch** | BM25 full-text search              | 9200        |
| **Neo4j**      | Knowledge Graph                    | 7474 / 7687 |
| **Redis**      | Semantic cache                     | 6379        |
| **MinIO**      | Object storage PDF originali       | 9000 / 9001 |
| **Ollama**     | LLM locale + embedding             | 11434       |

---

## Prerequisiti

- Docker + Docker Compose v2
- Ollama installato localmente **oppure** avviato via Docker (incluso nel compose)
- Python 3.11+ (solo per sviluppo locale senza Docker)
- ~8 GB RAM libera, ~10 GB disco per modelli + dati

---

## Avvio rapido

```bash
# 1. Clona il repo
git clone <repo-url>
cd semantic-rag-engine/mvp

# 2. Avvia tutti i servizi
docker compose up -d

# 3. Prima installazione — scarica i modelli Ollama (~4 GB)
make pull-models

# 4. Apri il browser
# Frontend:   http://localhost:8080
# API docs:   http://localhost:8000/docs
# MinIO:      http://localhost:9001   (minioadmin / minioadmin)
# Qdrant:     http://localhost:6333/dashboard
# Neo4j:      http://localhost:7474
```

> **Credenziali default**: qualsiasi username, ruolo `reader` / `writer` / `admin`.

---

## Comandi utili

```bash
make up            # avvia i container
make down          # ferma i container (dati preservati)
make clean         # reset completo — cancella volumi
make status        # stato dei container
make pull-models   # scarica modelli Ollama (prima volta)
make list-models   # elenca modelli installati
make health        # check API health
make dev           # FastAPI in hot-reload (sviluppo locale)
```

---

## Ingestione documenti

### Via interfaccia web
Accedi a **http://localhost:8080** → sezione **Documenti** → drag & drop PDF/MD.

### Via API
```bash
curl -X POST http://localhost:8000/api/v1/ingest \
     -H "Authorization: Bearer <token>" \
     -F "file=@documento.pdf"
```

### Bulk ingest
```bash
python bulk_ingest.py --dir ./cartella-pdf --token <token>
```

---

## Pipeline di query

Ogni query attraversa questi stadi:

```
Intent detection
      │
      ▼
Query expansion (HyDE)
      │
      ▼
Hybrid retrieval: Qdrant (dense) + OpenSearch (BM25) → Rerank
      │
      ▼
Context compression + token budget
      │
      ▼
Semantic cache lookup (Redis)
      │
      ▼
LLM generation (Ollama)
      │
      ▼
Grounding check + confabulation detection
      │
      ▼
Citation extraction + risposta finale
```

### Esempio query via API

```bash
# 1. Login → ottieni token
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/token \
  -H "Content-Type: application/json" \
  -d '{"sub":"mario","role":"reader"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# 2. Query
curl -s -X POST http://localhost:8000/api/v1/query \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"question": "Qual è la metodologia descritta?"}' | python3 -m json.tool
```

---

## Configurazione

Le variabili d'ambiente sono gestite via `.env` (copia da `.env.example` se presente) o direttamente nel `docker-compose.yml`.

| Variabile          | Default           | Descrizione                    |
|--------------------|-------------------|--------------------------------|
| `CHAT_MODEL`       | `gemma4:latest`   | Modello LLM Ollama             |
| `EMBED_MODEL`      | `nomic-embed-text`| Modello embedding              |
| `POSTGRES_USER`    | `raguser`         | Utente PostgreSQL              |
| `POSTGRES_PASSWORD`| `ragpassword`     | Password PostgreSQL            |
| `MINIO_ACCESS_KEY` | `minioadmin`      | Chiave accesso MinIO           |
| `MINIO_SECRET_KEY` | `minioadmin`      | Secret MinIO                   |
| `API_BASE`         | `http://localhost:8000` | URL backend (frontend) |

---

## Struttura del progetto

```
mvp/
├── app/                    # Backend FastAPI
│   ├── core/               # Auth, cache, config, monitoring, Ollama
│   ├── ingestion/          # PDF parser, OCR fallback, chunking
│   ├── indexing/           # Tree index per gerarchie documentali
│   ├── knowledge/          # Knowledge Graph builder (entità + relazioni)
│   ├── models/             # Pydantic schemas
│   ├── pipeline/           # RAG pipeline (expansion, rerank, grounding…)
│   ├── prompts/            # Template prompt LLM
│   ├── services/           # RAG query service, eval RAGAS
│   ├── storage/            # Adapter: PostgreSQL, Qdrant, OpenSearch, Neo4j, MinIO
│   └── tuning/             # Auto-tuner UCB1
├── frontend/               # NiceGUI single-page app
│   ├── pages/              # chat, dashboard, ingest, eval, entities, tuner, sidebar
│   ├── api.py              # Client HTTP async verso il backend
│   ├── state.py            # Stato condiviso + CSS design system
│   └── main.py             # Entry point NiceGUI
├── data/                   # Thesaurus, vocabulary, tuner history
├── scripts/                # Utility (reindex, build tree index)
├── docker-compose.yml
├── Makefile
└── requirements.txt
```

---

## Funzionalità frontend

| Pagina         | Descrizione                                                  |
|----------------|--------------------------------------------------------------|
| **Chat**       | Chat persistente con storico, CRUD conversazioni, sorgenti   |
| **Dashboard**  | Salute servizi + metriche Prometheus real-time               |
| **Documenti**  | Upload drag & drop PDF/MD con progress                       |
| **Eval RAGAS** | Valutazione faithfulness, relevancy, recall                  |
| **Entità / KG**| Esplorazione Knowledge Graph, triple e contesto testuale     |
| **Auto Tuner** | Parametri attivi UCB1 + storico osservazioni                 |

---

## Sicurezza

- Autenticazione **JWT** (HS256) con ruoli: `reader`, `writer`, `admin`
- I ruoli limitano l'accesso alle operazioni di ingest e amministrazione
- Tutti i servizi sono isolati nella rete Docker interna

---

## Sviluppo locale (senza Docker per il backend)

```bash
# Installa dipendenze
pip install -r requirements.txt

# Avvia solo i servizi infrastruttura
docker compose up -d postgres qdrant minio redis opensearch neo4j ollama

# Avvia backend
uvicorn app.main:app --reload --port 8000

# Avvia frontend
python frontend/main.py
```
