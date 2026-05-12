flowchart TD

    %% =========================================================
    %% MACRO AREA 1 - DATA SOURCES
    %% =========================================================

    subgraph A0["1. DATA SOURCES"]
        A1["Document Repositories<br/>PDF, DOCX, HTML, Markdown"]
        A2["Structured Sources<br/>CSV, SQL DB, Data Lake"]
        A3["Enterprise Sources<br/>SharePoint, Confluence, Git, Wiki"]
    end

    %% =========================================================
    %% MACRO AREA 2 - OFFLINE INGESTION PIPELINE
    %% =========================================================

    subgraph B0["2. OFFLINE INGESTION PIPELINE"]
        B1["Connectors"]
        B2["Document Loading"]
        B3["Parsing"]
        B4["OCR if needed"]
        B5["Cleaning"]
        B6["Layout Analysis"]
        B7["Table Extraction"]
        B8["Source Provenance"]
        B9["Document Versioning"]
    end

    %% =========================================================
    %% MACRO AREA 3 - SEMANTIC LAYER
    %% =========================================================

    subgraph C0["3. SEMANTIC LAYER / ONTOLOGY PIPELINE"]
        C1["Controlled Vocabulary<br/>allowed terms, aliases, acronyms"]
        C2["Metadata Standards<br/>schemas, required fields, document types"]
        C3["Taxonomy<br/>hierarchies, parent-child relations"]
        C4["Thesaurus<br/>synonyms, related terms, broader/narrower terms"]
        C5["Ontology<br/>classes, properties, relations, constraints"]
        C6["Knowledge Graph<br/>entities, relations, provenance"]
    end

    %% =========================================================
    %% MACRO AREA 4 - DOCUMENT PROCESSING
    %% =========================================================

    subgraph D0["4. DOCUMENT PROCESSING"]
        D1["Entity Extraction"]
        D2["Relation Extraction"]
        D3["Domain Classification"]
        D4["Metadata Enrichment"]
        D5["Semantic Chunking"]
        D6["Embedding Generation"]
    end

    %% =========================================================
    %% MACRO AREA 5 - STORAGE AND INDEXING
    %% =========================================================

    subgraph E0["5. STORAGE AND INDEXING"]
        E1["Object Storage<br/>raw documents, parsed artifacts"]
        E2["Vector DB<br/>Qdrant, Milvus, Weaviate"]
        E3["Keyword Index<br/>OpenSearch, Elasticsearch, BM25"]
        E4["Metadata Store<br/>PostgreSQL"]
        E5["Graph DB<br/>Neo4j, RDF Store"]
        E6["Audit Log Store"]
    end

    %% =========================================================
    %% MACRO AREA 6 - ONLINE QUERY PIPELINE
    %% =========================================================

    subgraph F0["6. ONLINE QUERY PIPELINE"]
        F1["User Query"]
        F2["Intent Detection"]
        F3["Query Rewriting"]
        F4["Query Expansion<br/>via vocabulary, taxonomy, thesaurus"]
        F5["Retrieval Routing"]
    end

    %% =========================================================
    %% MACRO AREA 7 - RETRIEVAL AND RANKING
    %% =========================================================

    subgraph G0["7. HYBRID RETRIEVAL AND RANKING"]
        G1["Vector Retrieval"]
        G2["Keyword Retrieval"]
        G3["Metadata Filtering"]
        G4["Graph Traversal"]
        G5["Semantic Filtering"]
        G6["Reranking<br/>cross-encoder, LLM, rules"]
    end

    %% =========================================================
    %% MACRO AREA 8 - GENERATION AND VALIDATION
    %% =========================================================

    subgraph H0["8. GENERATION AND VALIDATION"]
        H1["Context Builder"]
        H2["LLM / Agent Layer"]
        H3["Tool Calling"]
        H4["Structured Output"]
        H5["Grounding Check"]
        H6["Citation Validation"]
        H7["Compliance Check"]
        H8["Final Answer<br/>answer, sources, metadata, confidence"]
    end

    %% =========================================================
    %% MACRO AREA 9 - GOVERNANCE AND FEEDBACK
    %% =========================================================

    subgraph I0["9. GOVERNANCE AND FEEDBACK"]
        I1["Access Control"]
        I2["Data Lineage"]
        I3["Monitoring"]
        I4["Evaluation Metrics"]
        I5["Human Feedback"]
        I6["Ontology Updates"]
    end

    %% =========================================================
    %% MAIN OFFLINE FLOW
    %% =========================================================

    A1 --> B1
    A2 --> B1
    A3 --> B1

    B1 --> B2
    B2 --> B3
    B3 --> B4
    B4 --> B5
    B5 --> B6
    B6 --> B7
    B7 --> B8
    B8 --> B9

    B9 --> D1
    D1 --> D2
    D2 --> D3
    D3 --> D4

    D4 --> C1
    C1 --> C2
    C2 --> C3
    C3 --> C4
    C4 --> C5
    C5 --> C6

    C6 --> D5
    D5 --> D6

    D6 --> E2
    D5 --> E3
    D4 --> E4
    C6 --> E5
    B9 --> E1
    B8 --> E6

    %% =========================================================
    %% MAIN ONLINE FLOW
    %% =========================================================

    F1 --> F2
    F2 --> F3
    F3 --> F4
    F4 --> F5

    F5 --> G1
    F5 --> G2
    F5 --> G3
    F5 --> G4

    E2 --> G1
    E3 --> G2
    E4 --> G3
    E5 --> G4

    G1 --> G5
    G2 --> G5
    G3 --> G5
    G4 --> G5
    G5 --> G6

    G6 --> H1
    H1 --> H2
    H2 --> H3
    H2 --> H4
    H3 --> H5
    H4 --> H5
    H5 --> H6
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

    %% =========================================================
    %% GOVERNANCE CONNECTIONS
    %% =========================================================

    I1 -.-> B1
    I2 -.-> E6
    I3 -.-> G6
    I4 -.-> H8
    I5 -.-> I6
    I6 -.-> C1
    I6 -.-> C3
    I6 -.-> C5
    I6 -.-> C6

    %% =========================================================
    %% COLORS - MACRO AREAS
    %% =========================================================

    classDef dataSources fill:#E3F2FD,stroke:#1565C0,stroke-width:2px,color:#0D1B2A;
    classDef ingestion fill:#E8F5E9,stroke:#2E7D32,stroke-width:2px,color:#0D1B2A;
    classDef semantic fill:#FFF3E0,stroke:#EF6C00,stroke-width:2px,color:#0D1B2A;
    classDef processing fill:#F3E5F5,stroke:#6A1B9A,stroke-width:2px,color:#0D1B2A;
    classDef storage fill:#ECEFF1,stroke:#455A64,stroke-width:2px,color:#0D1B2A;
    classDef query fill:#E0F7FA,stroke:#00838F,stroke-width:2px,color:#0D1B2A;
    classDef retrieval fill:#FCE4EC,stroke:#AD1457,stroke-width:2px,color:#0D1B2A;
    classDef generation fill:#EDE7F6,stroke:#4527A0,stroke-width:2px,color:#0D1B2A;
    classDef governance fill:#FFEBEE,stroke:#C62828,stroke-width:2px,color:#0D1B2A;

    class A1,A2,A3 dataSources;
    class B1,B2,B3,B4,B5,B6,B7,B8,B9 ingestion;
    class C1,C2,C3,C4,C5,C6 semantic;
    class D1,D2,D3,D4,D5,D6 processing;
    class E1,E2,E3,E4,E5,E6 storage;
    class F1,F2,F3,F4,F5 query;
    class G1,G2,G3,G4,G5,G6 retrieval;
    class H1,H2,H3,H4,H5,H6,H7,H8 generation;
    class I1,I2,I3,I4,I5,I6 governance;