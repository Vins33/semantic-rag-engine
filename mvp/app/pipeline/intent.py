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

Fase 1: regex leggera (sincrona, < 1ms).
Fase 2 (async): se query è di lunghezza media e non matchata, fallback LLM.
"""

import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

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


# ── LLM-based fallback for ambiguous queries (async) ─────────────────────────

_LLM_INTENT_PROMPT = """\
Classifica la seguente QUERY in una di queste categorie:
  "trivial"  — saluto, domanda meta (chi sei, cosa puoi fare), ringraziamento
  "simple"   — domanda fattuale diretta su un singolo concetto
  "complex"  — confronto, riassunto, analisi multi-step, lista esaustiva

Rispondi SOLO con un JSON nel formato:
{{"complexity": "<trivial|simple|complex>", "tags": ["tag1","tag2"], "reason": "<max 10 parole>"}}

QUERY: {query}
JSON:"""


async def analyze_intent_async(query: str) -> IntentResult:
    """
    Analisi intent con fallback LLM per query di lunghezza media (8-15 parole)
    che la regex non classifica come complex ma potrebbero esserlo.
    Per query corte o chiaramente classificate, usa il risultato sincrono direttamente.
    """
    sync_result = analyze_intent(query)

    # Non invocare LLM per triviali o query già classificate complex
    if not sync_result.retrieval_needed or sync_result.complexity == "complex":
        return sync_result

    word_count = len(query.strip().split())
    # LLM fallback solo per query di lunghezza intermedia (ambigua per regex)
    if word_count < 5 or word_count > 20:
        return sync_result

    try:
        from app.core import ollama
        raw = await ollama.generate(
            _LLM_INTENT_PROMPT.format(query=query),
            num_predict=128,
            num_ctx=512,
        )
        import json
        import re as _re
        m = _re.search(r'\{[^{}]*"complexity"[^{}]*\}', raw, _re.DOTALL)
        if m:
            obj = json.loads(m.group())
            complexity = obj.get("complexity", "simple")
            if complexity not in ("trivial", "simple", "complex"):
                complexity = "simple"
            tags = [str(t) for t in obj.get("tags", [])]
            multiplier = 1.5 if complexity == "complex" else 1.0
            logger.debug("LLM intent: %s → %s", query[:60], complexity)
            return IntentResult(
                retrieval_needed=complexity != "trivial",
                complexity=complexity,
                direct_answer=sync_result.direct_answer,
                intent_tags=tags or sync_result.intent_tags,
                top_k_multiplier=multiplier,
            )
    except Exception as exc:
        logger.debug("LLM intent fallback failed: %s", exc)

    return sync_result
