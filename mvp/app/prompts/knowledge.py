"""
Prompts per la knowledge extraction pipeline.

  NER            → Named Entity Recognition (D1)
  RELATION       → Relation Extraction (D2)
  METADATA       → arricchimento metadata documenti (ingest)
"""

NER = """\
You are a Named Entity Recognition (NER) system specialized in technical and academic documents.

Extract all named entities from the following text. For each entity return a JSON array.
Each element must have exactly these fields:
  "text"       : the exact surface text of the entity
  "type"       : one of [PERSON, ORGANIZATION, LOCATION, DATE, REGULATION, CONCEPT, AMOUNT, PRODUCT, METHOD, DATASET]
  "confidence" : a float 0.0-1.0

Rules:
- Only return entities explicitly present in the text
- Do NOT invent entities not in the text
- For CONCEPT: technical/scientific concepts (e.g. "Retrieval-Augmented Generation", "HNSW index")
- For METHOD: algorithms, techniques (e.g. "BM25", "cross-encoder reranking", "HyDE")
- For DATASET: named datasets or benchmarks (e.g. "MS MARCO", "BEIR", "TriviaQA")
- For REGULATION: laws, standards, norms (e.g. "GDPR", "NIS2", "ISO 27001")
- Minimum confidence 0.7 to include

Text:
\"\"\"
{text}
\"\"\"

Respond ONLY with a valid JSON array. No explanation, no markdown, just the array.
Example: [{{"text": "BERT", "type": "METHOD", "confidence": 0.95}}]
"""

RELATION = """\
You are a Relation Extraction (RE) system for technical and academic documents.

Given the text below and a list of known entities, extract semantic relations.
Return a JSON array where each element has:
  "subject"    : exact text of the subject entity
  "predicate"  : one of [defines, uses, improves, extends, contradicts, requires, produces, evaluates_on, part_of, related_to]
  "object"     : exact text of the object entity
  "confidence" : float 0.0-1.0

Rules:
- Both subject and object must be present in the text
- Only include relations with confidence >= 0.7
- Keep it factual, no inference beyond what the text states

Known entities: {entities}

Text:
\"\"\"
{text}
\"\"\"

Respond ONLY with a valid JSON array. No explanation.
Example: [{{"subject": "RAG", "predicate": "uses", "object": "BM25", "confidence": 0.9}}]
"""

METADATA_ENRICHMENT = """\
Analyze this academic paper and return ONLY a valid JSON object (no explanation, no markdown).

Filename: {filename}
Text excerpt (first ~1500 chars):
{excerpt}

Return exactly this JSON structure:
{{
  "domain": "<one of: rag_foundation|graph_rag|agentic_rag|embeddings_memory|indexing_retrieval|ontology_semantic|security|multimodal|survey|advanced_rag>",
  "doc_type": "<one of: research_paper|survey|technical_report>",
  "language": "<en|it|other>",
  "year": <integer year of publication, or null>,
  "topics": ["<keyword1>", "<keyword2>", "<keyword3>"]
}}

JSON:"""
