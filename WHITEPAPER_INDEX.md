# WHITEPAPER INDEX — Semantic RAG Engine

## Cover Page
- Title, subtitle, version, date, authors

## Table of Contents (auto from sections)

---

## Part I — Foundations
### 1. Executive Summary
### 2. Introduction to RAG Systems
  2.1 What is Retrieval-Augmented Generation
  2.2 Evolution from Naive RAG to Advanced RAG
  2.3 The Case for Vertical RAG on PDF Documents

## Part II — System Architecture
### 3. Architecture Overview
  3.1 Design Principles
  3.2 Macro-Architecture: Offline + Online Pipelines
  3.3 Cross-Cutting Governance Layer

### 4. Document Ingestion Pipeline
  4.1 PDF Sources and Connectors
  4.2 Offline Batch Ingestion (Airflow, Celery)
  4.3 Online Real-Time Ingestion (REST API, Webhooks)
  4.4 PDF Parsing, OCR, and Layout Extraction
  4.5 Text Cleaning and Table Extraction
  4.6 Document Versioning and Source Provenance

### 5. Semantic Layer
  5.1 Controlled Vocabulary and Thesaurus
  5.2 Lightweight Ontology (OWL 2 + SHACL)
  5.3 Knowledge Graph (Neo4j)
  5.4 Auto-Builder: Automated Ontology Construction

### 6. Document Processing
  6.1 Entity and Relation Extraction (GraphRAG)
  6.2 Domain Classification
  6.3 Metadata Enrichment
  6.4 SAGE Semantic Chunking
  6.5 Embedding Generation (QuOTE + SmartVector)

### 7. Storage and Indexing
  7.1 Object Storage (MinIO/S3)
  7.2 Vector Database (Qdrant)
  7.3 BM25 Keyword Index (OpenSearch)
  7.4 Metadata Store (PostgreSQL)
  7.5 Hierarchical Tree Index (Ψ-RAG)
  7.6 Merkle Audit Log

## Part III — Query Pipeline
### 8. Online Query Pipeline
  8.1 Intent Gate and Complexity Classification (SURE-RAG)
  8.2 Query Rewriting (HyDE + Step-back)
  8.3 Query Expansion (Thesaurus, Taxonomy)
  8.4 Retrieval Routing and Semantic Cache (CacheRAG)

### 9. Iterative Controller
  9.1 S2G Quality Evaluator (Sufficiency-to-Generate)
  9.2 Decision Gate and Stop Policy (AutoSearch RL)
  9.3 Sub-query Decomposer (Self-RAG)
  9.4 Contradiction Detector (Korn)

### 10. Retrieval and Ranking
  10.1 Four-Signal Vector Retrieval
  10.2 BM25 Hybrid Search
  10.3 Metadata Filtering
  10.4 Tree Retrieval (Ψ-RAG)
  10.5 Semantic Denoising
  10.6 Confidence-Aware Reranking (CAR + Verbal-R3)

### 11. Context Compression and Generation
  11.1 Query-Conditioned Context Compression
  11.2 Confabulation Guard
  11.3 LLM Generation (GPT-4o, Claude, Llama)
  11.4 Grounding Check (Self-RAG)
  11.5 Citation Validation and XGRAG Explanation
  11.6 Compliance Check

## Part IV — Governance and Security
### 12. Governance Framework
  12.1 RBAC and Privacy-Aware RAG (PRAG)
  12.2 Data Lineage and Audit Trail
  12.3 Token Budget Controller
  12.4 AutoRAGTuner (Bayesian Optimization)
  12.5 Human Feedback Loop
  12.6 Security Monitor (CleanBase, Needle-in-RAG)

## Part V — MVP Implementation
### 13. MVP Architecture and Scope
  13.1 What is Implemented in the MVP
  13.2 Technology Stack
  13.3 Local Development Setup (Docker Compose)

### 14. Key Implementation Details
  14.1 FastAPI Application Structure
  14.2 Ingestion Pipeline Code Walkthrough
  14.3 Query Pipeline Code Walkthrough
  14.4 Hybrid Retrieval: RRF across Vector + BM25 + Tree
  14.5 Cross-Encoder Reranking (ms-marco-MiniLM)
  14.6 Knowledge Graph Builder
  14.7 Merkle Audit Log Implementation

### 15. API Reference
  15.1 POST /api/v1/query
  15.2 POST /api/v1/ingest
  15.3 GET /api/v1/health
  15.4 POST /api/v1/feedback
  15.5 Authentication and RBAC

## Part VI — Quality, Performance and Roadmap
### 16. Evaluation Framework
  16.1 RAGAS Metrics (Faithfulness, Relevancy, Recall)
  16.2 EnterpriseRAG-Bench
  16.3 Prometheus Monitoring Dashboard

### 17. Performance and Scalability
  17.1 Latency Targets and Benchmarks
  17.2 Scaling Strategies
  17.3 Caching and Cost Optimization

### 18. Development Roadmap
  18.1 Phase 1 — Foundations (Weeks 1–6)
  18.2 Phase 2 — Semantic Layer (Weeks 7–12)
  18.3 Phase 3 — Quality and Control (Weeks 13–18)
  18.4 Phase 4 — Optimization and Governance (Weeks 19–24)

### 19. Conclusion

## Back Cover / References
  - Academic Paper References
  - Technology References
