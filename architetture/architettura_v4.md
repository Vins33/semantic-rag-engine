flowchart TD

    %% =========================================================
    %% MACRO AREA 1 - DATA SOURCES
    %% =========================================================

    subgraph A0["1. DATA SOURCES"]
        A1["Document Repositories<br/>PDF, DOCX, HTML, Markdown"]
        A2["Structured Sources<br/>CSV, SQL DB, Data Lake"]
        A3["Enterprise Sources<br/>SharePoint, Confluence, Git, Wiki"]
        A4["[NEW v4] Multimodal Sources<br/>Images, Audio, Video, Scanned Docs"]
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
        B10["[NEW v4] 3-Pass Pyramid Parser<br/>pixel → layout → semantic<br/>for vision-rich docs (PDF, scans)<br/>(arXiv 2511.21121)"]
    end

    %% =========================================================
    %% MACRO AREA 3 - SEMANTIC LAYER
    %% [N4-v3] Auto-construction pipeline via LLM
    %% (Salovskii & Gorshkova, arXiv 2604.20795)
    %% =========================================================

    subgraph C0["3. SEMANTIC LAYER / ONTOLOGY PIPELINE"]
        C1["Controlled Vocabulary<br/>allowed terms, aliases, acronyms"]
        C2["Metadata Standards<br/>schemas, required fields, document types"]
        C3["Taxonomy<br/>hierarchies, parent-child relations"]
        C4["Thesaurus<br/>synonyms, related terms, broader/narrower terms"]
        C5["Ontology<br/>classes, properties, relations, constraints<br/>SHACL/OWL validation"]
        C6["Knowledge Graph<br/>entities, relations, provenance"]
        C7["[v3] LLM Auto-Ontology Builder<br/>entity recognition → relation extraction →<br/>triple generation → SHACL validation →<br/>continuous graph update<br/>(Salovskii et al. 2604.20795)"]
    end

    %% =========================================================
    %% MACRO AREA 4 - DOCUMENT PROCESSING
    %% =========================================================

    subgraph D0["4. DOCUMENT PROCESSING"]
        D1["Entity Extraction<br/>(GraphRAG: Edge et al. 2404.16130)"]
        D2["Relation Extraction<br/>(GraphRAG: entity knowledge graph)"]
        D3["Domain Classification"]
        D4["Metadata Enrichment"]
        D5["Semantic Chunking<br/>128-256 token overlap<br/>(Best Practices: Wang et al. 2407.01219)"]
        D6["[v3] Self-Aware Embedding Generation<br/>vector + timestamp + confidence_score + relational_links<br/>Ebbinghaus decay + feedback reconsolidation<br/>+ QuOTE question-oriented alignment<br/>(SmartVector: Xu 2604.20598 + QuOTE: arXiv 2502.10976)"]
        D7["[NEW v4] Multimodal Feature Extraction<br/>image embeddings (CLIP/SigLIP),<br/>table2text, audio transcription → embeddings<br/>→ cross-modal KG alignment<br/>(M³KG-RAG: arXiv 2512.20136;<br/>MegaRAG: arXiv 2512.20626)"]
    end

    %% =========================================================
    %% MACRO AREA 5 - STORAGE AND INDEXING
    %% =========================================================

    subgraph E0["5. STORAGE AND INDEXING"]
        E1["Object Storage<br/>raw documents, parsed artifacts"]
        E2["Vector DB<br/>Qdrant, Milvus, Weaviate<br/>(Self-Aware Embeddings with confidence decay)"]
        E3["Keyword Index<br/>OpenSearch, Elasticsearch, BM25"]
        E4["Metadata Store<br/>PostgreSQL"]
        E5["[v3] Bitemporal Graph DB<br/>WorldDB pattern: content-addressed nodes (Merkle hash),<br/>typed edges (supersession, contradicts, same_as),<br/>on_insert/on_delete/on_query_rewrite handlers<br/>(Ganesan, arXiv 2604.18478)"]
        E6["Audit Log Store<br/>(Merkle audit trail from E5)"]
        E7["[v3] Hierarchical Tree Index<br/>Ψ-RAG: merging+collapse, cross-document links,<br/>multi-granularity (token → document level)<br/>(Zhao & Yang, ICML 2026 arXiv 2605.00529)"]
        E8["[NEW v4] Thinking Traces Store<br/>intermediate reasoning trajectories<br/>from prior problem-solving sessions<br/>indexed as compact retrieval-friendly units<br/>(T3: Arabzadeh et al. arXiv 2605.03344)<br/>+56.3% on AIME2026, -15% inference cost"]
        E9["[NEW v4] Multimodal KG Store<br/>unified text + image + audio graph<br/>cross-modal edges with typed relations<br/>(M³KG-RAG CVPR2026; MegaRAG ACL2026)"]
    end

    %% =========================================================
    %% MACRO AREA 6 - ONLINE QUERY PIPELINE
    %% =========================================================

    subgraph F0["6. ONLINE QUERY PIPELINE"]
        F1["User Query"]
        F2["Intent Detection<br/>+ Query Complexity Scoring<br/>+ SURE-RAG: Retrieve or Not? gate<br/>(sufficiency + uncertainty check)<br/>(arXiv 2605.03534)"]
        F3["Query Rewriting<br/>(HyDE / Step-back)"]
        F4["Query Expansion<br/>via vocabulary, taxonomy, thesaurus"]
        F5["Retrieval Routing<br/>RouteRAG RL router: text / keyword / graph /<br/>tree / multimodal KG / thinking traces / multi-agent<br/>(RAG and Beyond: Zhao et al. 2409.14924;<br/>RouteRAG: arXiv 2512.09487)"]
    end

    %% =========================================================
    %% MACRO AREA 6B - ITERATIVE RETRIEVAL CONTROLLER
    %% (v2: CRAG + Self-RAG; v3: Contradiction Detector;
    %%  v4: TruthfulRAG fact alignment + AdaGATE gap assembly)
    %% =========================================================

    subgraph F6["6B. ITERATIVE RETRIEVAL CONTROLLER"]
        F6A["Retrieval Quality Evaluator<br/>(CRAG: Yan et al. 2401.15884)"]
        F6B{"Score OK?"}
        F6C["Web Search Fallback<br/>external augmentation"]
        F6D["Hop Counter<br/>max N iterations"]
        F6E["Sub-query Decomposer<br/>(Self-RAG: Asai et al. 2310.11511)"]
        F6F["[v3] Contradiction Detector<br/>conflict between retrieved docs<br/>(Korn, arXiv 2605.05632)"]
        F6G["[NEW v4] TruthfulRAG Fact Alignment<br/>align text ↔ KG triples via SHACL;<br/>resolve factual conflicts before generation<br/>(arXiv 2511.10375 — AAAI 2026)"]
        F6H["[NEW v4] AdaGATE Gap-Aware Assembly<br/>detect knowledge gaps in partial answer;<br/>retrieve only missing evidence tokens<br/>-40% token budget<br/>(arXiv 2605.05245)"]
    end

    %% =========================================================
    %% MACRO AREA 7 - RETRIEVAL AND RANKING
    %% =========================================================

    subgraph G0["7. HYBRID RETRIEVAL AND RANKING"]
        G1["Vector Retrieval<br/>(4-signal score: semantic + temporal + confidence + graph)"]
        G2["Keyword Retrieval<br/>BM25"]
        G3["Metadata Filtering"]
        G4["Graph Traversal<br/>(Bitemporal GraphDB — WorldDB pattern)"]
        G5["Semantic Filtering"]
        G6["[v3+v4] CAR Confidence-Aware Reranker<br/>Verbal Annotations (Verbal-R3) +<br/>query-passage relevance × passage confidence<br/>fused via confidence-weighted RRF<br/>(Verbal-R3: Park et al. ACL2026 arXiv 2605.01399;<br/>CAR: arXiv 2605.04495)"]
        G7["[v3] Hierarchical Tree Retrieval<br/>multi-granularity: token / paragraph / document<br/>(Ψ-RAG: Zhao & Yang, ICML 2026)"]
        G8["[NEW v4] Multimodal Retrieval<br/>cross-modal evidence chaining:<br/>text ↔ image ↔ audio ↔ table<br/>(M³KG-RAG: arXiv 2512.20136 CVPR2026)"]
        G9["[NEW v4] Thinking Traces Retrieval<br/>retrieve prior reasoning trajectories<br/>relevant to current query structure<br/>(T3: arXiv 2605.03344)"]
    end

    %% =========================================================
    %% MACRO AREA 8 - GENERATION AND VALIDATION
    %% =========================================================

    subgraph H0["8. GENERATION AND VALIDATION"]
        H1["Context Builder<br/>+ Community Summaries (GraphRAG)<br/>+ Verbal Annotations (Verbal-R3)<br/>+ Multimodal Context Fusion"]
        H2["[v3+v4] Multi-Agent LLM Layer<br/>MEMTIER tiered memory: working/episodic/semantic<br/>promotion+eviction policies, -14pp degradation over 72h<br/>Agentic tool use: search, find, open, summarize<br/>(AgenticRAG: Suresh et al. arXiv 2605.05538;<br/>MEMTIER: arXiv 2605.03675;<br/>Agentic RAG Survey: Singh et al. arXiv 2501.09136)"]
        H3["Tool Calling"]
        H4["Structured Output"]
        H5["Grounding Check<br/>(Self-RAG: Asai et al. 2310.11511)"]
        H6["Citation Validation"]
        H7["Compliance Check"]
        H8["Final Answer<br/>answer, sources, metadata, confidence,<br/>hop_count, temporal_validity,<br/>source_trust_score, modality_sources"]
    end

    %% =========================================================
    %% MACRO AREA 8B - AGENTIC SELF-CORRECTION LOOP
    %% (v2: Self-RAG pattern)
    %% =========================================================

    subgraph H9["8B. AGENTIC SELF-CORRECTION"]
        H9A{"Grounding OK?"}
        H9B["Reflection & Re-planning<br/>(Self-RAG reflection tokens)"]
        H9C["Query Refinement<br/>back to retrieval"]
    end

    %% =========================================================
    %% MACRO AREA 8C - SPECULATIVE GENERATION LOOP  [NEW v4]
    %% Specialist draft → Generalist verify → Accept/Reject
    %% (Speculative RAG: Wang et al. ICLR 2025 arXiv 2407.08223)
    %% =========================================================

    subgraph H10["8C. SPECULATIVE GENERATION [NEW v4]"]
        H10A["Specialist LM<br/>drafts answer from top-k chunks<br/>(small, fast, domain-tuned model)"]
        H10B["Generalist LM<br/>verifies draft: checks grounding,<br/>coherence, faithfulness"]
        H10C{"Draft Accepted?"}
        H10D["Refinement Pass<br/>generalist rewrites rejected draft<br/>with additional retrieved context"]
    end

    %% =========================================================
    %% MACRO AREA 8D - MEPIC KV-CACHE LAYER  [NEW v4]
    %% Position-independent KV-cache for repeated chunks
    %% (arXiv 2512.16822) — -60% GPU memory pressure
    %% =========================================================

    subgraph H11["8D. MEPIC SERVING LAYER [NEW v4]"]
        H11A["KV-Cache Manager<br/>position-independent cache<br/>for repeated document chunks<br/>(MEPIC: arXiv 2512.16822)"]
        H11B["Cache Hit Router<br/>reuse cached KV states<br/>across different prompt positions"]
    end

    %% =========================================================
    %% MACRO AREA 9 - GOVERNANCE AND FEEDBACK
    %% =========================================================

    subgraph I0["9. GOVERNANCE AND FEEDBACK"]
        I1["Access Control<br/>(vendor-neutral, multitenant)"]
        I2["Data Lineage<br/>(Merkle hash chain from E5+E6)"]
        I3["Monitoring<br/>+ Retrieval Score Tracking<br/>+ Temporal Staleness Alerts<br/>+ Multimodal Coverage Metrics"]
        I4["Evaluation Metrics<br/>RAGAS, TruLens, Precision@K,<br/>EnterpriseRAG-Bench (arXiv 2605.05253),<br/>DICE probabilistic scoring (arXiv 2512.22629)"]
        I5["Human Feedback<br/>(confidence reconsolidation → SmartVector)"]
        I6["Ontology Updates<br/>(auto-triggered via C7)"]
        I7["[v3+v4] Security Monitor<br/>KB Poisoning Detection (Korn arXiv 2605.05632)<br/>Needle-in-RAG: character-level span forensics (arXiv 2605.01782)<br/>LeakDojo: 5-category leakage threat model (arXiv 2605.05818)<br/>SoK: full agentic attack surface map (arXiv 2603.22928)<br/>MemoryGraft: agent experience poisoning defense (arXiv 2512.16962)"]
        I8["[NEW v4] AutoRAGTuner<br/>Bayesian black-box optimization of:<br/>chunk size, top-k, reranker, prompt templates<br/>declarative config → auto end-to-end tuning<br/>(arXiv 2605.02967 — EuroSys 2026)"]
    end

    %% =========================================================
    %% MAIN OFFLINE FLOW
    %% =========================================================

    A1 --> B1
    A2 --> B1
    A3 --> B1
    A4 --> B10

    B1 --> B2
    B2 --> B3
    B3 --> B4
    B4 --> B5
    B5 --> B6
    B6 --> B7
    B7 --> B8
    B8 --> B9

    %% Multimodal path
    B10 --> B8

    B9 --> D1
    D1 --> D2
    D2 --> D3
    D3 --> D4
    D4 --> D5

    %% [NEW v4] Multimodal feature extraction branch
    B10 --> D7
    D7 --> E9
    D7 --> E2

    %% [v3] LLM Auto-Ontology Builder feeds and is fed by semantic layer
    C7 --> C1
    C7 --> C5
    C7 --> C6
    D1 -.-> C7
    D2 -.-> C7

    C1 --> C2
    C2 --> C3
    C3 --> C4
    C4 --> C5
    C5 --> C6

    %% Semantic layer guides processing (dotted = guidance, not data flow)
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

    %% [NEW v4] Thinking Traces Store populated by H0 reasoning
    H5 -.-> E8

    %% =========================================================
    %% MAIN ONLINE FLOW
    %% =========================================================

    F1 --> F2
    F2 -- "Confident — skip retrieval" --> H1
    F2 -- "Retrieve" --> F3
    F3 --> F4
    F4 --> F5

    F5 --> G1
    F5 --> G2
    F5 --> G3
    F5 --> G4
    F5 --> G7
    F5 --> G8
    F5 --> G9

    E2 --> G1
    E3 --> G2
    E4 --> G3
    E5 --> G4
    E7 --> G7
    E9 --> G8
    E8 --> G9

    G1 --> G5
    G2 --> G5
    G3 --> G5
    G4 --> G5
    G7 --> G5
    G8 --> G5
    G9 --> G5
    G5 --> G6

    %% [v3+v4] CAR reranker → quality evaluation → contradiction/fact-align → gap assembly
    G6 --> F6A
    F6A --> F6F
    F6F --> F6G
    F6G --> F6B
    F6B -- "OK" --> F6H
    F6H --> H1
    F6B -- "Low score" --> F6C
    F6C --> H1
    F6B -- "Multi-hop needed" --> F6E
    F6E --> F6D
    F6D -- "iter < N" --> F5
    F6D -- "iter >= N" --> H1

    H1 --> H2
    H2 --> H3
    H2 --> H4
    H3 --> H5
    H4 --> H5

    %% [NEW v4] MEPIC caching layer integrated into LLM serving
    H1 --> H11A
    H11A --> H11B
    H11B --> H2

    %% [NEW v4] Speculative generation loop
    H5 --> H10A
    H10A --> H10B
    H10B --> H10C
    H10C -- "Accepted" --> H6
    H10C -- "Rejected" --> H10D
    H10D --> H6

    %% Agentic self-correction loop
    H5 --> H9A
    H9A -- "Grounded" --> H10A
    H9A -- "Not grounded" --> H9B
    H9B --> H9C
    H9C -.-> F3

    H6 --> H7
    H7 --> H8

    %% =========================================================
    %% SEMANTIC LAYER USED ALSO ONLINE
    %% =========================================================

    C1 -.-> F4
    C3 -.-> F4
    C4 -.-> F4
    C5 -.-> G5
    C6 -.-> G4
    C6 -.-> H1

    %% Multimodal KG feeds semantic layer
    E9 -.-> C6

    %% =========================================================
    %% GOVERNANCE CONNECTIONS
    %% =========================================================

    I1 -.-> B1
    I1 -.-> F1
    I2 -.-> E6
    I3 -.-> G6
    I3 -.-> F6A
    I4 -.-> H8
    I5 -.-> I6
    I5 -.-> E2
    I6 -.-> C7
    I6 -.-> C1
    I6 -.-> C3
    I6 -.-> C5
    I6 -.-> C6
    I7 -.-> F6F
    I7 -.-> F6G
    I7 -.-> B8
    I7 -.-> H2
    I8 -.-> F5
    I8 -.-> G6
    I8 -.-> D5

    %% =========================================================
    %% SELF-AWARE EMBEDDING LIFECYCLE (SmartVector + QuOTE)
    %% confidence decay background agent
    %% =========================================================

    E2 -.-> I3
    I5 -.-> D6

    %% =========================================================
    %% COLORS - MACRO AREAS
    %% =========================================================

    classDef dataSources fill:#E3F2FD,stroke:#1565C0,stroke-width:2px,color:#0D1B2A;
    classDef dataSourcesNew fill:#BBDEFB,stroke:#0D47A1,stroke-width:3px,color:#0D1B2A;
    classDef ingestion fill:#E8F5E9,stroke:#2E7D32,stroke-width:2px,color:#0D1B2A;
    classDef ingestionNew fill:#C8E6C9,stroke:#1B5E20,stroke-width:3px,color:#0D1B2A;
    classDef semantic fill:#FFF3E0,stroke:#EF6C00,stroke-width:2px,color:#0D1B2A;
    classDef semanticNew fill:#FFE0B2,stroke:#BF360C,stroke-width:3px,color:#0D1B2A;
    classDef processing fill:#F3E5F5,stroke:#6A1B9A,stroke-width:2px,color:#0D1B2A;
    classDef processingNew fill:#E1BEE7,stroke:#4A148C,stroke-width:3px,color:#0D1B2A;
    classDef storage fill:#ECEFF1,stroke:#455A64,stroke-width:2px,color:#0D1B2A;
    classDef storageNew fill:#CFD8DC,stroke:#263238,stroke-width:3px,color:#0D1B2A;
    classDef storageV4 fill:#B0BEC5,stroke:#102027,stroke-width:3px,color:#0D1B2A;
    classDef query fill:#E0F7FA,stroke:#00838F,stroke-width:2px,color:#0D1B2A;
    classDef iterative fill:#E8EAF6,stroke:#283593,stroke-width:2px,color:#0D1B2A;
    classDef iterativeNew fill:#C5CAE9,stroke:#1A237E,stroke-width:3px,color:#0D1B2A;
    classDef iterativeV4 fill:#9FA8DA,stroke:#0D1B6E,stroke-width:3px,color:#0D1B2A;
    classDef retrieval fill:#FCE4EC,stroke:#AD1457,stroke-width:2px,color:#0D1B2A;
    classDef retrievalNew fill:#F8BBD9,stroke:#880E4F,stroke-width:3px,color:#0D1B2A;
    classDef retrievalV4 fill:#F48FB1,stroke:#560027,stroke-width:3px,color:#0D1B2A;
    classDef generation fill:#EDE7F6,stroke:#4527A0,stroke-width:2px,color:#0D1B2A;
    classDef generationNew fill:#D1C4E9,stroke:#311B92,stroke-width:3px,color:#0D1B2A;
    classDef generationV4 fill:#B39DDB,stroke:#1A0050,stroke-width:3px,color:#0D1B2A;
    classDef agentic fill:#F9FBE7,stroke:#827717,stroke-width:2px,color:#0D1B2A;
    classDef agenticV4 fill:#F0F4C3,stroke:#524C00,stroke-width:3px,color:#0D1B2A;
    classDef speculative fill:#FFF8E1,stroke:#F57F17,stroke-width:3px,color:#0D1B2A;
    classDef speculativeV4 fill:#FFE082,stroke:#E65100,stroke-width:3px,color:#0D1B2A;
    classDef governance fill:#FFEBEE,stroke:#C62828,stroke-width:2px,color:#0D1B2A;
    classDef governanceNew fill:#FFCDD2,stroke:#B71C1C,stroke-width:3px,color:#0D1B2A;
    classDef governanceV4 fill:#EF9A9A,stroke:#7F0000,stroke-width:3px,color:#0D1B2A;
    classDef serving fill:#E8F5E9,stroke:#1B5E20,stroke-width:3px,color:#0D1B2A;

    class A1,A2,A3 dataSources;
    class A4 dataSourcesNew;
    class B1,B2,B3,B4,B5,B6,B7,B8,B9 ingestion;
    class B10 ingestionNew;
    class C1,C2,C3,C4,C5,C6 semantic;
    class C7 semanticNew;
    class D1,D2,D3,D4,D5 processing;
    class D6 processingNew;
    class D7 processingNew;
    class E1,E2,E3,E4 storage;
    class E5,E6,E7 storageNew;
    class E8,E9 storageV4;
    class F1,F2,F3,F4,F5 query;
    class F6A,F6B,F6C,F6D,F6E iterative;
    class F6F iterativeNew;
    class F6G,F6H iterativeV4;
    class G1,G2,G3,G4,G5 retrieval;
    class G6,G7 retrievalNew;
    class G8,G9 retrievalV4;
    class H1,H3,H4,H5,H6,H7,H8 generation;
    class H2 generationNew;
    class H9A,H9B,H9C agentic;
    class H10A,H10B,H10C,H10D speculative;
    class H11A,H11B serving;
    class I1,I2,I3,I4,I5,I6 governance;
    class I7 governanceNew;
    class I8 governanceV4;
