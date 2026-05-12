#!/usr/bin/env python3
"""
pipeline.py — Infrastruttura di test per il Semantic RAG Engine
================================================================
Modulo di supporto condiviso da tutti i file di test in tests/.
NON è un file pytest: non contiene test né fixtures.

Contiene:
  • sys.path setup per import da mvp/
  • Classe Scenario + 5 scenari enterprise multi-regolamento
  • Funzioni metriche: precision_at_k, recall_at_k, mrr, ndcg_at_k,
    average_precision, faithfulness_proxy, cosine_sim
  • Costanti: CACHE_THRESHOLD, REFUSAL_RE

Scenari:
  S1  GDPR Data Breach Notification (72h to authority)
  S2  NIS2 Incident Reporting       (24h early warning + 72h detailed)
  S3  EU AI Act High-Risk Systems   (Art.9/13/14)
  S4  DORA ICT Incident Reporting   (4h + 72h + 1 month)
  S5  GDPR vs CCPA Rights           (erasure + portability cross-regulation)

Paper di riferimento:
  [RAGAS]          arXiv:2309.15217  Es et al. (2023)
  [RGB]            arXiv:2309.01431  Chen et al. (AAAI 2024)
  [ARES]           arXiv:2311.09476  Saad-Falcon et al. (NAACL 2024)
  [EnterpriseRAG]  arXiv:2605.05253  Sun et al. (2026)
  [BestPractices]  arXiv:2407.01219  Wang et al. (2024)
"""

import math
import re
import sys
from pathlib import Path
from typing import NamedTuple

# ── sys.path setup: permette `from app.* import …` nei test ──────────────────
_TESTS_PATH = Path(__file__).resolve().parent
_MVP_PATH   = _TESTS_PATH.parent.parent / "mvp"
for _p in (_TESTS_PATH, _MVP_PATH):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))


# ═══════════════════════════════════════════════════════════════════════════════
# SCENARI DI VALUTAZIONE
# Struttura uniforme: rank-1=rilevante, rank-2=rumore, rank-3=rilevante,
#                     rank-4=rumore, rank-5=rilevante → P@3=2/3, P@5=3/5,
#                     MRR=1.0, R@5=1.0 per tutti e 5 gli scenari.
# Ref: EnterpriseRAG-Bench arXiv:2605.05253 §3 (scenario taxonomy)
# ═══════════════════════════════════════════════════════════════════════════════

class Scenario(NamedTuple):
    """Scenario di retrieval con ground-truth per metriche P/R/MRR/NDCG."""
    id:        str
    name:      str
    query:     str
    retrieved: list        # lista ordinata di chunk_id recuperati
    relevant:  frozenset   # set di chunk_id ground-truth rilevanti
    context:   str         # contesto testuale per test di faithfulness


# ── S1: GDPR Data Breach Notification ─────────────────────────────────────────
S1_GDPR = Scenario(
    id="S1",
    name="GDPR Data Breach Notification",
    query="GDPR data breach notification deadline",
    retrieved=[
        "chunk_gdpr_33",   # ✓ Art. 33 — notifica entro 72 ore
        "chunk_nis2_23",   # ✗ NIS2, regolamento diverso
        "chunk_gdpr_5",    # ✓ Art. 5  — principi del trattamento
        "chunk_firewall",  # ✗ rumore tecnico
        "chunk_gdpr_83",   # ✓ Art. 83 — sanzioni
    ],
    relevant=frozenset({"chunk_gdpr_33", "chunk_gdpr_5", "chunk_gdpr_83"}),
    context=(
        "Il GDPR Art. 33 prevede la notifica di una violazione dei dati personali "
        "all'autorità di controllo entro 72 ore dalla scoperta della violazione. "
        "Il titolare del trattamento deve documentare tutte le violazioni dei dati. "
        "Le sanzioni previste dall'Art. 83 comma 5 possono arrivare fino al 4% "
        "del fatturato annuo globale dell'impresa."
    ),
)

