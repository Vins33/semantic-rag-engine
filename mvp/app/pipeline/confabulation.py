"""
G7B — Confabulation Guard

Verifica che la risposta generata dal LLM non contenga affermazioni
non supportate dall'evidenza recuperata.

Differenza rispetto a H3 (grounding check):
  - H3 (grounding): overlap lessicale frase → contesto  (veloce, recall-oriented)
  - G7B (confabulation): rileva pattern specifici di allucinazione (precision-oriented)
    * Numeri/date/nomi propri nella risposta non presenti nel contesto
    * Frasi di certezza su fatti non riscontrabili nel contesto
    * Citazioni di documenti non presenti nelle fonti recuperate

Output: ConfabulationResult con:
  - has_confabulation: bool
  - confidence: float  (0=molto confabulato, 1=totalmente grounded)
  - flags: list[str]   (descrizioni specifiche dei problemi trovati)
  - filtered_answer: str  (risposta con warning se confabulation rilevata)
"""

import re
from dataclasses import dataclass, field

# ── Pattern di allucinazione tipici ──────────────────────────────────────────

# Frasi di hyper-certezza che i LLM usano quando allucinano
_CERTAINTY_PHRASES: list[re.Pattern] = [
    re.compile(r"\bsicuramente\b", re.I),
    re.compile(r"\bè certo che\b", re.I),
    re.compile(r"\bè noto che\b", re.I),
    re.compile(r"\bcome è ampiamente (noto|riconosciuto)\b", re.I),
    re.compile(r"\btutti sanno che\b", re.I),
    re.compile(r"\bit is (well[ -]known|certain|obvious) that\b", re.I),
    re.compile(r"\beveryone knows\b", re.I),
    re.compile(r"\bobviously\b", re.I),
    re.compile(r"\bclearly,\b", re.I),
]

# Pattern per numeri e percentuali specifici nella risposta
_NUMBER_PATTERN = re.compile(r"\b\d+(?:[.,]\d+)?(?:\s*%|\s*GB|\s*MB|\s*ms|\s*sec)?\b")

# Pattern per anni
_YEAR_PATTERN = re.compile(r"\b(19|20)\d{2}\b")

# Pattern citazioni inventate (es. "[Autore, 2024]" non nel contesto)
_CITATION_PATTERN = re.compile(r"\[([A-Z][a-zA-Z]+(?:\s+et\s+al\.?)?,?\s*\d{4})\]")

# Frasi di disclaimer che indicano il LLM non ha trovato le info nel contesto
_HALLUCINATION_DISCLAIMERS: list[re.Pattern] = [
    re.compile(r"non ho informazioni\b", re.I),
    re.compile(r"non posso rispondere\b", re.I),
    re.compile(r"non è presente nel contesto\b", re.I),
    re.compile(r"fuori dal (mio )?dominio\b", re.I),
    re.compile(r"I don't have (enough |any )?information\b", re.I),
    re.compile(r"not (mentioned|found|present) in (the )?context\b", re.I),
]


@dataclass
class ConfabulationResult:
    has_confabulation: bool
    confidence: float           # 0.0 = molto confabulato, 1.0 = totalmente grounded
    flags: list[str] = field(default_factory=list)
    filtered_answer: str = ""


def check_confabulation(answer: str, context_chunks: list[str]) -> ConfabulationResult:
    """
    Analisi sincrona — nessuna chiamata LLM.
    
    Args:
        answer: risposta generata dal LLM
        context_chunks: lista di testi dei chunk usati come contesto
    
    Returns:
        ConfabulationResult
    """
    flags: list[str] = []
    penalties: float = 0.0

    full_context = " ".join(context_chunks).lower()
    answer_lower = answer.lower()

    # 1. Il LLM ha dichiarato di non avere informazioni → ottimo segno, non è confabulation
    for pat in _HALLUCINATION_DISCLAIMERS:
        if pat.search(answer):
            return ConfabulationResult(
                has_confabulation=False,
                confidence=1.0,
                flags=["model_correctly_abstained"],
                filtered_answer=answer,
            )

    # 2. Frasi di hyper-certezza su fatti non verificabili
    certainty_hits = [pat.pattern for pat in _CERTAINTY_PHRASES if pat.search(answer)]
    if certainty_hits:
        flags.append(f"hyper-certainty phrases detected ({len(certainty_hits)})")
        penalties += 0.1 * len(certainty_hits)

    # 3. Numeri specifici nella risposta — verifica presenza nel contesto
    # Ignora numeri ≤ 4 cifre che sono spesso anni/ID nei filename e non fanno parte di affermazioni fattuali
    answer_numbers = set(_NUMBER_PATTERN.findall(answer))
    missing_numbers: list[str] = []
    for num in answer_numbers:
        num_clean = re.sub(r"\s+", "", num)
        # Salta numeri brevi senza unità di misura (es. "31", "2501" da arxiv ID)
        if re.match(r"^\d{1,4}$", num_clean):
            continue
        if num_clean not in re.sub(r"\s+", "", full_context):
            missing_numbers.append(num)
    if missing_numbers:
        flags.append(f"numbers not in context: {missing_numbers[:5]}")
        penalties += 0.15 * min(len(missing_numbers), 4)

    # 4. Anni specifici — verifica nel contesto
    answer_years = set(_YEAR_PATTERN.findall(answer))
    missing_years = [y for y in answer_years if y not in full_context]
    if missing_years:
        flags.append(f"years not in context: {missing_years[:3]}")
        penalties += 0.1 * min(len(missing_years), 3)

    # 5. Citazioni nel formato [Autore, Anno] — verifica nel contesto
    citations = _CITATION_PATTERN.findall(answer)
    missing_citations: list[str] = []
    for cite in citations:
        # Estrai cognome autore
        author = cite.split(",")[0].split("et al")[0].strip().lower()
        if author not in full_context:
            missing_citations.append(cite)
    if missing_citations:
        flags.append(f"citations not in context: {missing_citations[:3]}")
        penalties += 0.2 * min(len(missing_citations), 3)

    # 6. Calcola confidence score
    confidence = max(0.0, 1.0 - penalties)
    has_confabulation = confidence < 0.6

    # 7. Prepara risposta filtrata con warning se necessario
    if has_confabulation:
        warning = (
            "\n\n⚠️ **Attenzione:** Alcune affermazioni in questa risposta potrebbero non essere "
            "completamente supportate dai documenti recuperati. Verifica le fonti citate."
        )
        filtered_answer = answer + warning
    else:
        filtered_answer = answer

    return ConfabulationResult(
        has_confabulation=has_confabulation,
        confidence=round(confidence, 3),
        flags=flags,
        filtered_answer=filtered_answer,
    )
