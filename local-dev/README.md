# Semantic RAG Engine — Local Dev Stack

Setup locale per testare il **data layer (E-layer)** dell'architettura RAG prima di fare deployment su cloud.

## Prerequisiti

- Docker ≥ 24 e Docker Compose v2
- Python 3.12+
- ~6 GB di RAM libera (tutti i servizi insieme)

---

## Servizi inclusi

| Servizio | Porta | Componente architetturale | UI |
|---|---|---|---|
| **MinIO** | 9000 / 9001 | E1 Object Storage | http://localhost:9001 |
| **PostgreSQL 15** | 5432 | E4 Metadata Store | — |
| **Redis 7** | 6379 | Broker Celery + BB4 Status Tracker | — |
| **Qdrant** | 6333 | E2 Vector DB | http://localhost:6333/dashboard |
| **OpenSearch 2.15** | 9200 | E3 Keyword Index BM25 | — |
| **Neo4j 5.x** | 7474 / 7687 | C5 Knowledge Graph / E5 Tree Index | http://localhost:7474 |

---

## Avvio rapido

```bash
# 1. Entra nella directory
cd local-dev

# 2. Avvia lo stack
make up
# oppure: docker compose up -d

# 3. Attendi ~60 secondi (Neo4j e OpenSearch sono i più lenti ad avviarsi)
docker compose ps   # tutti i servizi devono essere "healthy"

# 4. Installa dipendenze Python
make install
# oppure: pip install -r requirements-test.txt

# 5. Esegui il test di integrazione completo
make test
# oppure: python test_stack.py
```

### Output atteso

```
================================================================
 Semantic RAG Engine — Local Stack Integration Test
 2026-05-11 10:30:00
================================================================

[1/6] MinIO — Object Storage (E1)
    ✓ Bucket 'rag-documents' già esistente
    ✓ PDF caricato → raw/<uuid>.pdf
    ✓ Metadati caricati → parsed/<uuid>_meta.json
    ✓ Integrità verificata: upload == download (byte-per-byte)
    ...

================================================================
 RIEPILOGO
================================================================
  [PASS] MinIO          Bucket 'rag-documents' OK · upload/download OK
  [PASS] PostgreSQL     Schema OK · insert/JOIN/delete OK
  [PASS] Redis          PING OK · hash set/get/TTL OK
  [PASS] Qdrant         Collection OK · 5 vettori · search filter OK
  [PASS] OpenSearch     Index OK · BM25 · filter OK
  [PASS] Neo4j          Bolt OK · Document+Concept · :MENTIONS OK

  6/6 servizi OK
================================================================
```

---

## Struttura bucket MinIO

Il bucket `rag-documents` rispecchia l'architettura E1:

```
rag-documents/
├── raw/           # PDF originali immutabili
├── parsed/        # Testo estratto, metadati JSON
└── artifacts/     # Output OCR, layout XML
```

---

## Comandi utili

```bash
make up        # Avvia stack
make down      # Ferma stack (mantiene dati)
make clean     # Ferma stack + rimuove volumi (reset)
make logs      # Log in tempo reale
make status    # Stato salute servizi
make test      # Esegui test integrazione
make install   # Installa dipendenze Python
```

---

## Credenziali default

| Servizio | User | Password |
|---|---|---|
| MinIO | `minioadmin` | `minioadmin` |
| PostgreSQL | `raguser` | `ragpassword` |
| Neo4j | `neo4j` | `ragpassword` |
| Redis | — | nessuna auth |
| OpenSearch | — | security disabilitata (dev only) |

> ⚠ Queste credenziali sono solo per sviluppo locale. Cambia tutto in `.env` prima di fare deploy.

---

## Prossimi passi

1. **Ingestione reale** — aggiungi i tuoi PDF nella cartella `raw/` e testa B2 (PDF Loader)
2. **Pipeline completa** — aggiungi Airflow + Celery worker al compose
3. **LLM locale** — aggiungi Ollama per test senza OpenAI API key