# ── S2: NIS2 Incident Reporting ───────────────────────────────────────────────
S2_NIS2 = Scenario(
    id="S2",
    name="NIS2 Incident Reporting",
    query="NIS2 incident reporting obligations for essential entities",
    retrieved=[
        "chunk_nis2_art23",  # ✓ Art. 23 — tempistiche di notifica
        "chunk_gdpr_33",     # ✗ GDPR, regime diverso
        "chunk_nis2_art21",  # ✓ Art. 21 — misure di gestione del rischio
        "chunk_random_tech", # ✗ contenuto tecnico non rilevante
        "chunk_nis2_art20",  # ✓ Art. 20 — obblighi di governance
    ],
    relevant=frozenset({"chunk_nis2_art23", "chunk_nis2_art21", "chunk_nis2_art20"}),
    context=(
        "La Direttiva NIS2 Art. 23 prevede la notifica degli incidenti significativi "
        "all'autorità competente entro 24 ore (early warning) e entro 72 ore (notifica "
        "dettagliata). I soggetti essenziali e importanti devono implementare misure di "
        "gestione del rischio ai sensi dell'Art. 21. La notifica finale deve essere "
        "presentata entro un mese dall'incidente secondo Art. 23 comma 6. "
        "L'Art. 20 impone responsabilità di governance agli organi direttivi degli enti."
    ),
)

# ── S3: EU AI Act High-Risk Systems ───────────────────────────────────────────
S3_AIACT = Scenario(
    id="S3",
    name="EU AI Act High-Risk Systems",
    query="AI Act requirements for high-risk AI systems in healthcare",
    retrieved=[
        "chunk_aiact_art9",  # ✓ Art. 9  — sistema di gestione del rischio
        "chunk_gdpr_35",     # ✗ GDPR DPIA, correlato ma fuori scope
        "chunk_aiact_art13", # ✓ Art. 13 — obblighi di trasparenza
        "chunk_random_ml",   # ✗ rumore ML generico
        "chunk_aiact_art14", # ✓ Art. 14 — supervisione umana
    ],
    relevant=frozenset({"chunk_aiact_art9", "chunk_aiact_art13", "chunk_aiact_art14"}),
    context=(
        "Il Regolamento UE sull'IA (AI Act) classifica i sistemi di IA ad alto rischio "
        "all'Allegato III. L'Art. 9 richiede l'implementazione di un sistema di gestione "
        "del rischio per tutto il ciclo di vita del sistema di IA. L'Art. 13 impone "
        "obblighi di trasparenza e fornitura di informazioni agli utenti dei sistemi "
        "ad alto rischio. L'Art. 14 richiede la supervisione umana dei sistemi ad alto "
        "rischio per prevenire rischi per salute, sicurezza o diritti fondamentali."
    ),
)

# ── S4: DORA ICT Incident Reporting ───────────────────────────────────────────
S4_DORA = Scenario(
    id="S4",
    name="DORA ICT Incident Reporting",
    query="DORA ICT incident classification and reporting timelines",
    retrieved=[
        "chunk_dora_art17",  # ✓ Art. 17 — processo di classificazione
        "chunk_nis2_art23",  # ✗ NIS2, settore diverso
        "chunk_dora_art19",  # ✓ Art. 19 — notifica incidenti gravi
        "chunk_random_fin",  # ✗ rumore finanziario generico
        "chunk_dora_art18",  # ✓ Art. 18 — criteri incidente grave
    ],
    relevant=frozenset({"chunk_dora_art17", "chunk_dora_art19", "chunk_dora_art18"}),
    context=(
        "Il Regolamento DORA (Digital Operational Resilience Act) Art. 17 stabilisce "
        "il processo di classificazione degli incidenti ICT in base all'impatto operativo. "
        "L'Art. 18 definisce i criteri per classificare un incidente come grave, includendo "
        "impatto su clienti, controparte e mercato. L'Art. 19 impone la segnalazione degli "
        "incidenti gravi all'autorità competente entro 4 ore dalla classificazione iniziale, "
        "con un report intermedio entro 72 ore e report finale entro un mese dall'incidente."
    ),
)

# ── S5: GDPR vs CCPA Cross-Regulation Rights ──────────────────────────────────
S5_CCPA = Scenario(
    id="S5",
    name="GDPR vs CCPA Data Subject Rights",
    query="compare data subject rights under GDPR and CCPA",
    retrieved=[
        "chunk_gdpr_17",     # ✓ GDPR Art. 17 — diritto alla cancellazione
        "chunk_random_us",   # ✗ US law non rilevante
        "chunk_ccpa_1798",   # ✓ CCPA §1798.105 — right to delete
        "chunk_ccpa_optout", # ✗ CCPA opt-out (tangenziale)
        "chunk_gdpr_20",     # ✓ GDPR Art. 20 — portabilità dei dati
    ],
    relevant=frozenset({"chunk_gdpr_17", "chunk_ccpa_1798", "chunk_gdpr_20"}),
    context=(
        "Il GDPR Art. 17 garantisce il diritto alla cancellazione dei dati personali "
        "('diritto all'oblio'). Il GDPR Art. 20 riconosce il diritto alla portabilità "
        "dei dati in formato strutturato e leggibile da macchina. "
        "Il California Consumer Privacy Act (CCPA) sezione 1798.105 riconosce il diritto "
        "del consumatore a richiedere la cancellazione dei dati personali raccolti. "
        "Entrambe le normative prevedono eccezioni per obblighi legali e interesse pubblico."
    ),
)

