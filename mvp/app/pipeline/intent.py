"""
F2 — Intent + Complexity Gate (ispirato a SURE-RAG, arXiv 2605.03534)

Decide se il retrieval è necessario e classifica la complessità della query.

Logica:
  - Query triviale/saluto/metadato di sistema → risposta diretta senza retrieval
  - Query fattuale semplice (single-hop) → retrieval standard
  - Query complessa (confronto, riepilogo, multi-hop) → retrieval esteso (top_k aumentato)

Output: IntentResult con campi:
  - retrieval_needed: bool
  - complexity: "trivial" | "simple" | "complex"
  - direct_answer: str | None   (solo se retrieval_needed=False)
  - intent_tags: list[str]
"""

import re
from dataclasses import dataclass, field

# ── Patterns per bypass retrieval ─────────────────────────────────────────────

_TRIVIAL_PATTERNS: list[re.Pattern] = [
    re.compile(r"^\s*(ciao|hello|hi|salve|buongiorno|buonasera)\s*[!?.]?\s*$", re.I),
    re.compile(r"^\s*come stai\??", re.I),
    re.compile(r"^\s*chi sei\??", re.I),
    re.compile(r"^\s*cosa (puoi fare|sai fare)\??", re.I),
    re.compile(r"^\s*aiuto\s*$", re.I),
    re.compile(r"^\s*help\s*$", re.I),
    re.compile(r"^\s*grazie\s*[!.]?\s*$", re.I),
    re.compile(r"^\s*ok\s*$", re.I),
]

_TRIVIAL_DIRECT_ANSWERS: dict[str, str] = {
    "ciao":        "Ciao! Sono il Semantic RAG Engine. Puoi farmi domande sui documenti indicizzati.",
    "hello":       "Hello! I'm the Semantic RAG Engine. Ask me anything about the indexed documents.",
    "hi":          "Hi! Ask me anything about the indexed documents.",
    "salve":       "Salve! Puoi farmi domande sui documenti indicizzati.",
    "chi sei":     "Sono un sistema RAG (Retrieval-Augmented Generation) specializzato nell'analisi di documenti PDF tecnici e accademici.",
    "cosa puoi fare": "Posso rispondere a domande sui documenti indicizzati, citando le fonti precise (documento e pagina).",
    "grazie":      "Prego! Se hai altre domande, sono qui.",
}

# ── Patterns per classificazione complessità ──────────────────────────────────

_COMPLEX_PATTERNS: list[re.Pattern] = [
    re.compile(r"\b(confronta|compara|differenz[ae]|vs\.?|versus)\b", re.I),
    re.compile(r"\b(riassumi|riassunto|sintesi|sommario|overview)\b", re.I),
    re.compile(r"\b(elenca|lista|tutt[ie]|ogni|enumerate)\b", re.I),
    re.compile(r"\b(perché|ragioni|cause|motivi|spieg[a-z]+)\b", re.I),
    re.compile(r"\b(multi.hop|multi.step|passo per passo|step by step)\b", re.I),
    re.compile(r"\b(relazione tra|come si collega|in che modo)\b", re.I),
    re.compile(r"\b(compare|comparison|summarize|summarise|overview|differences?)\b", re.I),
    re.compile(r"\b(pros? and cons?|vantaggi e svantaggi)\b", re.I),
]

_INTENT_TAGS_MAP: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\b(definiz|cos'è|what is|define)\b", re.I),       "definition"),
    (re.compile(r"\b(come funzion|how does|how to)\b", re.I),        "how-to"),
    (re.compile(r"\b(confronta|compare|differenz)\b", re.I),         "comparison"),
    (re.compile(r"\b(riassumi|summarize|overview)\b", re.I),         "summary"),
    (re.compile(r"\b(esempio|example|es\.|e\.g\.)\b", re.I),         "example"),
    (re.compile(r"\b(autore|author|chi ha scritto|who wrote)\b", re.I), "metadata"),
    (re.compile(r"\b(quando|anno|year|date|data)\b", re.I),           "temporal"),
    (re.compile(r"\b(perché|why|ragion[ei])\b", re.I),               "causal"),
]


# ── Dataclass risultato ────────────────────────────────────────────────────────

@dataclass
class IntentResult:
    retrieval_needed: bool
    complexity: str                   # "trivial" | "simple" | "complex"
    direct_answer: str | None = None  # presente solo se retrieval_needed=False
    intent_tags: list[str] = field(default_factory=list)
    top_k_multiplier: float = 1.0     # 1.0 normal, 1.5 complex, 0 trivial


# ── Funzione principale ───────────────────────────────────────────────────────

def analyze_intent(query: str) -> IntentResult:
    """
    Analisi sincrona e leggera dell'intent — nessuna chiamata LLM.
    Basata su pattern matching; latenza < 1ms.
    """
    q_stripped = query.strip()

    # 1. Check triviale
    for pat in _TRIVIAL_PATTERNS:
        if pat.match(q_stripped):
            # Cerca risposta diretta
            direct = None
            for key, ans in _TRIVIAL_DIRECT_ANSWERS.items():
                if key in q_stripped.lower():
                    direct = ans
                    break
            if direct is None:
                direct = "Sono il Semantic RAG Engine. Puoi farmi domande sui documenti indicizzati."
            return IntentResult(
                retrieval_needed=False,
                complexity="trivial",
                direct_answer=direct,
                intent_tags=["greeting"],
                top_k_multiplier=0.0,
            )

    # 2. Estrai intent tags
    tags: list[str] = []
    for pat, tag in _INTENT_TAGS_MAP:
        if pat.search(q_stripped):
            tags.append(tag)

    # 3. Classifica complessità
    is_complex = any(pat.search(q_stripped) for pat in _COMPLEX_PATTERNS)
    # Heuristica aggiuntiva: query lunghe (> 15 parole) tendono a essere complesse
    word_count = len(q_stripped.split())
    if word_count > 15:
        is_complex = True

    if is_complex:
        return IntentResult(
            retrieval_needed=True,
            complexity="complex",
            intent_tags=tags or ["general"],
            top_k_multiplier=1.5,   # aumenta top_k del 50% per query complesse
        )

    return IntentResult(
        retrieval_needed=True,
        complexity="simple",
        intent_tags=tags or ["general"],
        top_k_multiplier=1.0,
    )
