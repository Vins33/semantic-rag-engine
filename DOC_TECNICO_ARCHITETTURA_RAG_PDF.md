# Documento Funzionale Tecnico Architetturale
## Sistema RAG Verticale su PDF — Semantic RAG Engine

**Versione:** 1.0  
**Data:** 10 maggio 2026  
**Stato:** Bozza Tecnica Definitiva  

---

## Indice

1. [Sommario Esecutivo](#1-sommario-esecutivo)
2. [Obiettivi e Perimetro del Sistema](#2-obiettivi-e-perimetro-del-sistema)
3. [Vincoli e Assunzioni Architetturali](#3-vincoli-e-assunzioni-architetturali)
4. [Vista d'insieme dell'Architettura](#4-vista-dinsieme-dellarchitettura)
5. [Area 1 — Sorgenti PDF](#5-area-1--sorgenti-pdf)
6. [Area 2 — Pipeline di Ingestione PDF (Offline + Online)](#6-area-2--pipeline-di-ingestione-pdf)
7. [Area 3 — Layer Semantico](#7-area-3--layer-semantico)
8. [Area 4 — Processing dei Documenti](#8-area-4--processing-dei-documenti)
9. [Area 5 — Storage e Indicizzazione](#9-area-5--storage-e-indicizzazione)
10. [Area 6 — Query Pipeline Online](#10-area-6--query-pipeline-online)
11. [Area 6B — Controller Iterativo](#11-area-6b--controller-iterativo)
12. [Area 7 — Retrieval e Ranking](#12-area-7--retrieval-e-ranking)
13. [Area 7B — Compressione del Contesto](#13-area-7b--compressione-del-contesto)
14. [Area 8 — Generazione e Validazione](#14-area-8--generazione-e-validazione)
15. [Area 9 — Governance e Feedback](#15-area-9--governance-e-feedback)
16. [Flussi Dati Principali](#16-flussi-dati-principali)
17. [Stack Tecnologico](#17-stack-tecnologico)
18. [Interfacce API](#18-interfacce-api)
19. [Schema Dati e Modelli](#19-schema-dati-e-modelli)
20. [Sicurezza e Conformità](#20-sicurezza-e-conformità)
21. [Performance e Scalabilità](#21-performance-e-scalabilità)
22. [Deployment e Infrastruttura](#22-deployment-e-infrastruttura)
23. [Metriche di Valutazione](#23-metriche-di-valutazione)
24. [Piano di Sviluppo a Fasi](#24-piano-di-sviluppo-a-fasi)
25. [Dipendenze e Rischi](#25-dipendenze-e-rischi)

---

## 1. Sommario Esecutivo

Il **Semantic RAG Engine** è un sistema di Retrieval-Augmented Generation (RAG) verticale, progettato esclusivamente per documenti PDF come sorgente informativa. Il sistema consente di porre domande in linguaggio naturale su un corpus di PDF aziendali, normativi o tecnici e ricevere risposte accurate, tracciate e con citazioni verificabili alle pagine sorgente.

L'architettura integra le più recenti tecniche di ricerca (2024–2026) in materia di RAG, embedding semantici, knowledge graph, compressione del contesto e governance enterprise, combinandole in una pipeline coerente e modulare.

**Capacità chiave del sistema:**
- Ingestione automatica di PDF da filesystem, repository enterprise (SharePoint, Confluence) e web
- Comprensione semantica profonda tramite ontologie e knowledge graph costruiti automaticamente
- Retrieval multi-segnale (vettoriale, keyword, metadata, gerarchico) con reranking confidence-aware
- Generazione di risposte grounded, citate e verificate per dominio (compliance, legale, tecnico)
- Governance completa: RBAC, audit trail Merkle, monitoraggio costi token, ottimizzazione Bayesiana

---

## 2. Obiettivi e Perimetro del Sistema

### 2.1 Obiettivi Funzionali

| ID | Obiettivo | Priorità |
|----|-----------|----------|
| OF-01 | Ingestione automatica di PDF da più sorgenti con deduplicazione e versionamento | Alta |
| OF-02 | Estrazione di testo strutturato, tabelle e metadati da PDF nativi e scansionati | Alta |
| OF-03 | Costruzione automatica di ontologia e knowledge graph dal corpus | Alta |
| OF-04 | Chunking semantico adattivo con embedding confidence-aware | Alta |
| OF-05 | Risposta a domande in linguaggio naturale con citazioni a pagina e chunk | Alta |
| OF-06 | Rilevamento e gestione di contraddizioni tra documenti diversi | Media |
| OF-07 | Verifica di conformità normativa nelle risposte (compliance check) | Media |
| OF-08 | Feedback utente per miglioramento continuo del knowledge graph | Media |
| OF-09 | Ottimizzazione automatica Bayesiana dei parametri RAG | Bassa |

### 2.2 Obiettivi Non-Funzionali

| ID | Obiettivo | Target |
|----|-----------|--------|
| ONF-01 | Latenza risposta p95 (query online) | < 3 secondi |
| ONF-02 | Throughput ingestione PDF | ≥ 100 pagine/minuto per worker |
| ONF-03 | Precisione retrieval (Precision@5) | ≥ 0.85 |
| ONF-04 | Hallucination rate | < 5% |
| ONF-05 | Disponibilità sistema (uptime) | ≥ 99.5% |
| ONF-06 | Tracciabilità completa di ogni risposta | 100% claim tracciati |
| ONF-07 | Conformità GDPR e accesso RBAC | Obbligatoria |

### 2.3 Perimetro — In Scope

- Documenti PDF come unica sorgente (nativi digitali e scansionati)
- Interfaccia query in linguaggio naturale via API REST
- Pipeline di ingestione offline schedulata e on-demand
- Knowledge graph locale, non federato
- LLM come servizio esterno (GPT-4o, Claude, Llama-3) via API

### 2.4 Perimetro — Out of Scope

- Sorgenti multimodali (immagini, video, audio standalone)
- Graph store distribuiti o federati
- Fine-tuning o LoRA parametrici
- Agentic loop multi-step autonomo
- Streaming/real-time document ingestion

---

## 3. Vincoli e Assunzioni Architetturali

### 3.1 Vincoli

- **C-01:** I PDF scansionati richiedono OCR; la qualità dell'OCR condiziona la qualità del retrieval.
- **C-02:** Il modello LLM per la generazione è accessibile via API (non self-hosted per default); la latenza dipende dal provider.
- **C-03:** Il knowledge graph è locale al corpus; non integra fonti esterne per default.
- **C-04:** Il budget token per query è configurabile e vincolante per il controller F6D.
- **C-05:** L'accesso ai PDF è soggetto a RBAC; solo i PDF autorizzati per l'utente sono accessibili in retrieval.

### 3.2 Assunzioni

- **A-01:** I PDF sono in italiano e/o inglese (altri linguaggi richiedono estensione dei modelli embedding).
- **A-02:** La qualità dell'estrazione tabelle dipende dalla struttura del PDF; tabelle in immagine richiedono OCR specializzato.
- **A-03:** Il corpus è prevalentemente statico con aggiornamenti periodici (non real-time streaming).
- **A-04:** L'infrastruttura sottostante supporta containerizzazione Docker/Kubernetes.

---

## 4. Vista d'insieme dell'Architettura

### 4.1 Macro-Architettura

Il sistema è strutturato in due pipeline principali e un layer trasversale di governance:

```
┌─────────────────────────────────────────────────────────┐
│              PIPELINE OFFLINE (INGESTIONE)               │
│  Sorgenti → Ingestione → Layer Semantico → Processing    │
│                       → Storage & Indicizzazione         │
└─────────────────────────────────────────────────────────┘
                           │ indici
                           ▼
┌─────────────────────────────────────────────────────────┐
│              PIPELINE ONLINE (QUERY)                     │
│  Query → Intent Gate → Retrieval → Ranking → Compressione│
│                    → Generazione → Validazione → Risposta │
└─────────────────────────────────────────────────────────┘
                           │
┌─────────────────────────────────────────────────────────┐
│         LAYER TRASVERSALE GOVERNANCE E FEEDBACK          │
│  RBAC · Audit · Monitoring · Evaluation · Security       │
│  Feedback Loop · Token Budget · AutoTuner                │
└─────────────────────────────────────────────────────────┘
```

### 4.2 Principi Architetturali

| Principio | Descrizione |
|-----------|-------------|
| **Separation of Concerns** | Pipeline offline e online sono disaccoppiate; comunicano solo tramite store condivisi |
| **Fail-Safe** | In caso di fallimento del retrieval, il sistema risponde con incertezza esplicita anziché allucinare |
| **Auditability by Design** | Ogni chunk, ogni embedding, ogni risposta è tracciata con provenienza e hash |
| **Cost Awareness** | Il token budget è un cittadino di prima classe; ogni componente lo rispetta |
| **Semantic Enrichment** | Il layer semantico è costruito automaticamente e si aggiorna via feedback |

---

## 5. Area 1 — Sorgenti PDF

### 5.1 Descrizione

Le sorgenti rappresentano i punti di origine fisici o logici dei documenti PDF che alimentano il sistema.

### 5.2 Componenti

#### B1-SRC-01 — PDF Locali
- **Tipo:** Filesystem locale, cartelle condivise di rete (NAS, CIFS/NFS)
- **Accesso:** Scansione ricorsiva di directory configurate; supporto glob pattern per inclusione/esclusione
- **Scheduling:** Watcher basato su inotify (Linux) / FSEvents (macOS) per ingestione real-time; cron job per batch notturno
- **Identificazione duplicati:** Hash SHA-256 del file raw; se hash già presente in E1, skip o versioning

#### B1-SRC-02 — PDF da Repository Enterprise
- **Tipo:** SharePoint Online, Confluence Cloud/Server, portali documentali custom
- **Protocollo:** Microsoft Graph API v1.0 per SharePoint; Confluence REST API v2
- **Autenticazione:** OAuth 2.0 con token refresh; credenziali in secret vault (Vault/AWS Secrets Manager)
- **Filtro accessi:** Le permission del repository sorgente vengono mappate sul RBAC interno (I1)

#### B1-SRC-03 — PDF da Web / API
- **Tipo:** arXiv, portali normativi (EUR-Lex, Gazzetta Ufficiale), portali tecnici
- **Meccanismo:** Scheduler HTTP con retry esponenziale; rispetto di robots.txt e rate limiting
- **Deduplicazione:** URL canonico + hash contenuto; cache locale per evitare re-download
- **Integrità:** Verifica ETag/Last-Modified HTTP per aggiornamenti incrementali

### 5.3 Contratto Output

Ogni sorgente produce un evento di tipo `PDFIngestionRequest`:

```json
{
  "source_type": "local|enterprise|web",
  "raw_path": "s3://bucket/raw/document.pdf",
  "source_uri": "https://...",
  "fetched_at": "2026-05-10T14:30:00Z",
  "sha256": "a3f4...",
  "acl": ["user:alice", "group:legal"],
  "metadata_hints": {
    "author": "...",
    "date": "...",
    "language": "it"
  }
}
```

---

## 6. Area 2 — Pipeline di Ingestione PDF (Offline + Online)

### 6.1 Descrizione

La pipeline di ingestione è articolata in **tre sotto-aree**:

- **2A — Modalità Offline (Batch):** trigger automatici per ingestione schedulata e massiva, senza SLA stretto sulla latenza
- **2B — Modalità Online (Real-time):** trigger manuali o event-driven per ingestione immediata, con SLA < 60s per PDF standard
- **2C — Pipeline Condivisa:** fasi di elaborazione comuni a entrambe le modalità, a partire dal connettore di accesso

### 6.2 Componenti — Area 2A (Offline Batch)

#### BA1 — Filesystem Watcher
- **Funzione:** Monitoraggio in tempo reale di directory locali e mount remoti per rilevare nuovi PDF o modifiche
- **Meccanismo:** `inotify` (Linux) / `FSEvents` (macOS) per eventi in tempo reale; polling con intervallo configurabile (default 5 min) per NAS CIFS/NFS che non supportano inotify
- **Filtro:** Pattern glob configurabili per inclusione/esclusione (es. `*.pdf`, `!archivio/**`)
- **Deduplicazione:** Hash SHA-256 confrontato con E4 prima di accodare; se identico → skip

#### BA2 — Scheduler Batch
- **Funzione:** Orchestrazione di scansioni ricorsive programmate su directory configurate e sorgenti enterprise
- **Tecnologia:** Apache Airflow 2.9 — DAG `pdf_batch_ingest` con scheduling cron configurabile (default: `0 2 * * *` — ogni notte alle 02:00)
- **Scope:** PDF Locali (A1), PDF Web/API (A3), scansioni periodiche di SharePoint/Confluence (A2)
- **Parallelismo:** Fino a N worker Airflow configurabili; ogni task è un documento PDF
- **Idempotenza:** Il DAG verifica SHA-256 su E4 prima di processare; re-run sicuro

#### BA3 — Bulk Import
- **Funzione:** Caricamento massivo di grandi volumi di PDF in una singola operazione
- **Modalità di input:**
  - Cartella locale/NFS montata: scansione ricorsiva con `find`/`glob`
  - File ZIP: estrazione in-memory, processamento sequenziale dei PDF contenuti
  - API batch: endpoint `POST /api/v1/ingest/batch` con lista di URL o path
- **Priorità:** Bassa — usa la coda batch BA4; non impatta le ingestioni online BB3
- **Progress tracking:** Job Airflow con log progressivo; notifica su completamento

#### BA4 — Coda Batch (Celery low-priority)
- **Tecnologia:** Celery 5.3 con Redis 7 come broker; coda denominata `ingest_low`
- **Caratteristiche:**
  - Priorità bassa — i task di BA4 cedono il passo a BB3
  - Concurrency: default 4 worker; scalabile tramite Kubernetes HPA su lunghezza coda
  - Retry policy: max 3 tentativi con backoff esponenziale (30s, 5min, 30min)
  - Dead-letter queue per PDF non processabili dopo 3 tentativi
- **Nessun SLA stretto:** latenza di ingestione accettabile nell'ordine di minuti/ore

### 6.3 Componenti — Area 2B (Online Real-time)

#### BB1 — API Upload REST
- **Funzione:** Endpoint REST per upload diretto di PDF da parte di utenti o sistemi integrati
- **Endpoint:** `POST /api/v1/ingest` — `multipart/form-data` con `file` (PDF binario) + `metadata` (JSON opzionale)
- **Dimensione massima:** 50 MB per richiesta (configurabile); PDF più grandi → redirect a BA3 (bulk)
- **Autenticazione:** JWT Bearer obbligatorio; ACL ricavata dai gruppi del token
- **Risposta sincrona:** HTTP 202 Accepted con `{job_id, status_url, estimated_seconds}`
- **Sicurezza:** Scan antivirus (ClamAV) sul file prima di accodare; I6 esegue anomaly check

#### BB2 — Webhook Push
- **Funzione:** Ricezione di eventi push da sistemi enterprise (SharePoint, Confluence) su creazione/modifica documenti PDF
- **Endpoint registrazione:** `POST /api/v1/webhooks/register` — registra URL callback e tipo evento
- **Protocollo:** HTTP POST JSON con payload evento; verifica firma HMAC-SHA256 sul body
- **Payload evento atteso:**
  ```json
  {
    "event": "document.created|document.updated",
    "source": "sharepoint|confluence",
    "doc_url": "https://...",
    "triggered_at": "2026-05-10T14:30:00Z"
  }
  ```
- **Retry webhook:** Se il sistema non risponde 200 entro 5s → retry fino a 5 volte con backoff

#### BB3 — Coda Prioritaria (Celery high-priority)
- **Tecnologia:** Celery 5.3 + Redis 7; coda denominata `ingest_high` con priorità numerica 9 (max)
- **SLA:** < 60 secondi per PDF standard (≤ 20 pagine, nativo digitale); < 180s con OCR
- **Preemption:** I worker monitorano entrambe le code; BA4 è interrotta se BB3 ha task in attesa
- **Scalabilità:** Auto-scaling Kubernetes HPA su queue depth > 5 task → aggiunge worker entro 30s
- **Circuit breaker:** Se il processing fallisce per > 10% dei task in 5 minuti → alert I3; coda pausa automatica

#### BB4 — Status Tracker
- **Funzione:** Espone lo stato di avanzamento di ogni job di ingestione online
- **Storage stato:** Redis hash `ingest:job:{job_id}` con TTL 24h
  ```json
  {
    "job_id": "uuid",
    "status": "queued|processing|completed|failed",
    "progress_pct": 65,
    "current_step": "D5_chunking",
    "started_at": "...",
    "completed_at": null,
    "error": null,
    "doc_id": "uuid"
  }
  ```
- **Modalità di consumo:**
  - **Polling:** `GET /api/v1/ingest/{job_id}/status` — risponde con stato corrente
  - **Webhook callback:** Se il client ha registrato un `callback_url`, il sistema chiama `POST {callback_url}` su completamento
- **Webhook callback payload:**
  ```json
  {
    "job_id": "uuid",
    "status": "completed",
    "doc_id": "uuid",
    "duration_seconds": 23
  }
  ```

### 6.4 Confronto Modalità

| Caratteristica | 2A Offline Batch | 2B Online Real-time |
|---------------|-----------------|---------------------|
| Trigger | Automatico (watcher, cron) | Manuale (API) o push (webhook) |
| SLA ingestione | Nessuno (minuti/ore) | < 60s PDF standard |
| Priorità coda | Bassa (`ingest_low`) | Alta (`ingest_high`) |
| Feedback avanzamento | Log Airflow, batch report | Polling status, webhook callback |
| Caso d'uso tipico | Indicizzazione corpus iniziale, aggiornamenti notturni | Upload urgente utente, evento SharePoint |
| Scala tipica | 100–10.000 PDF/giorno | 1–50 PDF/ora |

### 6.5 Componenti — Area 2C (Pipeline Condivisa)

#### B1 — Connettore PDF (Access Control)
- **Funzione:** Gateway di ingresso; verifica l'autorizzazione della sorgente e dell'utente/servizio richiedente
- **Integrazione con I1:** Prima di caricare qualsiasi PDF, il connettore verifica le policy RBAC
- **Output:** PDF raw archiviato in E1 (Object Storage) con metadati di accesso

#### B2 — PDF Loader
- **Librerie primarie:** `PyMuPDF` (fitz) per PDF nativi digitali — alta fedeltà, accesso a struttura interna
- **Librerie fallback:** `pdfplumber` per tabelle complesse; `PDFMiner` per layout di testo legacy
- **Logica di selezione:** Euristica basata su dimensione file, numero pagine, presenza di font embedded
- **Output:** Struttura a pagine con text layer grezzo, bounding box, font info

#### B3 — Parser Testo + Layout
- **Funzione:** Estrae gerarchia strutturale del documento (H1/H2/H3, paragrafi, liste, didascalie)
- **Algoritmo:** Analisi font-size e font-weight per inferire heading level; analisi indentazione per liste
- **Output:** Albero strutturale `DocumentTree` con nodi tipizzati (heading, paragraph, list_item, caption, footer)
- **Artefatti filtrati in B5:** Header/footer ripetuti, numeri di pagina, watermark testuali, boilerplate legale standard

#### B4 — OCR (se necessario)
- **Trigger:** Rilevamento di PDF scansionati (assenza di text layer, presenza di immagini raster full-page)
- **Engine primario:** `Tesseract` v5 con modelli LSTM per italiano/inglese
- **Engine cloud (alta qualità):** Azure Document Intelligence (Form Recognizer) per documenti complessi (moduli, contratti, fatture)
- **Post-processing OCR:** Correzione errori comuni via dizionario di dominio; confidence score per carattere
- **Output:** Testo OCR archiviato come layer aggiuntivo, con mappa di confidenza per zona

#### B5 — Pulizia Testo
- **Operazioni:**
  - Rimozione header/footer ricorrenti (rilevati tramite frequenza e posizione)
  - Normalizzazione spazi, unicode, encoding
  - Rimozione artefatti di conversione (es. ligature rotte, caratteri invisibili)
  - Strip di boilerplate: disclaimer standard, pagine di copertina vuote
- **Implementazione:** Pipeline di trasformazioni sequenziali con regex e heuristic rules; configurabili per dominio

#### B6 — Estrazione Tabelle
- **Libreria primaria:** `camelot-py` per tabelle con bordi visibili (lattice mode)
- **Libreria fallback:** `pdfplumber` per tabelle senza bordi (stream mode, basata su whitespace)
- **Output formato:** Struttura tabellare serializzata come JSON con righe, colonne, header, valori
- **Integrazione successiva:** Le tabelle estratte sono input sia per D5 (chunking) che per D2 (relation extraction)

#### B7 — Source Provenance
- **Hash documento:** SHA-256 del PDF raw (pre-processing)
- **Hash testo:** SHA-256 del testo estratto post-pulizia
- **Metadati di provenienza:** URL originale, nome file, data download, sorgente tipo
- **Registrazione in E6:** Ogni documento entra nell'Audit Log con hash iniziale; le modifiche successive formano la catena Merkle

#### B8 — Versioning Documento
- **Schema versione:** `{document_id}.v{n}` con incremento a ogni ingestione di un aggiornamento
- **Rilevamento aggiornamenti:** Confronto SHA-256 con versione precedente; se diverso → nuova versione
- **Policy di retention:** Configurabile; default: mantieni ultime 5 versioni; le versioni scadute passano in archivio freddo
- **Output evento:** `DocumentVersionedEvent` con `doc_id`, `version`, `prev_version`, `diff_summary`

---

## 7. Area 3 — Layer Semantico

### 7.1 Descrizione

Il Layer Semantico è il "cervello del dominio" del sistema. Fornisce il vocabolario controllato, la tassonomia, le relazioni semantiche e l'ontologia che guidano sia il processing offline che la query expansion online. È costruito automaticamente dall'Auto-Builder (C6) e arricchito dal feedback.

### 7.2 Componenti

#### C1 — Vocabolario Controllato
- **Contenuto:** Elenco di termini ammessi per il dominio (es. legale, finanziario, tecnico), con alias e acronimi
- **Formato storage:** SKOS (Simple Knowledge Organization System) serializzato in Turtle/JSON-LD
- **Utilizzo:** Normalizzazione dei termini in D3 (classificazione dominio) e F4 (query expansion)
- **Esempio:**
  ```turtle
  :GDPR a skos:Concept ;
    skos:prefLabel "GDPR"@it ;
    skos:altLabel "Regolamento Generale sulla Protezione dei Dati"@it ;
    skos:altLabel "General Data Protection Regulation"@en .
  ```

#### C2 — Tassonomia
- **Struttura:** Gerarchia padre-figlio di concetti; ogni nodo ha BT (broader term) e NT (narrower term)
- **Profondità tipica:** 3–5 livelli per dominio tecnico/legale
- **Utilizzo:** Guida il tree retrieval (G4) e arricchisce i metadati di classificazione (D3)

#### C3 — Thesaurus
- **Contenuto:** Sinonimi, termini correlati (RT), termini più ampi (BT), termini più specifici (NT)
- **Standard:** ANSI/NISO Z39.19 per struttura thesaurus
- **Utilizzo online:** Query expansion (F4) — aggiunge sinonimi e varianti alla query originale

#### C4 — Ontologia Leggera
- **Standard:** OWL 2 RL (regole Horn-like per motori rule-based) + SHACL per vincoli di validazione
- **Classi principali:** `Document`, `Concept`, `Entity`, `Regulation`, `Organization`, `Person`, `Date`, `Amount`
- **Proprietà chiave:** `mentions`, `issuedBy`, `effectiveDate`, `supersedes`, `contradicts`, `relatedTo`
- **Validazione SHACL:** Ogni tripla generata automaticamente viene validata prima dell'inserimento in C5

#### C5 — Knowledge Graph Locale
- **Storage:** RDF triplestore embedded (Apache Jena TDB2) o graph DB (Neo4j con plugin RDF)
- **Contenuto:** Entità estratte dai PDF, relazioni semantiche, provenienza (quale PDF, quale pagina)
- **Query language:** SPARQL 1.1 per interrogazioni semantiche; Cypher per graph traversal (se Neo4j)
- **Aggiornamento:** Append-only durante l'ingestione; consolidamento notturno; feedback utente (I5) applica patch

#### C6 — Auto-Builder Ontologia
- **Pipeline automatica** (basata su Salovskii et al. arXiv 2604.20795):
  1. **Entity Recognition:** NER su testo estratto (modello spaCy fine-tuned o LLM-based)
  2. **Relation Extraction:** Identificazione di relazioni semantiche tra entità via modello RE
  3. **Triple Generation:** Costruzione di triple RDF `(soggetto, predicato, oggetto)`
  4. **SHACL Validation:** Verifica conformità all'ontologia C4 prima di inserire in C5
  5. **Deduplicazione:** Coreference resolution per unificare menzioni della stessa entità
- **Trigger:** Eseguito dopo ogni batch di ingestione; risultati alimentano C1, C4, C5

---

## 8. Area 4 — Processing dei Documenti

### 8.1 Descrizione

Il Processing dei Documenti trasforma il testo strutturato (output dell'Area 2) in unità semantiche indicizzabili: entità, relazioni, metadati arricchiti, chunk e embedding.

### 8.2 Componenti

#### D1 — Entity Extraction
- **Approccio:** GraphRAG (Edge et al. arXiv 2404.16130) — LLM-assisted entity extraction con prompt strutturati
- **Tipi di entità:** Persona, Organizzazione, Luogo, Data, Norma, Concetto, Importo, Prodotto
- **Output:** Lista di entità con tipo, testo superficie, offset nel documento, confidence score
- **Feed a C6:** Le entità sono input primario per l'Auto-Builder dell'ontologia

#### D2 — Relation Extraction
- **Approccio:** Triple `(soggetto, predicato, oggetto)` estratte da frasi tramite LLM con schema guidato
- **Predicati supportati:** `regola`, `vieta`, `richiede`, `definisce`, `abroga`, `modifica`, `contraddice`, `èParteRi`, `hannoRuolo`
- **Filtraggio:** Solo relazioni con confidence ≥ 0.7 entrano nel KG (C5)
- **Output:** Lista di triple con provenienza (documento, pagina, frase)

#### D3 — Classificazione Dominio
- **Classi:** Finanziario, Legale, Tecnico, Medico, HR, Compliance, General
- **Modello:** Classifier fine-tuned su dataset interno + zero-shot LLM fallback
- **Utilizzo:** Tag sul documento e sui chunk; usato in G3 (metadata filtering) per limitare il retrieval al dominio pertinente

#### D4 — Arricchimento Metadati
- **Metadati estratti:**
  - `author`: autore/i del documento
  - `creation_date`: data di creazione
  - `language`: ISO 639-1 (rilevato via langdetect)
  - `domain`: output di D3
  - `topic_tags`: top-5 parole chiave TF-IDF / KeyBERT
  - `document_type`: contratto / norma / manuale / report / articolo
  - `page_count`, `word_count`
- **Storage:** PostgreSQL (E4) con indici su tutti i campi filtrabili

#### D5 — SAGE Semantic Chunking
- **Algoritmo:** SAGE (arXiv 2604.15583) — chunking guidato da "attenzione selettiva" del modello
  - Identifica i **span task-relevant** a index-time tramite saliency scoring
  - Elimina sezioni a bassa salienza (boilerplate, transizioni vuote) durante la costruzione del chunk
  - Preserva span ad alta salienza con contesto minimo necessario
- **Parametri default:**
  - Chunk size target: 512 token
  - Overlap: 128–256 token (configurabile via AutoRAGTuner I8)
  - Unità semantica minima: paragrafo completo (no mid-sentence splits)
- **Chunk speciali:**
  - Tabelle estratte in B6 → chunk dedicati con header preservato
  - Sezioni normative → chunk allineati agli articoli/commi
- **Metadati chunk:**
  ```json
  {
    "chunk_id": "uuid",
    "doc_id": "...",
    "doc_version": 3,
    "page_start": 12,
    "page_end": 13,
    "section_title": "Art. 5 — Responsabilità del Titolare",
    "domain": "Legale",
    "saliency_score": 0.87,
    "token_count": 498
  }
  ```

#### D6 — Embedding Generation
- **Modello primario:** `text-embedding-3-large` (OpenAI) o `multilingual-e5-large` per corpus italiano
- **QuOTE alignment** (arXiv 2502.10976): gli embedding sono orientati alle domande tipiche del dominio (question-oriented), non solo al testo
- **SmartVector** (arXiv 2604.20598): ogni embedding è arricchito con:
  - `timestamp`: data di generazione
  - `confidence_score`: basato su qualità OCR, coerenza semantica, copertura ontologica
  - `decay_factor`: decadimento Ebbinghaus per documenti datati (configurabile)
- **Dimensionalità:** 3072 (text-embedding-3-large) o 1024 (E5-large)
- **Batch size:** 256 chunk per batch; parallelizzazione su GPU se disponibile

---

## 9. Area 5 — Storage e Indicizzazione

### 9.1 Descrizione

Il layer di storage è composto da sei store specializzati, ciascuno ottimizzato per un tipo specifico di accesso.

### 9.2 Componenti

#### E1 — Object Storage
- **Contenuto:** PDF raw (originali non modificati) + artefatti di parsing (testo estratto, tabelle JSON)
- **Tecnologia:** Filesystem S3-compatible (MinIO self-hosted o AWS S3)
- **Struttura bucket:**
  ```
  bucket/
  ├── raw/           # PDF originali, immutabili
  ├── parsed/        # Testo estratto, tabelle JSON, metadati B7/B8
  └── artifacts/     # OCR output, layout XML
  ```
- **Retention policy:** Raw PDF mai eliminati; artefatti con TTL configurabile

#### E2 — Vector DB
- **Tecnologia primaria:** `Qdrant` (self-hosted su Kubernetes) — supporto nativo a payload filtering, named vectors, quantizzazione
- **Alternative:** `Milvus` per scala molto elevata (>100M vettori); `ChromaDB` per sviluppo locale
- **Collection structure:**
  ```
  Collection: pdf_chunks
  - vector: float32[3072]   # embedding principale
  - payload:
      chunk_id, doc_id, doc_version, page_start, page_end,
      domain, author, date, confidence_score, decay_factor,
      section_title, token_count
  ```
- **Confidence decay:** Embedding con `decay_factor` < threshold sono de-prioritizzati nel ranking G6
- **Aggiornamento:** Upsert per nuove versioni documento; soft-delete per versioni scadute

#### E3 — Keyword Index (BM25)
- **Tecnologia:** `OpenSearch` 2.x o `Elasticsearch` 8.x
- **Index mapping:** Campi analizzati per italiano/inglese con synonym filter (dal Thesaurus C3)
- **BM25 parameters:** k1=1.5, b=0.75 (default Lucene, tunable via I8)
- **Campi indicizzati:** `text_content`, `section_title`, `author`, `topic_tags`
- **Update strategy:** Index refresh ogni 30 secondi; bulk indexing per ingestione batch

#### E4 — Metadata Store
- **Tecnologia:** `PostgreSQL` 15 con estensione `pg_trgm` per ricerca fuzzy
- **Schema principale:**
  ```sql
  TABLE documents (
    doc_id        UUID PRIMARY KEY,
    sha256_raw    CHAR(64) UNIQUE,
    source_uri    TEXT,
    source_type   VARCHAR(20),
    title         TEXT,
    author        TEXT[],
    creation_date DATE,
    language      CHAR(2),
    domain        VARCHAR(30),
    doc_type      VARCHAR(30),
    page_count    INTEGER,
    version       INTEGER,
    ingested_at   TIMESTAMPTZ,
    acl           JSONB
  );

  TABLE chunks (
    chunk_id      UUID PRIMARY KEY,
    doc_id        UUID REFERENCES documents,
    page_start    INTEGER,
    page_end      INTEGER,
    section_title TEXT,
    token_count   INTEGER,
    saliency_score FLOAT,
    confidence_score FLOAT
  );
  ```
- **Indici:** B-tree su `domain`, `language`, `creation_date`; GIN su `acl`; trigram su `author`, `title`

#### E5 — Hierarchical Tree Index (Ψ-RAG)
- **Base:** Ψ-RAG (arXiv 2605.00529, ICML 2026) — indice ad albero multi-granularità
- **Struttura:** Token → Frase → Paragrafo → Sezione → Documento
- **Cross-document links:** Nodi dello stesso livello in documenti diversi sono collegati se semanticamente correlati (cosine similarity > soglia)
- **Operazioni chiave:**
  - `merge`: unisce nodi di granularità inferiore in nodi di granularità superiore
  - `collapse`: rimuove nodi ridondanti preservando la copertura semantica
- **Storage:** Neo4j (modalità graph) o PostgreSQL con LTREE extension (modalità leggera)
- **Alimentazione:** I chunk di D5 entrano come nodi foglia; il KG di C5 aggiunge cross-document links

#### E6 — Audit Log (Merkle Hash Chain)
- **Struttura:** Ogni entry è `{timestamp, event_type, doc_id, chunk_id, action, actor, prev_hash, current_hash}`
- **Catena Merkle:** `current_hash = SHA256(prev_hash + payload)` — garantisce immutabilità retroattiva
- **Storage:** PostgreSQL append-only table con check trigger che previene UPDATE/DELETE
- **Utilizzo:** I2 (Data Lineage) legge da E6 per ricostruire la storia di ogni documento

---

## 10. Area 6 — Query Pipeline Online

### 10.1 Descrizione

La Query Pipeline Online gestisce l'elaborazione di ogni richiesta utente, dall'analisi dell'intent alla preparazione del piano di retrieval.

### 10.2 Componenti

#### F1 — Query Utente
- **Input formati accettati:**
  - Domanda in linguaggio naturale (testo libero)
  - Domanda semi-strutturata con hint di filtro (es. `"autore:Rossi dopo:2025-01-01 ...testo..."`  )
- **Contesto opzionale:** Session history (ultime 5 interazioni) per query multi-turn
- **Pre-processing:** Normalizzazione unicode, rimozione caratteri di controllo, troncamento a max 512 token

#### F2 — Intent + Complexity Gate (SURE-RAG)
- **Base:** SURE-RAG (arXiv 2605.03534) — valuta se il retrieval è necessario
- **Logica decisionale:**
  1. **Sufficiency check:** La query è rispondibile con la session history o la conoscenza parametrica del LLM? Se sì → risponde direttamente senza retrieval
  2. **Uncertainty check:** Il sistema ha alta incertezza sulla risposta? Se sì → retrieval obbligatorio
  3. **Complexity classification:** Domanda semplice (single-hop) vs. complessa (multi-hop, confronto, riepilogo)
- **Output:** `{retrieval_needed: bool, complexity: simple|multi_hop|comparison|summary, intent_tags: [...]}`
- **Integrazione I7:** Prima di procedere, verifica disponibilità del token budget

#### F3 — Query Rewriting
- **Tecniche applicate:**
  - **HyDE (Hypothetical Document Embeddings):** Genera un documento ipotetico che risponderebbe alla query; usa l'embedding di quel documento per il retrieval
  - **Step-back prompting:** Riscrive la query a un livello di astrazione superiore per catturare concetti padre
  - **Query denoising:** Rimuove stop word e ambiguità sintattiche
- **LLM utilizzato:** Modello leggero (GPT-3.5-turbo o Llama-3-8B) per contenere i costi

#### F4 — Query Expansion
- **Fonte 1 — Vocabolario C1:** Espansione acronimi, normalizzazione termini
- **Fonte 2 — Thesaurus C3:** Aggiunta sinonimi e termini correlati (RT)
- **Fonte 3 — Tassonomia C2:** Aggiunta di narrower terms per domande specifiche
- **Strategia:** Espansione soft (boost, non filtro) — i termini espansi aumentano il recall senza ridurre la precisione
- **Output:** Query vettore principale + lista di query string espanse per BM25

#### F5 — Routing Retrieval con Cache Semantica
- **Routing logic:** Il router invia la query a uno o più retriever in parallelo basandosi su:
  - Presenza di filtri metadata espliciti → G3 attivo
  - Query di tipo "cerca documento" → E3 (BM25) prioritario
  - Query semantica/concettuale → E2 (vector) prioritario
  - Query su struttura gerarchica (es. "in quale sezione...") → E5 (tree) attivo
- **Cache semantica** (CacheRAG: arXiv 2604.26176):
  - Ogni piano di retrieval eseguito viene serializzato e indicizzato per embedding della query
  - Per query nuove: cosine similarity con cache → se > 0.92, riutilizza piano cached (F5B)
  - TTL cache: 24h di default (configurable); invalidazione su aggiornamento indici

#### F5B — Cache Piano di Retrieval
- **Funzione:** Serve direttamente i risultati del piano cached senza rieseguire la pipeline di retrieval
- **Risparmio stimato:** ~60% della latenza media su query frequenti (es. FAQ aziendali)
- **Logging:** Ogni cache hit è registrato in I3 per monitoraggio hit rate

---

## 11. Area 6B — Controller Iterativo

### 11.1 Descrizione

Il Controller Iterativo implementa la logica di stop/continua per il retrieval multi-step. Valuta la qualità dell'evidenza recuperata e decide se è sufficiente per generare una risposta o se serve ulteriore retrieval.

### 11.2 Componenti

#### F6A — S2G Quality Evaluator
- **Base:** S2G-RAG (arXiv 2604.23783, ACL 2026) — "Sufficient-to-Generate"
- **Funzione:** Valuta se l'insieme corrente di chunk recuperati è sufficiente per rispondere alla query
- **Valutazione:**
  - **Evidence coverage:** Quante sotto-domande della query originale sono coperte dall'evidenza?
  - **Evidence quality:** I chunk sono rilevanti, aggiornati e non contraddittori?
  - **Gap identification:** Quali aspetti della query rimangono senza evidenza?
- **Output:** `{sufficient: bool, coverage_score: float, gap_description: str}`

#### F6B — Decision Gate
- **Nodo di decisione con tre rami:**
  1. **Sufficiente** → procedi alla compressione contesto (G7A)
  2. **Gap identificato** → decomposizione in sub-query (F6E)
  3. **Score basso** → fallback a web search (F6C)

#### F6C — Fallback Web Search
- **Trigger:** Score di evidenza basso E il corpus PDF non contiene informazioni sufficienti
- **Meccanismo:** Query a motore di ricerca web (es. Bing Search API) o RAG su indice web esterno
- **Sicurezza:** I risultati web sono trattati come evidenza di bassa fiducia (confidence_score = 0.3)
- **Annotazione:** Le risposte basate su web search sono marcate con warning "fonte esterna"

#### F6D — Stop Policy RL
- **Base:** AutoSearch (arXiv 2604.17337) — policy di stop addestrata con reinforcement learning
- **Obiettivo:** Bilanciare qualità della risposta vs. costo del retrieval (numero di step, token consumati)
- **Input:** `{coverage_score, token_spent, budget_remaining, iteration_count}`
- **Output:** `{action: stop|continue, reason: str}`
- **Beneficio:** -40% passi medi di retrieval rispetto a policy naive (continua finché budget > 0)
- **Integrazione I7:** Riceve segnale di stop obbligatorio se il token budget è esaurito

#### F6E — Sub-query Decomposer
- **Base:** Self-RAG (Asai et al. arXiv 2310.11511)
- **Funzione:** Decompone la query originale o il gap identificato in sub-query atomiche, ciascuna rispondibile con un singolo retrieval step
- **Esempio:**
  - Query: "Quali sono le differenze tra GDPR e NIS2 riguardo alla notifica delle violazioni?"
  - Sub-query: ["Termine notifica violazioni GDPR", "Termine notifica violazioni NIS2", "Differenze GDPR NIS2"]
- **Output:** Lista ordinata di sub-query con priorità

#### F6F — Contradiction Detector
- **Base:** Korn (arXiv 2605.05632)
- **Funzione:** Identifica conflitti tra chunk provenienti da documenti diversi nell'evidenza corrente
- **Classificazione contraddizioni:**
  - **Tipo A — Versione:** Stesso documento, versione diversa (es. norma aggiornata vs. vecchia)
  - **Tipo B — Fonte:** Documenti diversi con affermazioni incompatibili
  - **Tipo C — Temporale:** Affermazione valida in un periodo ma non in un altro
- **Output:** Lista di conflitti rilevati; usato in H1 per annotare il contesto e in H3 per il grounding check

---

## 12. Area 7 — Retrieval e Ranking

### 12.1 Descrizione

Il layer di retrieval esegue la ricerca multi-sorgente e consolida i risultati in una lista ranked pronta per la compressione del contesto.

### 12.2 Componenti

#### G1 — Vector Retrieval (4-segnale)
- **Retrieval base:** ANN (Approximate Nearest Neighbor) su E2 (Qdrant) con HNSW index
- **Top-K iniziale:** 50 candidati (poi ridotti a 10–20 dal reranker G6)
- **Score composito 4-segnale:**
  ```
  score = α·semantic_sim + β·temporal_score + γ·confidence_score + δ·graph_centrality
  ```
  - `semantic_sim`: cosine similarity query-chunk (0–1)
  - `temporal_score`: recency bonus per documenti recenti (funzione logistica)
  - `confidence_score`: qualità embedding (OCR quality, completezza ontologica)
  - `graph_centrality`: PageRank del nodo chunk in E5 (nodi centrali nel KG pesati di più)
  - Pesi `α,β,γ,δ`: ottimizzati da I8 (AutoRAGTuner)

#### G2 — Keyword Retrieval BM25
- **Esecuzione:** Query espansa (output F4) su OpenSearch/Elasticsearch (E3)
- **Configurazione:**
  - Multi-field: `text_content^2, section_title^3, topic_tags^1.5`
  - Synonym filter applicato al query time tramite Thesaurus C3
- **Top-K:** 30 candidati

#### G3 — Metadata Filtering
- **Funzione:** Filtro hard su metadati da E4 (PostgreSQL)
- **Filtri supportati:** `domain`, `language`, `author`, `date_range`, `doc_type`, `acl`
- **Combinazione con G1/G2:** I filtri metadata sono applicati come pre-filter su E2 (Qdrant payload filter) e come WHERE clause in E4

#### G4 — Tree Retrieval (Ψ-RAG)
- **Funzione:** Traversal dell'indice gerarchico E5 a granularità appropriata
- **Selezione granularità:** La query classifica automaticamente il livello di dettaglio richiesto:
  - "Riassumi il capitolo 3" → livello Sezione
  - "Qual è il valore specifico di..." → livello Token/Frase
- **Cross-document:** Sfrutta i link cross-document di E5 per aggregare evidenza da più PDF correlati

#### G5 — Denoising Semantico
- **Base:** arXiv 2605.00505 (SIGIR 2026) — "denoise first, then rerank"
- **Fase 1 — Denoising:** Rimuove chunk chiaramente irrilevanti (cosine similarity < soglia bassa, es. 0.3) prima del reranking costoso
- **Fase 2 — Merge lista:** Unisce i candidati da G1, G2, G3, G4 con deduplicazione (stesso `chunk_id`)
- **Beneficio:** Riduce il costo del reranker G6 rimuovendo il rumore prima

#### G6 — CAR Confidence-Aware Reranker
- **Base combinata:**
  - **Verbal-R3** (arXiv 2605.01399): annotazioni verbali di confidenza ("I am certain that...", "This likely applies to...")
  - **CAR** (arXiv 2605.04495): Confidence-Aware Reranking — ponderate la rilevanza per la confidenza dell'embedding
- **Algoritmo:**
  1. Cross-encoder reranker (es. `ms-marco-MiniLM-L-12-v2`) calcola `relevance_score`
  2. Score finale: `final_score = relevance_score × confidence_score`
  3. RRF (Reciprocal Rank Fusion) pesato sulla confidenza per fusione multi-sorgente
- **Output:** Lista ordinata di top-K chunk (K = 10–20, configurabile) con `relevance_score`, `confidence_score`, `source_annotation`

---

## 13. Area 7B — Compressione del Contesto

### 13.1 Descrizione

Prima di inviare il contesto al generatore LLM, questa area comprime il contesto recuperato per massimizzare la rilevanza task-specific e prevenire la confabulazione da evidenza parziale.

### 13.2 Componenti

#### G7A — Compressore Query-Conditioned
- **Base:** arXiv 2602.15856 (WWW 2026) — compressione del contesto guidata dalla query
- **Funzione:**
  - Data la query e la lista di chunk rankati, il compressore identifica gli **span minimali** che contengono l'informazione necessaria
  - Scarta frasi e paragrafi non rilevanti alla specifica query (anche se il chunk era globalmente rilevante)
  - Preserva la struttura logica e il riferimento alla fonte (pagina, sezione)
- **Tecnica:** Estrattore span con modello BERT fine-tuned su QA extraction; fallback a LLM-based extraction
- **Riduzione tipica:** 40–60% dei token in input al generatore, senza perdita di recall

#### G7B — Confabulation Guard
- **Base:** arXiv 2604.25931 — "evidenza parziale amplifica allucinazioni"
- **Funzione:** Verifica che la catena di evidenza sia completa e non contenga gap logici prima di passare al generatore
- **Meccanismo:**
  1. Costruisce il "grafo di evidenza" per la query: quali claim devono essere supportati e da quali chunk
  2. Identifica claim obbligatori senza evidenza (gap)
  3. Se gap critici → ritorna al controller F6 per recupero aggiuntivo
  4. Se gap non critici → annota il contesto con "evidenza mancante su: ..." per il generatore
- **Output:** Contesto annotato pronto per H1; flag `has_evidence_gap: bool`

---

## 14. Area 8 — Generazione e Validazione

### 14.1 Descrizione

Il layer di generazione trasforma il contesto compresso in una risposta finale in linguaggio naturale, verificata, citata e conforme al dominio.

### 14.2 Componenti

#### H1 — Context Builder
- **Funzione:** Assembla il prompt finale per il generatore LLM con:
  - Chunk compressi (output G7A) ordinati per rilevanza
  - Community summaries del KG (C5) per contesto macro
  - Annotazioni verbali di confidenza da G6
  - Flag di contraddizioni rilevate da F6F
  - Istruzioni di citazione strutturate
- **Template prompt (struttura):**
  ```
  [SYSTEM]
  Sei un assistente esperto in {domain}. Rispondi basandoti ESCLUSIVAMENTE
  sul contesto fornito. Cita la fonte per ogni affermazione (documento, pagina).
  Se l'evidenza è insufficiente, dichiara esplicitamente l'incertezza.

  [CONTEXT]
  {compressed_chunks_with_citations}

  [CONTRADICTIONS]
  {detected_contradictions_if_any}

  [QUESTION]
  {original_query}

  [ANSWER FORMAT]
  Risposta: ...
  Fonti: [{doc_title}, p.{page}, chunk {chunk_id}]
  Confidence: alta|media|bassa
  ```

#### H2 — LLM Generator
- **Modelli supportati (configurabili):**
  - `gpt-4o` (OpenAI) — default per produzione
  - `claude-3-5-sonnet` (Anthropic) — alternativa per uso enterprise EU
  - `llama-3.1-70b` (Meta, self-hosted) — opzione on-premise
  - `mistral-large-2` — opzione cost-effective
- **Parametri generazione:**
  - `temperature`: 0.1–0.3 (bassa per risposta fattuale)
  - `max_tokens`: configurabile via I7 token budget
  - `top_p`: 0.9
- **Streaming:** Supporto SSE (Server-Sent Events) per risposta progressiva all'utente

#### H3 — Grounding Check
- **Base:** Self-RAG (Asai et al. arXiv 2310.11511)
- **Funzione:** Verifica che ogni claim nella risposta generata sia tracciabile a un chunk nel contesto
- **Meccanismo:**
  1. Parse della risposta in claim atomici
  2. Per ogni claim: verifica presenza di evidenza supportante nel contesto (NLI — Natural Language Inference)
  3. Claim senza supporto → flaggati come "not grounded"
  4. Se claim not-grounded superano soglia → feedback a F3 per nuovo ciclo retrieval
- **Output:** Risposta annotata con grounding status per claim

#### H4 — Citation Validation + XGRAG Explanation
- **Citation validation:** Per ogni affermazione, verifica che il riferimento (documento, pagina, chunk) sia realmente presente nell'Object Storage E1 e corrisponda al contenuto citato
- **XGRAG explanation** (arXiv 2604.24623): Genera una spiegazione esplicita del *perché* ogni chunk è stato selezionato per quella query — "questo chunk è stato incluso perché menziona la scadenza del 25/05/2024 che risponde alla domanda sulla deadline GDPR"
- **Output:** Struttura citazioni verificate con explanation opzionale

#### H5 — Compliance Check
- **Trigger:** Attivato solo se `domain` ∈ {Legale, Finanziario, Medico, Compliance}
- **Base:** ComplianceNLP (arXiv 2604.23585)
- **Funzione:**
  - Verifica che la risposta non contenga gap rispetto agli obblighi normativi del dominio
  - Identifica se la domanda implica un'azione regolamentata (es. "posso...") e aggiunge nota disclaimer
  - Verifica che le norme citate siano ancora in vigore (confronto con temporal_validity)
- **Output:** Risposta arricchita di note compliance; `compliance_warning: bool`

#### H6 — Risposta Finale
- **Struttura risposta:**
  ```json
  {
    "answer": "...",
    "sources": [
      {
        "doc_title": "...",
        "doc_id": "uuid",
        "page": 12,
        "chunk_id": "uuid",
        "excerpt": "...",
        "confidence": 0.91,
        "temporal_validity": "2025-01-01/2027-12-31"
      }
    ],
    "overall_confidence": "alta",
    "retrieval_explanation": "...",
    "has_evidence_gap": false,
    "compliance_warning": false,
    "contradictions_detected": [],
    "token_cost": {
      "retrieval": 1240,
      "generation": 876,
      "total": 2116
    }
  }
  ```

---

## 15. Area 9 — Governance e Feedback

### 15.1 Descrizione

Il layer di governance garantisce sicurezza, conformità, osservabilità e miglioramento continuo del sistema.

### 15.2 Componenti

#### I1 — Access Control (RBAC + PRAG)
- **RBAC:** Ruoli configurabili (Admin, Editor, Reader, Auditor) con permessi su collezioni, domini, documenti specifici
- **PRAG** (arXiv 2604.26525): Privacy-aware RAG — il retrieval filtra automaticamente i chunk non accessibili all'utente corrente in base all'ACL del documento
- **Implementazione:** JWT token con claims di gruppo; ogni query porta il token; Qdrant filtra su `payload.acl`
- **Audit:** Ogni accesso a documento sensibile è loggato in E6

#### I2 — Data Lineage
- **Funzione:** Per ogni documento, mantiene la storia completa: chi l'ha caricato, quando, da dove, quante volte è stato usato in retrieval, quali query l'hanno interrogato
- **Implementazione:** Query a E6 (Audit Log) + join con E4 (Metadata Store)
- **API:** Endpoint REST `/lineage/{doc_id}` che restituisce grafo di provenienza

#### I3 — Monitoring
- **Metriche raccolte:**
  - `retrieval_score_avg`: score medio di retrieval per finestra temporale
  - `staleness_ratio`: % di chunk con `decay_factor` < soglia
  - `confabulation_risk`: % di risposte con `has_evidence_gap = true`
  - `token_cost_p95`: costo token al p95 per query
  - `cache_hit_rate`: % di query servite da cache F5B
  - `contradiction_rate`: % di retrieval set con contraddizioni rilevate
- **Stack:** Prometheus + Grafana; alert via PagerDuty/Slack per anomalie
- **Dashboard:** Latenza end-to-end, distribuzione confidence score, top query per costo

#### I4 — Evaluation Metrics
- **Framework primario:** RAGAS (Retrieval-Augmented Generation Assessment)
  - `faithfulness`: % claim groundati nel contesto
  - `answer_relevancy`: pertinenza risposta alla query
  - `context_precision`: % chunk rilevanti nel contesto recuperato
  - `context_recall`: copertura del contesto rispetto all'evidenza di riferimento
- **Benchmark:** EnterpriseRAG-Bench (arXiv 2605.05253) per valutazione su dominio enterprise
- **Cadenza:** Evaluation batch giornaliera su campione 5% delle query; evaluation completa settimanale

#### I5 — Human Feedback Loop
- **Meccanismo:**
  - Utente esprime feedback (thumbs up/down + commento opzionale) sull'interfaccia
  - Feedback negativo → analisi automatica del chunk sorgente → proposta di patch al KG (C5)
  - Feedback positivo → rinforzo dell'embedding (SmartVector reconsolidation in E2)
- **Supervisione:** Le patch al KG generate automaticamente richiedono approvazione di un Admin prima di essere applicate in produzione

#### I6 — Security Monitor
- **CleanBase** (arXiv 2605.00460): Rilevamento anomalie pre-indice — ogni nuovo PDF è confrontato con la distribuzione degli embedding esistenti; outlier statistici sono messi in quarantena per revisione umana (previene poisoning dell'indice)
- **Needle-in-RAG** (arXiv 2605.01782): Span forensics — analisi dei chunk recuperati per identificare injection di contenuto malevolo nelle risposte
- **KB Poisoning Detection** (arXiv 2605.05632): Verifica integrità del Knowledge Graph tramite analisi di consistenza logica (rilevamento triple contradditorie introdotte da attacchi di poisoning)
- **Alert:** Qualsiasi anomalia rilevata genera alert in I3 e blocca il chunk/documento in quarantena

#### I7 — Cost / Token Budget Controller
- **Ruolo:** Componente trasversale che monitora e limita il consumo di token per ogni query
- **Budget configurabile:**
  - `max_tokens_per_query`: default 4000 (prompt + retrieval + generazione)
  - `max_retrieval_steps`: default 3 iterazioni del controller F6
  - `warn_at_pct`: alert quando il budget è consumato al 80%
- **Flusso:**
  1. Query entra → I7 apre un "budget account" per quella query
  2. Ogni componente report il consumo (retrieval: ~500 token, generazione: ~1000 token)
  3. Se budget esaurito → segnale stop obbligatorio a F6D
  4. Costo totale incluso in H6 (risposta finale)
- **Reporting:** Spend aggregato per utente, dominio, giorno — inviato a I3 e I8

#### I8 — AutoRAGTuner
- **Base:** arXiv 2605.02967 (EuroSys 2026) — ottimizzazione black-box Bayesiana dei parametri RAG
- **Parametri ottimizzati:**
  - `chunk_size` (256–1024 token)
  - `chunk_overlap` (64–256 token)
  - `top_k_retrieval` (5–50)
  - `reranker_model` (cross-encoder variants)
  - `bm25_k1`, `bm25_b`
  - `prompt_template` (variant A/B/C)
- **Metodo:** Ottimizzazione Bayesiana (Gaussian Process) minimizzando `(1 - RAGAS_score) + λ·token_cost`
- **Cadenza:** Ciclo di ottimizzazione ogni 7 giorni su dati reali anonimizzati
- **Output:** Configurazione aggiornata deployata via feature flag

---

## 16. Flussi Dati Principali

### 16.1 Flusso Ingestione — Offline e Online

```
MODALITÀ OFFLINE (A)             MODALITÀ ONLINE (B)
─────────────────────            ─────────────────────
A1 → BA1 (Watcher)               Utente → BB1 (API Upload)
A2 → BA2 (Scheduler)             A2 → BB2 (Webhook Push)
A3 → BA2 (Scheduler)
BA3 (Bulk Import) ─────────────────────────────┐
     │                                          │
     ▼                                          ▼
 BA4 (Coda low-priority)          BB3 (Coda high-priority)
           \                           /
            ──────────────────────────
                        │
           (SLA: nessuno / < 60s)
                        │
1. Sorgente PDF (A1/A2/A3)
   │
2. Connettore (B1) — verifica ACL, sha256, dedup
   │
3. PDF Loader (B2) → Parser Layout (B3)
   │
4. [se scansionato] OCR (B4)
   │
5. Pulizia Testo (B5) → Estrazione Tabelle (B6)
   │
6. Source Provenance (B7) + Versioning (B8)
   │
7. Entity/Relation Extraction (D1, D2) → Auto-Ontologia (C6)
   │
8. Classificazione Dominio (D3) + Metadata Enrichment (D4)
   │
9. SAGE Semantic Chunking (D5)
   │
10. Embedding Generation (D6)
    │
    ├─→ Vector DB E2 (embedding + payload)
    ├─→ Keyword Index E3 (BM25)
    ├─→ Metadata Store E4 (PostgreSQL)
    ├─→ Hierarchical Tree Index E5 (Ψ-RAG)
    └─→ Object Storage E1 (raw PDF + artefatti)
        + Audit Log E6 (Merkle chain entry)
```

**Tempo stimato per PDF standard (10 pagine, nativo digitale):** 15–45 secondi per documento

### 16.2 Flusso Online — Query

```
1. Query Utente (F1) — testo + session context
   │
2. Intent + Complexity Gate (F2) — retrieval needed?
   │
   ├─[no retrieval]─→ G7A → H1 → H2 → H6
   │
3. Query Rewriting (F3) + Query Expansion (F4)
   │
4. Routing + Cache Check (F5)
   │
   ├─[cache hit]─→ F5B → G7A → H1 → H2 → H6
   │
5. Retrieval Parallelo:
   G1 (Vector) + G2 (BM25) + G3 (Metadata) + G4 (Tree)
   │
6. Denoising (G5) → Reranking CAR (G6)
   │
7. S2G Quality Evaluator (F6A) → Contradiction Detector (F6F)
   │
   ├─[insufficient]─→ F6E Sub-query → F6D Stop Policy → [loop a 5]
   ├─[low score]────→ F6C Web Fallback → G7A
   │
8. Compressione Contesto (G7A) → Confabulation Guard (G7B)
   │
9. Context Builder (H1) → LLM Generator (H2)
   │
10. Grounding Check (H3) → Citation Validation (H4) → Compliance Check (H5)
    │
11. Risposta Finale (H6) → Feedback Loop (I5)
```

**Latenza stimata p50:** 1.5–2 secondi | **p95:** 3–4 secondi (senza cache)  
**Con cache hit:** 0.3–0.5 secondi

---

## 17. Stack Tecnologico

### 17.1 Linguaggi e Framework

| Layer | Tecnologia | Versione | Note |
|-------|-----------|---------|------|
| Backend API | Python | 3.12 | FastAPI per API REST |
| Pipeline ingestione | Python | 3.12 | Apache Airflow 2.9 per orchestrazione |
| Query pipeline | Python | 3.12 | Async con asyncio + FastAPI |
| Task queue batch | Celery + Redis | 5.3 / 7.x | Coda `ingest_low` — ingestione offline/schedulata |
| Task queue online | Celery + Redis | 5.3 / 7.x | Coda `ingest_high` — ingestione real-time, SLA < 60s |
| Configuration | Pydantic Settings | 2.x | Validazione config, .env support |

### 17.2 Librerie Core

| Funzione | Libreria | Versione |
|---------|---------|---------|
| PDF parsing | PyMuPDF (fitz) | 1.24 |
| PDF tabelle | camelot-py, pdfplumber | 0.11 / 0.11 |
| OCR | pytesseract (Tesseract 5) | 0.3.x |
| NER | spaCy | 3.8 (modello it_core_news_lg) |
| Embeddings | openai, sentence-transformers | latest |
| Vector DB | qdrant-client | 1.10 |
| Search | elasticsearch-py | 8.x |
| Graph DB | neo4j-python-driver | 5.x |
| ORM | SQLAlchemy | 2.x |
| RDF/SPARQL | rdflib | 7.x |
| SHACL validation | pyshacl | 0.26 |
| Reranker | sentence-transformers (cross-encoder) | latest |
| LLM gateway | litellm | latest (astrazione multi-LLM) |
| Monitoring | prometheus-client, opentelemetry | latest |
| Evaluation | ragas | 0.2.x |

### 17.3 Infrastruttura

| Componente | Tecnologia | Sizing indicativo |
|-----------|-----------|-----------------|
| Object Storage | MinIO / AWS S3 | 1TB iniziale, scalabile |
| Vector DB | Qdrant (3 nodi) | 16 GB RAM, 4 vCPU per nodo |
| Search | OpenSearch (3 nodi) | 8 GB RAM, 4 vCPU per nodo |
| Metadata DB | PostgreSQL 15 | 8 GB RAM, 4 vCPU, SSD |
| Graph DB | Neo4j Community / Enterprise | 16 GB RAM, 8 vCPU |
| Cache | Redis 7 | 4 GB RAM |
| API Gateway | FastAPI + Uvicorn | 2 repliche, 4 vCPU |
| Task Queue Batch | Celery `ingest_low` | 2–4 worker, 2 vCPU (HPA su queue depth) |
| Task Queue Online | Celery `ingest_high` | 2–8 worker, 2 vCPU (HPA aggressivo, scale-up 30s) |
| Orchestrazione | Apache Airflow | 1 scheduler + 4 worker |
| Container | Docker + Kubernetes (K3s/EKS) | Namespace isolato per prod |
| Monitoring | Prometheus + Grafana | 1 nodo dedicato |

---

## 18. Interfacce API

### 18.1 API REST — Endpoint Principali

#### `POST /api/v1/query`
Interroga il sistema con una domanda in linguaggio naturale.

**Request:**
```json
{
  "query": "Qual è il termine per la notifica di una violazione dei dati personali secondo il GDPR?",
  "domain_hint": "Legale",
  "filters": {
    "date_from": "2024-01-01",
    "language": "it"
  },
  "session_id": "uuid",
  "max_tokens": 2000
}
```

**Response:**
```json
{
  "answer": "Il GDPR (art. 33) prevede l'obbligo di notifica all'autorità...",
  "sources": [...],
  "overall_confidence": "alta",
  "retrieval_explanation": "...",
  "token_cost": { "total": 1876 },
  "query_id": "uuid"
}
```

#### `POST /api/v1/ingest`
Avvia l'ingestione online (real-time) di un PDF tramite upload diretto. Accodata su `ingest_high`.

**Request:** `multipart/form-data`
- `file`: PDF binario (max 50 MB)
- `metadata`: JSON opzionale `{title, author, domain, acl}`
- `callback_url`: URL opzionale per webhook callback su completamento

**Response:**
```json
{
  "job_id": "uuid",
  "status": "queued",
  "status_url": "/api/v1/ingest/uuid/status",
  "estimated_duration_seconds": 30,
  "queue": "ingest_high"
}
```

#### `POST /api/v1/ingest/batch`
Avvia l'ingestione offline (batch) di più PDF da URL o path. Accodata su `ingest_low`.

**Request:**
```json
{
  "sources": [
    {"type": "url", "uri": "https://..."},
    {"type": "path", "uri": "s3://bucket/doc.pdf"}
  ],
  "metadata_defaults": {"domain": "Legale", "language": "it"}
}
```

**Response:**
```json
{
  "batch_id": "uuid",
  "job_count": 42,
  "queue": "ingest_low",
  "airflow_dag_run_id": "..."
}
```

#### `GET /api/v1/ingest/{job_id}/status`
Verifica lo stato di un job di ingestione (online o batch).

**Response:**
```json
{
  "job_id": "uuid",
  "status": "queued|processing|completed|failed",
  "progress_pct": 65,
  "current_step": "D5_chunking",
  "doc_id": "uuid",
  "duration_seconds": 23,
  "error": null
}
```

#### `POST /api/v1/webhooks/register`
Registra un webhook per ricevere eventi push da sistemi enterprise (SharePoint, Confluence).

**Request:**
```json
{
  "source": "sharepoint|confluence",
  "events": ["document.created", "document.updated"],
  "callback_url": "https://my-system/ingest-callback",
  "secret": "hmac-secret-per-firma"
}
```

**Response:** `{webhook_id, status: "active"}`

#### `GET /api/v1/documents`
Lista documenti indicizzati con filtri (domain, language, date, author).

#### `GET /api/v1/documents/{doc_id}/lineage`
Restituisce il grafo di provenienza di un documento.

#### `POST /api/v1/feedback`
Registra il feedback utente su una risposta.

```json
{
  "query_id": "uuid",
  "rating": "positive|negative",
  "comment": "..."
}
```

#### `GET /api/v1/health`
Health check con status di tutti i componenti dipendenti.

### 18.2 Autenticazione API

- **Meccanismo:** Bearer token JWT (HS256) con claims `sub` (user_id), `groups` (RBAC groups), `exp`
- **Refresh:** Token con TTL 1h; refresh token con TTL 24h
- **API key per service-to-service:** Chiave statica in header `X-API-Key` per pipeline ingestione

---

## 19. Schema Dati e Modelli

### 19.1 Modello Chunk (core entity)

```python
@dataclass
class Chunk:
    chunk_id: UUID
    doc_id: UUID
    doc_version: int
    text: str
    page_start: int
    page_end: int
    section_title: str | None
    domain: str
    language: str
    token_count: int
    saliency_score: float        # SAGE score
    confidence_score: float      # SmartVector confidence
    decay_factor: float          # Ebbinghaus decay (0–1)
    embedding: list[float]       # dimensione 3072 o 1024
    embedding_model: str
    embedding_timestamp: datetime
    acl: list[str]               # ["user:alice", "group:legal"]
    created_at: datetime
    updated_at: datetime
```

### 19.2 Modello Document

```python
@dataclass
class Document:
    doc_id: UUID
    sha256_raw: str
    sha256_text: str
    source_uri: str
    source_type: Literal["local", "enterprise", "web"]
    ingestion_mode: Literal["offline_batch", "online_realtime"]
    ingestion_priority: Literal["low", "high"]
    title: str
    author: list[str]
    creation_date: date | None
    language: str
    domain: str
    doc_type: str
    page_count: int
    version: int
    acl: list[str]
    ingested_at: datetime
    chunks: list[Chunk]          # relazione 1:N
```

### 19.3 Modello Risposta (QueryResponse)

```python
@dataclass
class QueryResponse:
    query_id: UUID
    query: str
    answer: str
    sources: list[SourceCitation]
    overall_confidence: Literal["alta", "media", "bassa"]
    has_evidence_gap: bool
    compliance_warning: bool
    contradictions_detected: list[ContradictionInfo]
    retrieval_explanation: str
    token_cost: TokenCost
    latency_ms: int
    created_at: datetime
```

---

## 20. Sicurezza e Conformità

### 20.1 Controllo Accessi

| Livello | Meccanismo | Note |
|---------|-----------|------|
| API | JWT Bearer Token | Scadenza 1h, refresh 24h |
| Documento | RBAC + ACL su chunk | Filtro Qdrant payload |
| Admin | MFA obbligatorio | TOTP via authenticator app |
| Audit | Merkle hash chain E6 | Immutabile, verificabile |

### 20.2 Protezione Dati

- **At-rest:** Encryption AES-256 per Object Storage (MinIO SSE / S3 SSE-KMS)
- **In-transit:** TLS 1.3 su tutti i canali interni e API pubbliche
- **PII Detection:** Prima dell'embedding, le entità PII (nomi, CF, IBAN) in documenti pubblici sono pseudonimizzate se richiesto dal dominio
- **GDPR Art. 17 (right to erasure):** Procedura di cancellazione implementata: SHA256 → ricerca in E4 → cancellazione soft in E2/E3 → audit entry in E6

### 20.3 Sicurezza Pipeline RAG

| Minaccia | Contromisura | Componente |
|---------|-------------|-----------|
| Index poisoning | CleanBase anomaly detection | I6 |
| Prompt injection via PDF | Needle-in-RAG span forensics | I6 |
| KB pollution | KB Poisoning Detection (Korn) | I6, F6F |
| Unauthorized data access | PRAG end-to-end privacy | I1 |
| Data exfiltration via query | Rate limiting, token budget | I7, API Gateway |

---

## 21. Performance e Scalabilità

### 21.1 Target Performance

| Metrica | Target | Misurazione |
|---------|--------|------------|
| Latenza query p50 | < 1.5s | Prometheus histogram |
| Latenza query p95 | < 3.0s | Prometheus histogram |
| Throughput query | > 50 RPS | Load test k6 |
| Ingestione PDF | > 100 pag/min | Pipeline metrics |
| Vector search latency | < 50ms | Qdrant metrics |
| Cache hit rate | > 40% su corpus stabile | F5B counter |

### 21.2 Strategie di Scalabilità

- **Vector DB:** Qdrant sharding orizzontale per corpus > 10M chunk; quantizzazione scalar per ridurre footprint memoria del 4x
- **API Layer:** Stateless FastAPI replicas behind load balancer; auto-scaling Kubernetes HPA su CPU/latenza
- **Ingestione:** Worker Celery scalabili orizzontalmente; priorità queue (urgente vs. batch notturno)
- **LLM:** LiteLLM come gateway con rate limiting, retry e fallback automatico tra provider

### 21.3 Ottimizzazioni Chiave

- **Batch embedding:** 256 chunk per request GPU → amortizza overhead API
- **Quantizzazione vettori:** Int8 quantization in Qdrant → -75% memory, -5% recall
- **Query cache:** CacheRAG riduce latenza a ~300ms per query frequenti
- **Stop Policy RL:** -40% retrieval steps → -40% token retrieval cost

---

## 22. Deployment e Infrastruttura

### 22.1 Architettura Container

```yaml
# docker-compose (sviluppo locale)
services:
  api:           # FastAPI query + ingest endpoint
  worker:        # Celery ingestione PDF
  scheduler:     # Airflow pipeline scheduler
  qdrant:        # Vector DB
  opensearch:    # Keyword index
  postgres:      # Metadata store
  neo4j:         # Knowledge graph + tree index
  redis:         # Cache + Celery broker
  minio:         # Object storage
  prometheus:    # Metrics
  grafana:       # Dashboard
```

### 22.2 Kubernetes (Produzione)

```
Namespace: semantic-rag-prod
├── Deployment: api (2–10 repliche, HPA)
├── Deployment: celery-worker (2–8 repliche, HPA su queue depth)
├── StatefulSet: qdrant (3 nodi, PVC 500GB each)
├── StatefulSet: opensearch (3 nodi, PVC 200GB each)
├── StatefulSet: postgres (1 primary + 1 replica, PVC 100GB)
├── StatefulSet: neo4j (1 nodo, PVC 200GB)
├── Deployment: redis (1 nodo + sentinel)
├── PersistentVolumeClaim: minio (1TB)
└── CronJob: autorag-tuner (weekly)
```

### 22.3 CI/CD Pipeline

```
Git Push → GitHub Actions
├── Lint (ruff, mypy)
├── Unit Tests (pytest)
├── Integration Tests (docker-compose up + test suite)
├── Build Docker Image
├── Push to Registry
└── Deploy to K8s (kubectl apply + helm upgrade)
    ├── [staging] auto-deploy
    └── [prod] manual approval gate
```

### 22.4 Configurazione per Ambiente

| Parametro | Dev | Staging | Prod |
|-----------|-----|---------|------|
| LLM Provider | LM Studio locale | GPT-3.5-turbo | GPT-4o |
| Vector DB | ChromaDB in-memory | Qdrant single node | Qdrant 3 nodi |
| Token budget/query | 8000 | 4000 | 4000 |
| Cache TTL | 5 min | 1h | 24h |
| Monitoring | Log console | Prometheus | Prometheus + Alerting |

---

## 23. Metriche di Valutazione

### 23.1 Metriche di Qualità RAG

| Metrica | Descrizione | Target | Tool |
|---------|------------|--------|------|
| Faithfulness | % claim groundati nel contesto | > 0.90 | RAGAS |
| Answer Relevancy | Pertinenza risposta alla query | > 0.85 | RAGAS |
| Context Precision | % chunk rilevanti nel set recuperato | > 0.80 | RAGAS |
| Context Recall | Copertura evidenza necessaria | > 0.80 | RAGAS |
| Precision@5 | Top-5 chunk rilevanti | > 0.85 | Custom eval |
| Hallucination Rate | % risposte con claim non groundati | < 0.05 | Grounding check |

### 23.2 Metriche di Sistema

| Metrica | Target | Frequenza |
|---------|--------|-----------|
| Latenza p95 query | < 3s | Real-time |
| Token cost p95 | < 4000 token | Real-time |
| Ingestione errori | < 1% | Daily |
| Cache hit rate | > 40% | Daily |
| Index staleness | < 5% chunk stale | Daily |

### 23.3 Benchmark di Riferimento

- **EnterpriseRAG-Bench** (arXiv 2605.05253): benchmark specifico per dominio enterprise su task di Q&A, riepilogo e compliance
- **Test set interno:** 500 domande annotate con risposta attesa e fonti verificate — campione rappresentativo del corpus

---

## 24. Piano di Sviluppo a Fasi

### Fase 1 — Fondamenta (Settimane 1–6)

**Obiettivo:** Pipeline minima funzionante end-to-end

| Componente | Scope | Note |
|-----------|-------|------|
| B1–B8 | Pipeline ingestione completa | Incluso OCR |
| D3–D6 | Chunking + embedding | Senza entity extraction |
| E1–E4 | Storage base | Senza tree index e KG |
| F1–F5 | Query pipeline senza cache | Retrieval semplice |
| G1–G3 | Vector + BM25 + metadata filter | Senza tree retrieval |
| H1–H2–H6 | Generazione base | Senza grounding check |
| API REST base | `/query`, `/ingest`, `/health` | |

**Deliverable:** Sistema funzionante su corpus di test; demo Q&A su PDF

### Fase 2 — Layer Semantico (Settimane 7–12)

| Componente | Scope |
|-----------|-------|
| C1–C6 | Vocabolario + ontologia + KG + Auto-Builder |
| D1–D2 | Entity + relation extraction |
| E5 | Hierarchical tree index |
| F4 | Query expansion via thesaurus |
| G4, G5, G6 | Tree retrieval + denoising + reranker |

**Deliverable:** Retrieval migliorato; KG visualizzabile; Precision@5 > 0.80

### Fase 3 — Qualità e Controllo (Settimane 13–18)

| Componente | Scope |
|-----------|-------|
| F2, F6A–F6F | Intent gate + controller iterativo |
| G7A, G7B | Compressione contesto + confabulation guard |
| H3–H5 | Grounding check + citation validation + compliance |
| I1–I4 | RBAC + audit + monitoring + evaluation |
| F5 cache | CacheRAG semantic cache |

**Deliverable:** Faithfulness > 0.90; audit trail completo; compliance check operativo

### Fase 4 — Ottimizzazione e Governance (Settimane 19–24)

| Componente | Scope |
|-----------|-------|
| I5–I8 | Feedback loop + security monitor + token budget + AutoRAGTuner |
| E6 | Merkle audit chain |
| I7 | Token budget controller integrato |
| Performance tuning | Qdrant quantization, cache TTL, HPA |

**Deliverable:** Sistema production-ready; AutoTuner attivo; SLA garantito

---

## 25. Dipendenze e Rischi

### 25.1 Dipendenze Esterne

| Dipendenza | Tipo | Rischio | Mitigazione |
|-----------|------|---------|------------|
| OpenAI API (embeddings + LLM) | Critica | Provider downtime, costo | Fallback su self-hosted (E5-large + Llama-3) |
| Azure Document Intelligence (OCR) | Opzionale | Costo per volume | Tesseract come primary; Azure solo su scarsa qualità OCR |
| Microsoft Graph API | Opzionale | Auth changes | Adapter pattern; versione API fissa |
| arXiv paper implementations | Research | Codice non disponibile | Re-implementare da paper se necessario |

### 25.2 Rischi Tecnici

| Rischio | Probabilità | Impatto | Mitigazione |
|---------|------------|---------|------------|
| Qualità OCR insufficiente su PDF scansionati degradati | Media | Alta | Confidence score OCR; flag manuale review |
| KG Auto-Builder introduce triple errate | Alta | Media | SHACL validation; soglia confidence; human-in-the-loop su patch KG |
| Token budget troppo basso → risposte incomplete | Media | Media | Configurazione per dominio; alert proattivi; tuning via I8 |
| Qdrant performance degrado su >10M chunk | Bassa | Alta | Sharding preventivo; quantizzazione; benchmark periodici |
| Hallucination LLM nonostante grounding check | Bassa | Alta | Multi-layer check (H3+H4); risposta con low confidence se gap |
| Corpus poisoning da sorgenti web | Bassa | Alta | CleanBase pre-index gate; quarantena automatica; revisione umana |

### 25.3 Dipendenze Interne (ordine di sviluppo)

```
B1–B8 (ingestione) 
  → D3–D6 (chunking + embedding)
    → E1–E4 (storage)
      → C6 (auto-ontologia) → C1–C5 (layer semantico)
        → D1–D2 (entity/relation extraction)
          → E5 (tree index)
            → F1–F5 (query pipeline)
              → G1–G6 (retrieval + ranking)
                → F6A–F6F (controller iterativo)
                  → G7A–G7B (compressione)
                    → H1–H6 (generazione)
                      → I1–I8 (governance)
```

---

*Fine documento — Versione 1.0 — 10 maggio 2026*

*Riferimenti paper citati disponibili nella cartella `papers/` del repository.*