ALL_SCENARIOS: list[Scenario] = [S1_GDPR, S2_NIS2, S3_AIACT, S4_DORA, S5_CCPA]


# ═══════════════════════════════════════════════════════════════════════════════
# FUNZIONI METRICHE
# ═══════════════════════════════════════════════════════════════════════════════

def precision_at_k(retrieved: list, relevant: frozenset, k: int) -> float:
    """Precision@K = |retrieved[:k] ∩ relevant| / k
    Ref: RAGAS arXiv:2309.15217 §3.2 — Context Precision"""
    return sum(1 for d in retrieved[:k] if d in relevant) / k


def recall_at_k(retrieved: list, relevant: frozenset, k: int) -> float:
    """Recall@K = |retrieved[:k] ∩ relevant| / |relevant|
    Ref: RAGAS arXiv:2309.15217 §3.2 — Context Recall"""
    if not relevant:
        return 0.0
    return sum(1 for d in retrieved[:k] if d in relevant) / len(relevant)


def mrr(retrieved: list, relevant: frozenset) -> float:
    """Mean Reciprocal Rank = 1 / rank_first_relevant  (0 se non trovato)
    Ref: ARES arXiv:2311.09476 §2 — retrieval ranking"""
    for rank, doc in enumerate(retrieved, start=1):
        if doc in relevant:
            return 1.0 / rank
    return 0.0


def ndcg_at_k(retrieved: list, relevant: frozenset, k: int) -> float:
    """NDCG@K con binary relevance. Formula: DCG / IDCG.
    Ref: RAGAS arXiv:2309.15217 §3.2"""
    dcg  = sum(1.0 / math.log2(r + 2) for r, d in enumerate(retrieved[:k]) if d in relevant)
    idcg = sum(1.0 / math.log2(r + 2) for r in range(min(len(relevant), k)))
    return dcg / idcg if idcg > 0 else 0.0


def average_precision(retrieved: list, relevant: frozenset) -> float:
    """Average Precision = Σ P@k·rel(k) / |relevant|
    Ref: RGB arXiv:2309.01431 §2 — MAP"""
    if not relevant:
        return 0.0
    hits, total = 0, 0.0
    for rank, doc in enumerate(retrieved, start=1):
        if doc in relevant:
            hits  += 1
            total += hits / rank
    return total / len(relevant)


def faithfulness_proxy(answer: str, context: str) -> float:
    """Faithfulness proxy senza LLM: frazione di frasi dell'answer che
    condividono almeno un trigramma con il context.
    Approssima l'LLM-judge di RAGAS §3.1 (arXiv:2309.15217).
    Target operativo: ≥ 0.90."""
    sentences = [s.strip() for s in re.split(r"[.!?]", answer) if len(s.strip()) > 10]
    if not sentences:
        return 1.0
    ctx_lower = context.lower()

    def _has_trigram(sent: str) -> bool:
        words = sent.lower().split()
        if len(words) < 3:
            return any(w in ctx_lower for w in words if len(w) > 3)
        return any(" ".join(words[i:i+3]) in ctx_lower for i in range(len(words) - 2))

    return sum(1 for s in sentences if _has_trigram(s)) / len(sentences)


def cosine_sim(v1: list, v2: list) -> float:
    """Cosine similarity tra due vettori (implementazione pura Python)."""
    dot   = sum(a * b for a, b in zip(v1, v2))
    norm1 = math.sqrt(sum(a * a for a in v1))
    norm2 = math.sqrt(sum(b * b for b in v2))
    return dot / (norm1 * norm2) if norm1 and norm2 else 0.0


# ── Costanti condivise ────────────────────────────────────────────────────────
CACHE_THRESHOLD = 0.92   # F5B semantic cache cosine threshold
                          # Ref: BestPractices arXiv:2407.01219 §3.3

REFUSAL_RE = re.compile(
    r"non (?:ho|trovo|posso|sono in grado|ho informazioni)|"
    r"non è (?:possibile|disponibile|presente|chiaro)|"
    r"non (?:sono sicuro|ho dati sufficienti)|"
    r"insufficient|not enough|cannot answer|"
    r"I (?:don.t know|cannot|do not have)|"
    r"not (?:found|available|present|mentioned)",
    re.I,
)
# Ref: RGB arXiv:2309.01431 §3.1 Testbed 2 — Negative Rejection
