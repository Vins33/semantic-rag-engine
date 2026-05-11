```mermaid
flowchart TD

    %% =========================================================
    %% MACRO AREA 1 - DATA SOURCES
    %% =========================================================

    subgraph A0["1. DATA SOURCES"]
        A1["Document Repositories<br/>PDF, DOCX, HTML, Markdown"]
        A2["Structured Sources<br/>CSV, SQL DB, Data Lake"]
        A3["Enterprise Sources<br/>SharePoint, Confluence, Git, Wiki"]
        A4["[v4] Multimodal Sources<br/>Images, Audio, Video, Scanned Docs"]
        A5["[v6] Streaming/Infinite Video Sources<br/>live video feeds, continuous streams,<br/>long-duration recordings"]
    end

    %% =========================================================
    %% MACRO AREA 2 - OFFLINE INGESTION PIPELINE
    %% =========================================================

    subgraph B0["2. OFFLINE INGESTION PIPELINE"]
        B1["Connectors<br/>(Access Control enforced)"]
        B2["Document Loading"]
        B3["Parsing"]
        B4["OCR if needed"]
        B5["Cleaning"]
        B6["Layout Analysis"]
        B7["Table Extraction"]
        B8["Source Provenance + Integrity Hash"]
        B9["Document Versioning"]
        B10["[v4] 3-Pass Pyramid Parser<br/>pixel → layout → semantic<br/>for vision-rich docs (arXiv 2511.21121)"]
        B11["[v5] CleanBase Pre-Index Gate<br/>anomaly detection over doc embeddings<br/>before entering the index;<br/>blocks poisoned/injected docs proactively<br/>(arXiv 2605.00460)"]
        B12["[v6] Event-Causal Segmenter<br/>segment streaming video → semantic events<br/>encode each event as SES (State→Event→State) graph<br/>merge all SES graphs → global Event Knowledge Graph<br/>(Event-Causal RAG: arXiv 2605.06185)"]
    end

    %% =========================================================
    %% MACRO AREA 3 - SEMANTIC LAYER
    %% =========================================================

    subgraph C0["3. SEMANTIC LAYER / ONTOLOGY PIPELINE"]
        C1["Controlled Vocabulary<br/>allowed terms, aliases, acronyms"]
        C2["Metadata Standards<br/>schemas, required fields, document types"]
        C3["Taxonomy<br/>hierarchies, parent-child relations"]
        C4["Thesaurus<br/>synonyms, related terms, broader/narrower terms"]
        C5["Ontology<br/>classes, properties, relations, constraints<br/>SHACL/OWL validation"]
        C6["Knowledge Graph<br/>entities, relations, provenance"]
        C7["[v3] LLM Auto-Ontology Builder<br/>entity recognition → relation extraction →<br/>triple generation → SHACL validation<br/>(Salovskii et al. 2604.20795)"]
        C8["[v5] EvoRAG KG Backpropagation<br/>feedback-driven KG update:<br/>retrieval failures → gradient-like signal →<br/>auto-refine KG triples without manual curation<br/>(arXiv 2604.15676)"]
        C9["[v5] Order-Aware Hypergraph<br/>temporal ordering of knowledge:<br/>event sequences, version history, 'valid-at' facts<br/>hyperedges connect >2 temporally ordered nodes<br/>(arXiv 2604.12185)"]
    end

    %% =========================================================
    %% MACRO AREA 4 - DOCUMENT PROCESSING
    %% =========================================================

    subgraph D0["4. DOCUMENT PROCESSING"]
        D1["Entity Extraction<br/>(GraphRAG: Edge et al. 2404.16130)"]
        D2["Relation Extraction<br/>(GraphRAG: entity knowledge graph)"]
        D3["Domain Classification"]
        D4["Metadata Enrichment"]
        D5["[v5] SAGE-Compressed Semantic Chunking<br/>selective attention extracts task-relevant spans<br/>at index time → compressed chunk representations<br/>128-256 token overlap baseline<br/>(SAGE: arXiv 2604.15583;<br/>Best Practices: Wang et al. 2407.01219)"]
        D6["[v3] Self-Aware Embedding Generation<br/>vector + timestamp + confidence_score + relational_links<br/>Ebbinghaus decay + QuOTE question-oriented alignment<br/>(SmartVector: Xu 2604.20598;<br/>QuOTE: arXiv 2502.10976)"]
        D7["[v4] Multimodal Feature Extraction<br/>CLIP/SigLIP image embeddings,<br/>table2text, audio transcription → embeddings<br/>cross-modal KG alignment<br/>(M³KG-RAG: arXiv 2512.20136 CVPR2026;<br/>Graph-to-Frame: arXiv 2604.04372 CVPR2026)"]
        D8["[v6] FT-RAG Table Entry-Graph Builder<br/>decompose tables → entry-level semantic units<br/>construct intra-table KG with typed cell relations<br/>structural neighbor expansion for graph retrieval<br/>+23.5% Hit Rate, +62.2% exact-value accuracy<br/>(FT-RAG: arXiv 2605.01495)"]
    end

    %% =========================================================
    %% MACRO AREA 5 - STORAGE AND INDEXING
    %% =========================================================

    subgraph E0["5. STORAGE AND INDEXING"]
        E1["Object Storage<br/>raw documents, parsed artifacts"]
        E2["Vector DB<br/>Qdrant, Milvus, Weaviate<br/>(Self-Aware Embeddings with confidence decay)"]
        E3["Keyword Index<br/>OpenSearch / Elasticsearch, BM25"]
        E4["Metadata Store<br/>PostgreSQL"]
        E5["[v3] Bitemporal Graph DB<br/>WorldDB: content-addressed Merkle nodes,<br/>typed edges (supersession, contradicts, same_as),<br/>on_insert/on_delete/on_query_rewrite handlers<br/>(Ganesan, arXiv 2604.18478)"]
        E6["Audit Log Store<br/>(Merkle audit trail from E5)"]
        E7["[v3] Hierarchical Tree Index<br/>Ψ-RAG: multi-granularity token → document,<br/>cross-document links, merging+collapse<br/>(Zhao & Yang, ICML 2026 arXiv 2605.00529)"]
        E8["[v4] Thinking Traces Store<br/>indexed reasoning trajectories from prior sessions<br/>compact retrieval-friendly units<br/>(T3: arXiv 2605.03344)<br/>+56.3% on AIME2026, -15% inference cost"]
        E9["[v4] Multimodal KG Store<br/>unified text + image + audio graph<br/>cross-modal typed-edge relations<br/>(M³KG-RAG CVPR2026; MegaRAG ACL2026)"]
        E10["[v6] Parametric Knowledge Store<br/>domain knowledge encoded in LoRA adapters<br/>Orthogonal Subspace Decomposition (OSD):<br/>task LoRA ⊥ domain LoRAs → stable multi-adapter merge<br/>no index maintenance, no retrieval latency<br/>(Composable PRAG: arXiv 2604.26768)"]
        E11["[v6] Event Knowledge Graph Store<br/>SES graphs merged → global causal-topological memory<br/>dual-store: semantic matching + causal-topological retrieval<br/>supports multi-event integration & cross-temporal inference<br/>(Event-Causal RAG: arXiv 2605.06185)"]
    end

    %% =========================================================
    %% MACRO AREA 6 - ONLINE QUERY PIPELINE
    %% =========================================================

    subgraph F0["6. ONLINE QUERY PIPELINE"]
        F1["User Query"]
        F2["[v5] Intent + Complexity Scoring<br/>SURE-RAG: retrieve or not? gate<br/>(sufficiency + uncertainty check)<br/>When-to-Retrieve for LRM CoT chains:<br/>adaptive mid-reasoning trigger for o1/DeepSeek-R1<br/>(SURE-RAG: arXiv 2605.03534;<br/>Adaptive Retrieval LRM: arXiv 2604.26649 SIGIR2026)"]
        F3["Query Rewriting<br/>(HyDE / Step-back)"]
        F4["Query Expansion<br/>via vocabulary, taxonomy, thesaurus"]
        F5["[v5] Retrieval Routing<br/>RouteRAG RL router: text / keyword / graph /<br/>tree / multimodal / thinking traces / multi-agent /<br/>intrinsic (INTRA) / parametric (LoRA)<br/>CacheRAG: semantic sub-plan cache →<br/>reuse retrieval plans for similar queries<br/>(RouteRAG: arXiv 2512.09487;<br/>CacheRAG: arXiv 2604.26176)"]
        F5B["[v5] Semantic Plan Cache<br/>if similar query hit: return cached retrieval plan<br/>skip full retrieval pipeline<br/>(CacheRAG: arXiv 2604.26176)"]
    end

    %% =========================================================
    %% MACRO AREA 6B - ITERATIVE RETRIEVAL CONTROLLER
    %% =========================================================

    subgraph F6["6B. ITERATIVE RETRIEVAL CONTROLLER"]
        F6A["[v5] S2G Quality Evaluator<br/>two explicit decisions:<br/>① Is current evidence sufficient?<br/>② What gap must next retrieval fill?<br/>(S2G-RAG: arXiv 2604.23783 ACL2026;<br/>CRAG baseline: Yan et al. 2401.15884)"]
        F6B{"Evidence<br/>sufficient?"}
        F6C["Web Search Fallback<br/>external augmentation"]
        F6D["[v5] AutoSearch RL Stop Policy<br/>RL learns when-to-stop-searching:<br/>balances quality vs. retrieval cost<br/>-40% average retrieval steps<br/>(AutoSearch: arXiv 2604.17337)"]
        F6E["Sub-query Decomposer<br/>(Self-RAG: Asai et al. 2310.11511)"]
        F6F["[v3] Contradiction Detector<br/>(Korn, arXiv 2605.05632)"]
        F6G["[v4] TruthfulRAG Fact Alignment<br/>text ↔ KG triples via SHACL;<br/>resolve factual conflicts pre-generation<br/>(arXiv 2511.10375 AAAI2026)"]
        F6H["[v5] AdaGATE + NeocorRAG Assembly<br/>detect knowledge gaps in partial answer;<br/>build explicit evidence chains bridging retrieval↔QA<br/>retrieve only missing evidence tokens (-40% tokens)<br/>(AdaGATE: arXiv 2605.05245;<br/>NeocorRAG: arXiv 2604.27852 WWW2026)"]
    end

    %% =========================================================
    %% MACRO AREA 7 - RETRIEVAL AND RANKING
    %% =========================================================

    subgraph G0["7. HYBRID RETRIEVAL AND RANKING"]
        G1["Vector Retrieval<br/>(4-signal: semantic + temporal + confidence + graph)"]
        G2["Keyword Retrieval<br/>BM25"]
        G3["Metadata Filtering"]
        G4["Graph Traversal<br/>(Bitemporal GraphDB + Order-Aware Hypergraph +<br/>Event KG causal-topological traversal)"]
        G5["[v5] Denoising-First Semantic Filter<br/>objective: noise elimination over relevance ranking<br/>LLM attention budget is finite —<br/>irrelevant context hurts more than helps<br/>(LLM-Oriented IR: arXiv 2605.00505 SIGIR2026)"]
        G6["[v4+v5] CAR Confidence-Aware Reranker<br/>Verbal Annotations (Verbal-R3) +<br/>query-passage relevance × passage confidence<br/>confidence-weighted RRF fusion<br/>(Verbal-R3: arXiv 2605.01399 ACL2026;<br/>CAR: arXiv 2605.04495)"]
        G7["[v3] Hierarchical Tree Retrieval<br/>multi-granularity: token / paragraph / document<br/>(Ψ-RAG: arXiv 2605.00529 ICML2026)"]
        G8["[v4] Multimodal Retrieval<br/>cross-modal evidence chaining:<br/>text ↔ image ↔ audio ↔ table<br/>(M³KG-RAG: arXiv 2512.20136 CVPR2026)"]
        G9["[v4] Thinking Traces Retrieval<br/>retrieve prior reasoning trajectories<br/>relevant to current query structure<br/>(T3: arXiv 2605.03344)"]
        G11["[v6] INTRA Attention-Native Retrieval<br/>intrinsic retrieval via decoder attention queries<br/>pre-encoded evidence chunks scored in-model<br/>no separate retriever or embedding model needed<br/>eliminates retriever-generator representation mismatch<br/>(INTRA: arXiv 2605.05806)"]
        G12["[v6] Parametric Retrieval<br/>load relevant LoRA adapter(s) at inference time<br/>multi-adapter merge via OSD<br/>no index, no retrieval latency, graceful multi-domain<br/>(Composable PRAG: arXiv 2604.26768)"]
    end

    %% =========================================================
    %% MACRO AREA 7B - CONTEXT COMPRESSION [v5]
    %% Query-conditioned compression before generation
    %% (Query-Conditioned Selector: arXiv 2602.15856 WWW2026)
    %% =========================================================

    subgraph G10["7B. CONTEXT COMPRESSION [v5]"]
        G10A["Query-Conditioned Compressor<br/>compress retrieved context conditioned on query;<br/>preserves task-relevant information,<br/>discards irrelevant passages<br/>(arXiv 2602.15856 WWW2026)"]
        G10B["Anchored Confabulation Guard<br/>WARNING: partial evidence amplifies hallucinations<br/>before full evidence is assembled;<br/>enforce complete evidence chains before generation<br/>(arXiv 2604.25931)"]
        G10C["MEG-RAG Grounding Scorer<br/>quantify whether retrieved visual/textual evidence<br/>is genuinely used vs. ignored in generation<br/>(MEG-RAG: arXiv 2604.24564)"]
    end

    %% =========================================================
    %% MACRO AREA 8 - GENERATION AND VALIDATION
    %% =========================================================

    subgraph H0["8. GENERATION AND VALIDATION"]
        H1["Context Builder<br/>+ Community Summaries (GraphRAG)<br/>+ Verbal Annotations (Verbal-R3)<br/>+ Multimodal Context Fusion (balanced text/visual)"]
        H2["[v4+v5] Multi-Agent LLM Layer<br/>MEMTIER tiered memory: working/episodic/semantic<br/>promotion+eviction, -14pp degradation over 72h<br/>CogRAG+: diagnose memory vs. reasoning failures →<br/>targeted remediation per failure type<br/>(AgenticRAG: arXiv 2605.05538;<br/>MEMTIER: arXiv 2605.03675;<br/>CogRAG+: arXiv 2604.25928;<br/>Agentic RAG Survey: arXiv 2501.09136)"]
        H3["Tool Calling"]
        H4["Structured Output"]
        H5["Grounding Check<br/>(Self-RAG: Asai et al. 2310.11511)"]
        H6["Citation Validation<br/>+ XGRAG Explanation:<br/>why specific KG subgraphs were retrieved<br/>(XGRAG: arXiv 2604.24623)"]
        H7["Compliance Check<br/>ComplianceNLP: multi-framework regulatory gap detection<br/>(arXiv 2604.23585 ACL2026 Industry)"]
        H8["Final Answer<br/>answer, sources, metadata, confidence,<br/>hop_count, temporal_validity,<br/>source_trust_score, modality_sources,<br/>retrieval_explanation"]
    end

    %% =========================================================
    %% MACRO AREA 8B - AGENTIC SELF-CORRECTION LOOP
    %% =========================================================

    subgraph H9["8B. AGENTIC SELF-CORRECTION"]
        H9A{"Grounding OK?"}
        H9B["Reflection & Re-planning<br/>CogRAG+: memory gap vs. reasoning gap diagnosis<br/>(Self-RAG reflection tokens +<br/>CogRAG+: arXiv 2604.25928)"]
        H9C["Query Refinement<br/>back to retrieval"]
    end

    %% =========================================================
    %% MACRO AREA 8C - SPECULATIVE GENERATION LOOP [v4]
    %% =========================================================

    subgraph H10["8C. SPECULATIVE GENERATION [v4]"]
        H10A["Specialist LM<br/>drafts answer from top-k chunks<br/>(small, fast, domain-tuned model)"]
        H10B["Generalist LM<br/>verifies draft: grounding, coherence, faithfulness"]
        H10C{"Draft<br/>Accepted?"}
        H10D["Refinement Pass<br/>generalist rewrites with additional context"]
    end

    %% =========================================================
    %% MACRO AREA 8D - MEPIC KV-CACHE LAYER [v4]
    %% =========================================================

    subgraph H11["8D. MEPIC SERVING LAYER [v4]"]
        H11A["KV-Cache Manager<br/>position-independent cache<br/>for repeated document chunks<br/>(MEPIC: arXiv 2512.16822)<br/>-60% GPU memory pressure"]
        H11B["Cache Hit Router<br/>reuse cached KV states<br/>across different prompt positions"]
    end

    %% =========================================================
    %% MACRO AREA 9 - GOVERNANCE AND FEEDBACK
    %% =========================================================

    subgraph I0["9. GOVERNANCE AND FEEDBACK"]
        I1["[v5] Access Control + Privacy Layer<br/>vendor-neutral, multitenant<br/>PRAG: end-to-end cryptographic privacy<br/>query privacy + document privacy<br/>(PRAG: arXiv 2604.26525)"]
        I2["Data Lineage<br/>Merkle hash chain (E5+E6)<br/>+ XGRAG graph retrieval explanations"]
        I3["Monitoring<br/>+ Retrieval Score Tracking<br/>+ Temporal Staleness Alerts<br/>+ Multimodal Coverage Metrics<br/>+ Anchored Confabulation Risk Alerts"]
        I4["Evaluation Metrics<br/>RAGAS, TruLens, Precision@K,<br/>EnterpriseRAG-Bench (arXiv 2605.05253),<br/>DICE probabilistic scoring (arXiv 2512.22629),<br/>MEG-RAG multimodal grounding score (arXiv 2604.24564)"]
        I5["Human Feedback<br/>(confidence reconsolidation → SmartVector<br/>+ EvoRAG KG backpropagation signal)"]
        I6["Ontology Updates<br/>(auto-triggered via C7 + C8 EvoRAG)"]
        I7["[v4+v5] Security Monitor<br/>CleanBase: pre-index anomaly detection (arXiv 2605.00460)<br/>KB Poisoning Detection (arXiv 2605.05632)<br/>Needle-in-RAG: character-level span forensics (arXiv 2605.01782)<br/>LeakDojo: 5-category leakage model (arXiv 2605.05818)<br/>SoK: full agentic attack surface map (arXiv 2603.22928)<br/>MemoryGraft: agent experience poisoning defense (arXiv 2512.16962)"]
        I8["[v4] AutoRAGTuner<br/>Bayesian black-box optimization:<br/>chunk size, top-k, reranker, prompt templates<br/>(arXiv 2605.02967 EuroSys2026)"]
        I9["[v6] PAS Geospatial Privacy<br/>location-as-query privacy via anchor substitution<br/>⟨anchor, direction bin, distance bin⟩ encoding<br/>~370-400m adversarial location error<br/>non-monotonic privacy-utility tradeoff<br/>(PAS-Spatial: arXiv 2605.05459)"]
    end

    %% =========================================================
    %% MAIN OFFLINE FLOW
    %% =========================================================

    A1 --> B1
    A2 --> B1
    A3 --> B1
    A4 --> B10
    A5 --> B12

    B1 --> B2
    B2 --> B3
    B3 --> B4
    B4 --> B5
    B5 --> B6
    B6 --> B7
    B7 --> B8
    B8 --> B11
    B11 --> B9

    B10 --> B11
    B12 --> E11

    B7 --> D8

    B9 --> D1
    D1 --> D2
    D2 --> D3
    D3 --> D4
    D4 --> D5

    B10 --> D7
    D7 --> E9
    D7 --> E2

    %% EvoRAG + Auto-Ontology
    C7 --> C1
    C7 --> C5
    C7 --> C6
    C8 --> C6
    C8 --> C5
    C9 --> E5
    D1 -.-> C7
    D2 -.-> C7

    C1 --> C2
    C2 --> C3
    C3 --> C4
    C4 --> C5
    C5 --> C6

    C1 -.-> D1
    C3 -.-> D2
    C5 -.-> D3
    C6 -.-> D1
    C6 -.-> D2

    C6 --> D5
    D5 --> D6

    D6 --> E2
    D5 --> E3
    D5 --> E7
    D4 --> E4
    C6 --> E5
    B9 --> E1
    B8 --> E6
    E5 -.-> E6

    %% FT-RAG table entry-graph → stores
    D8 --> E5
    D8 --> E2

    %% Parametric store populated from document processing
    D5 --> E10

    %% Thinking Traces Store populated by H0 reasoning
    H5 -.-> E8

    %% =========================================================
    %% MAIN ONLINE FLOW
    %% =========================================================

    F1 --> F2
    F2 -- "Confident — skip retrieval" --> G10A
    F2 -- "Retrieve" --> F3
    F3 --> F4
    F4 --> F5
    F5 -- "Cache hit" --> F5B
    F5B --> G10A
    F5 -- "Cache miss" --> G1
    F5 --> G2
    F5 --> G3
    F5 --> G4
    F5 --> G7
    F5 --> G8
    F5 --> G9
    F5 --> G11
    F5 --> G12

    E2 --> G1
    E3 --> G2
    E4 --> G3
    E5 --> G4
    E7 --> G7
    E9 --> G8
    E8 --> G9
    E11 --> G4
    E10 --> G12

    G1 --> G5
    G2 --> G5
    G3 --> G5
    G4 --> G5
    G7 --> G5
    G8 --> G5
    G9 --> G5
    G11 --> G5
    G5 --> G6

    %% Parametric retrieval bypasses denoising/reranking — feeds directly to compression
    G12 --> G10A

    %% Context compression pipeline
    G6 --> F6A
    F6A --> F6F
    F6F --> F6G
    F6G --> F6B
    F6B -- "Sufficient" --> F6H
    F6H --> G10A
    F6B -- "Gap identified" --> F6E
    F6B -- "Low score" --> F6C
    F6C --> G10A
    F6E --> F6D
    F6D -- "Stop" --> G10A
    F6D -- "Continue" --> F5

    G10A --> G10B
    G10B --> G10C
    G10C --> H1

    H1 --> H2
    H2 --> H3
    H2 --> H4
    H3 --> H5
    H4 --> H5

    %% MEPIC caching
    H1 --> H11A
    H11A --> H11B
    H11B --> H2

    %% Speculative generation
    H5 --> H10A
    H10A --> H10B
    H10B --> H10C
    H10C -- "Accepted" --> H6
    H10C -- "Rejected" --> H10D
    H10D --> H6

    %% Agentic self-correction
    H5 --> H9A
    H9A -- "Grounded" --> H10A
    H9A -- "Not grounded" --> H9B
    H9B --> H9C
    H9C -.-> F3

    H6 --> H7
    H7 --> H8

    %% =========================================================
    %% SEMANTIC LAYER ONLINE
    %% =========================================================

    C1 -.-> F4
    C3 -.-> F4
    C4 -.-> F4
    C5 -.-> G5
    C6 -.-> G4
    C6 -.-> H1
    E9 -.-> C6

    %% =========================================================
    %% GOVERNANCE CONNECTIONS
    %% =========================================================

    I1 -.-> B1
    I1 -.-> F1
    I2 -.-> E6
    I3 -.-> G6
    I3 -.-> F6A
    I3 -.-> G10B
    I4 -.-> H8
    I4 -.-> G10C
    I5 -.-> I6
    I5 -.-> E2
    I5 -.-> C8
    I6 -.-> C7
    I6 -.-> C8
    I6 -.-> C1
    I6 -.-> C3
    I6 -.-> C5
    I6 -.-> C6
    I7 -.-> B11
    I7 -.-> F6F
    I7 -.-> F6G
    I7 -.-> B8
    I7 -.-> H2
    I8 -.-> F5
    I8 -.-> G6
    I8 -.-> D5
    I8 -.-> G12
    I9 -.-> F1
    I9 -.-> I1

    %% EvoRAG feedback loop
    H8 -.-> C8

    %% =========================================================
    %% SELF-AWARE EMBEDDING LIFECYCLE
    %% =========================================================

    E2 -.-> I3
    I5 -.-> D6

    %% =========================================================
    %% COLORS
    %% =========================================================

    classDef dataSources fill:#E3F2FD,stroke:#1565C0,stroke-width:2px,color:#0D1B2A;
    classDef dataSourcesNew fill:#BBDEFB,stroke:#0D47A1,stroke-width:3px,color:#0D1B2A;
    classDef dataSourcesV6 fill:#64B5F6,stroke:#01033D,stroke-width:4px,color:#0D1B2A;
    classDef ingestion fill:#E8F5E9,stroke:#2E7D32,stroke-width:2px,color:#0D1B2A;
    classDef ingestionNew fill:#C8E6C9,stroke:#1B5E20,stroke-width:3px,color:#0D1B2A;
    classDef ingestionV5 fill:#A5D6A7,stroke:#0A3D0A,stroke-width:3px,color:#0D1B2A;
    classDef ingestionV6 fill:#66BB6A,stroke:#012201,stroke-width:4px,color:#0D1B2A;
    classDef semantic fill:#FFF3E0,stroke:#EF6C00,stroke-width:2px,color:#0D1B2A;
    classDef semanticNew fill:#FFE0B2,stroke:#BF360C,stroke-width:3px,color:#0D1B2A;
    classDef semanticV5 fill:#FFCC80,stroke:#8D2800,stroke-width:3px,color:#0D1B2A;
    classDef processing fill:#F3E5F5,stroke:#6A1B9A,stroke-width:2px,color:#0D1B2A;
    classDef processingNew fill:#E1BEE7,stroke:#4A148C,stroke-width:3px,color:#0D1B2A;
    classDef processingV5 fill:#CE93D8,stroke:#2A004A,stroke-width:3px,color:#0D1B2A;
    classDef processingV6 fill:#AB47BC,stroke:#0D001A,stroke-width:4px,color:#FFFFFF;
    classDef storage fill:#ECEFF1,stroke:#455A64,stroke-width:2px,color:#0D1B2A;
    classDef storageNew fill:#CFD8DC,stroke:#263238,stroke-width:3px,color:#0D1B2A;
    classDef storageV4 fill:#B0BEC5,stroke:#102027,stroke-width:3px,color:#0D1B2A;
    classDef storageV6 fill:#78909C,stroke:#020A0D,stroke-width:4px,color:#FFFFFF;
    classDef query fill:#E0F7FA,stroke:#00838F,stroke-width:2px,color:#0D1B2A;
    classDef queryV5 fill:#B2EBF2,stroke:#004D57,stroke-width:3px,color:#0D1B2A;
    classDef iterative fill:#E8EAF6,stroke:#283593,stroke-width:2px,color:#0D1B2A;
    classDef iterativeNew fill:#C5CAE9,stroke:#1A237E,stroke-width:3px,color:#0D1B2A;
    classDef iterativeV4 fill:#9FA8DA,stroke:#0D1B6E,stroke-width:3px,color:#0D1B2A;
    classDef iterativeV5 fill:#7986CB,stroke:#001064,stroke-width:3px,color:#FFFFFF;
    classDef retrieval fill:#FCE4EC,stroke:#AD1457,stroke-width:2px,color:#0D1B2A;
    classDef retrievalNew fill:#F8BBD9,stroke:#880E4F,stroke-width:3px,color:#0D1B2A;
    classDef retrievalV4 fill:#F48FB1,stroke:#560027,stroke-width:3px,color:#0D1B2A;
    classDef retrievalV5 fill:#F06292,stroke:#3D0020,stroke-width:3px,color:#FFFFFF;
    classDef retrievalV6 fill:#E91E63,stroke:#14000F,stroke-width:4px,color:#FFFFFF;
    classDef compress fill:#FFF9C4,stroke:#F57F17,stroke-width:3px,color:#0D1B2A;
    classDef generation fill:#EDE7F6,stroke:#4527A0,stroke-width:2px,color:#0D1B2A;
    classDef generationNew fill:#D1C4E9,stroke:#311B92,stroke-width:3px,color:#0D1B2A;
    classDef generationV4 fill:#B39DDB,stroke:#1A0050,stroke-width:3px,color:#0D1B2A;
    classDef agentic fill:#F9FBE7,stroke:#827717,stroke-width:2px,color:#0D1B2A;
    classDef speculative fill:#FFF8E1,stroke:#F57F17,stroke-width:3px,color:#0D1B2A;
    classDef serving fill:#E8F5E9,stroke:#1B5E20,stroke-width:3px,color:#0D1B2A;
    classDef governance fill:#FFEBEE,stroke:#C62828,stroke-width:2px,color:#0D1B2A;
    classDef governanceNew fill:#FFCDD2,stroke:#B71C1C,stroke-width:3px,color:#0D1B2A;
    classDef governanceV4 fill:#EF9A9A,stroke:#7F0000,stroke-width:3px,color:#0D1B2A;
    classDef governanceV5 fill:#E57373,stroke:#4A0000,stroke-width:3px,color:#FFFFFF;
    classDef governanceV6 fill:#C62828,stroke:#1A0000,stroke-width:4px,color:#FFFFFF;

    class A1,A2,A3 dataSources;
    class A4 dataSourcesNew;
    class A5 dataSourcesV6;
    class B1,B2,B3,B4,B5,B6,B7,B8,B9 ingestion;
    class B10 ingestionNew;
    class B11 ingestionV5;
    class B12 ingestionV6;
    class C1,C2,C3,C4,C5,C6 semantic;
    class C7 semanticNew;
    class C8,C9 semanticV5;
    class D1,D2,D3,D4 processing;
    class D5,D6,D7 processingNew;
    class D8 processingV6;
    class E1,E2,E3,E4 storage;
    class E5,E6,E7 storageNew;
    class E8,E9 storageV4;
    class E10,E11 storageV6;
    class F1,F3,F4 query;
    class F2,F5,F5B queryV5;
    class F6A iterativeV5;
    class F6B,F6C,F6E iterative;
    class F6F iterativeNew;
    class F6G iterativeV4;
    class F6D,F6H iterativeV5;
    class G1,G2,G3,G4 retrieval;
    class G5 retrievalV5;
    class G6,G7 retrievalNew;
    class G8,G9 retrievalV4;
    class G11,G12 retrievalV6;
    class G10A,G10B,G10C compress;
    class H1,H3,H4,H5 generation;
    class H6,H7,H8 generationNew;
    class H2 generationV4;
    class H9A,H9B,H9C agentic;
    class H10A,H10B,H10C,H10D speculative;
    class H11A,H11B serving;
    class I1,I2,I3,I4,I5,I6 governance;
    class I7,I8 governanceNew;
    class I9 governanceV6;
```