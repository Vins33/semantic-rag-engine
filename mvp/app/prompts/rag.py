"""
Prompts per il pipeline RAG core.

  RAG_ANSWER        → risposta finale al documento
  HYDE              → generazione documento ipotetico (HyDE)
  S2G               → valutatore sufficienza contesto (SURE-RAG)
  CONTROLLER_DECOMPOSE   → query decomposition (F6C)
  CONTROLLER_CONTRADICT  → rilevamento contraddizioni (F6D)
"""

RAG_ANSWER = """\
Sei un assistente esperto in analisi documentale.
Rispondi alla domanda basandoti ESCLUSIVAMENTE sul contesto fornito.
Se il contesto non contiene informazioni sufficienti, dichiaralo esplicitamente.
Rispondi in italiano. Sii conciso e preciso; cita documento e pagina.

CONTESTO:
{context}

DOMANDA: {query}

RISPOSTA:"""

HYDE = """\
Scrivi un breve paragrafo tecnico (80-120 parole) che risponde direttamente \
alla seguente domanda di ricerca. Usa terminologia accademica precisa. \
Non citare fonti esterne, scrivi solo il contenuto sostanziale della risposta.

Domanda: {query}

Paragrafo:"""

S2G_SUFFICIENCY = """\
Sei un valutatore di qualità per sistemi RAG.

Analizza se il CONTESTO fornito contiene informazioni sufficienti per rispondere correttamente alla DOMANDA.

DOMANDA: {query}

CONTESTO (primi 1500 caratteri):
{context_excerpt}

Rispondi SOLO con un JSON nel formato:
{{"score": <float 0.0-1.0>, "reason": "<breve motivazione in max 20 parole>"}}

Dove score=1.0 significa "contesto completamente sufficiente", score=0.0 significa "contesto irrilevante o assente".
JSON:"""

CONTROLLER_DECOMPOSE = """\
Sei un assistente specializzato in query decomposition per sistemi RAG.

Scomponi la seguente DOMANDA in 2-3 sotto-query più semplici e specifiche,
ciascuna focalizzata su un aspetto distinto.

DOMANDA: {query}

Rispondi SOLO con una lista JSON di stringhe:
["sotto-query 1", "sotto-query 2", "sotto-query 3 (opzionale)"]
Lista JSON:"""

CONTROLLER_CONTRADICT = """\
Analizza il seguente CONTESTO e individua eventuali affermazioni contraddittorie o inconsistenti tra loro.

CONTESTO:
{context}

Se ci sono contraddizioni, elencale brevemente (max 3). Se non ce ne sono, rispondi "nessuna contraddizione".
Rispondi in italiano in max 100 parole:"""
