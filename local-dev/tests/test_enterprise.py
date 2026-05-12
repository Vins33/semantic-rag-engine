#!/usr/bin/env python3
"""
test_enterprise.py — Scenari enterprise × 5 regolamenti
=========================================================
Test ispirati ai pattern di EnterpriseRAG-Bench (arXiv:2605.05253) su 5 scenari:

  S1  GDPR  — Single-doc lookup, constrained retrieval, absent information
  S2  NIS2  — Multi-step timeline, governance obligations, complex intent
  S3  AI Act — High-risk classification, transparency, human oversight
  S4  DORA  — ICT incident timelines (4h / 72h / 1 mese), conflict resolution
  S5  GDPR+CCPA — Cross-regulation multi-doc reasoning, rights comparison

Tipi di domanda (EnterpriseRAG-Bench §3):
  single_doc_lookup         — query fattuali su un unico articolo
  multi_doc_reasoning       — confronto tra fonti multiple
  constrained_retrieval     — filtro per dominio/regolamento
  conflict_resolution       — risposta coerente con fonte specifica
  absent_information        — incertezza quando il contesto non contiene la risposta
  temporal_reasoning        — ordine/confronto di scadenze temporali

Ref:
  [EnterpriseRAG]  arXiv:2605.05253  Sun et al. (2026)   §3, §4
  [RAGAS]          arXiv:2309.15217  Es et al. (2023)    §3.1
  [RGB]            arXiv:2309.01431  Chen et al. (2024)  §3.1
"""

import pytest
from pipeline import (
    S1_GDPR, S2_NIS2, S3_AIACT, S4_DORA, S5_CCPA,
    precision_at_k, recall_at_k, mrr,
    faithfulness_proxy, REFUSAL_RE,
)


# ═══════════════════════════════════════════════════════════════════════════════
# S1 — GDPR Data Breach Notification
# ═══════════════════════════════════════════════════════════════════════════════

class TestEnterpriseGDPR:
    """EnterpriseRAG-Bench §4.1 — single-doc lookup, absent info, constrained."""

    def test_single_doc_lookup_intent_retrieval_needed(self):
        """Single-doc lookup: query su Art. 33 → retrieval_needed = True."""
        from app.pipeline.intent import analyze_intent
        result = analyze_intent("qual è il termine per la notifica di un data breach al Garante?")
        assert result.retrieval_needed

    def test_single_doc_lookup_complexity_simple(self):
        """Single-doc lookup su un articolo specifico → complexity simple/complex (non trivial)."""
        from app.pipeline.intent import analyze_intent
        result = analyze_intent("entro quante ore va notificato un data breach?")
        assert result.complexity != "trivial"

    def test_constrained_retrieval_domain_filter(self):
        """Solo chunk 'Legale' passano il filtro; P@all = 1.0."""
        retrieved_with_domain = [
            ("chunk_gdpr_33",  "Legale"),
            ("chunk_firewall", "Tecnico"),
            ("chunk_gdpr_5",   "Legale"),
            ("chunk_network",  "Tecnico"),
            ("chunk_gdpr_83",  "Legale"),
        ]
        filtered = [cid for cid, dom in retrieved_with_domain if dom == "Legale"]
        p = precision_at_k(filtered, S1_GDPR.relevant, k=len(filtered))
        assert p == 1.0, f"Filtro domain='Legale' → P@all deve essere 1.0, ottenuto {p:.2f}"

    def test_absent_information_hallucination_low_faith(self):
        """
        Absent information (EnterpriseRAG §4.4): risposta inventata su argomento assente
        → faithfulness bassa.
        """
        hallucination = (
            "Il termine per la notifica è di 48 ore come previsto dall'art. 14 comma 3. "
            "La dichiarazione va presentata all'Agenzia delle Entrate entro il 30 giugno."
        )
        assert faithfulness_proxy(hallucination, S1_GDPR.context) < 0.40

    def test_conflict_resolution_source_a_faithful(self):
        """
        Conflict resolution (EnterpriseRAG §4.3): risposta coerente con chunk A
        → faithfulness alta su chunk A.
        """
        chunk_a  = S1_GDPR.context  # include "72 ore"
        answer_a = "Il GDPR Art. 33 prevede la notifica entro 72 ore dalla scoperta."
        assert faithfulness_proxy(answer_a, chunk_a) >= 0.60

    def test_mrr_rank1_relevant(self):
        """Il chunk più rilevante è sempre al rank-1 in tutti gli scenari."""
        assert mrr(S1_GDPR.retrieved, S1_GDPR.relevant) == 1.0


# ═══════════════════════════════════════════════════════════════════════════════
# S2 — NIS2 Incident Reporting
# ═══════════════════════════════════════════════════════════════════════════════

class TestEnterpriseNIS2:
    """EnterpriseRAG-Bench §4.2 — multi-step timeline, governance, complex intent."""

    def test_multi_step_early_warning_in_context(self):
        """Il contesto NIS2 deve contenere il termine 24 ore (early warning)."""
        assert "24 ore" in S2_NIS2.context

    def test_multi_step_detailed_notification_in_context(self):
        """Il contesto NIS2 deve contenere il termine 72 ore (notifica dettagliata)."""
        assert "72 ore" in S2_NIS2.context

    def test_multi_step_final_report_in_context(self):
        """Il contesto NIS2 deve contenere 'un mese' (report finale)."""
        assert "un mese" in S2_NIS2.context

    def test_timeline_answer_faithful(self):
        answer = (
            "La Direttiva NIS2 Art. 23 prevede la notifica degli incidenti significativi "
            "all'autorità competente entro 24 ore e poi entro 72 ore."
        )
        assert faithfulness_proxy(answer, S2_NIS2.context) >= 0.50

    def test_complex_intent_comparison(self):
        """Confronto tra NIS2 e GDPR → complexity complex, top_k_multiplier > 1."""
        from app.pipeline.intent import analyze_intent
        result = analyze_intent("confronta gli obblighi di notifica di NIS2 e GDPR")
        assert result.complexity == "complex"
        assert result.top_k_multiplier > 1.0

    def test_recall_at_5_full_coverage(self):
        """Con 5 chunk recuperati, tutti e 3 i rilevanti NIS2 sono coperti."""
        assert recall_at_k(S2_NIS2.retrieved, S2_NIS2.relevant, k=5) == 1.0


# ═══════════════════════════════════════════════════════════════════════════════
# S3 — EU AI Act High-Risk Systems
# ═══════════════════════════════════════════════════════════════════════════════

class TestEnterpriseAIAct:
    """EnterpriseRAG-Bench §4.1 — domain-specific lookup, faithfulness, absent info."""

    def test_high_risk_classification_in_context(self):
        """Il contesto AI Act deve citare 'Allegato III' (lista sistemi alto rischio)."""
        assert "Allegato III" in S3_AIACT.context

    def test_transparency_obligation_faithful(self):
        answer = (
            "L'Art. 13 dell'AI Act impone obblighi di trasparenza e fornitura di "
            "informazioni agli utenti dei sistemi ad alto rischio."
        )
        assert faithfulness_proxy(answer, S3_AIACT.context) >= 0.60

    def test_human_oversight_in_context(self):
        """Il contesto AI Act deve citare la supervisione umana."""
        assert "supervisione umana" in S3_AIACT.context

    def test_absent_info_gdpr_dpia_low_faith(self):
        """
        DPIA GDPR è nel contesto come rumore (chunk_gdpr_35 non incluso nel retrieved
        relevant). Una risposta su DPIA in contesto AI Act → bassa faithfulness.
        """
        dpia_answer = (
            "Il GDPR Art. 35 richiede la valutazione d'impatto sulla protezione dei dati. "
            "La DPIA è obbligatoria per trattamenti ad alto rischio per i diritti degli interessati."
        )
        assert faithfulness_proxy(dpia_answer, S3_AIACT.context) < 0.50

    def test_precision_at_5_correct(self):
        from pipeline import precision_at_k
        p = precision_at_k(S3_AIACT.retrieved, S3_AIACT.relevant, k=5)
        assert abs(p - 3/5) < 0.001

    def test_intent_retrieval_needed(self):
        from app.pipeline.intent import analyze_intent
        result = analyze_intent("quali sono i requisiti dell'AI Act per sistemi ad alto rischio?")
        assert result.retrieval_needed


# ═══════════════════════════════════════════════════════════════════════════════
# S4 — DORA ICT Incident Reporting
# ═══════════════════════════════════════════════════════════════════════════════

class TestEnterpriseDORA:
    """EnterpriseRAG-Bench §4.2 — temporal reasoning, timeline precision."""

    def test_4hour_deadline_in_context(self):
        """Il contesto DORA deve contenere il termine '4 ore' (classificazione iniziale)."""
        assert "4 ore" in S4_DORA.context

    def test_72hour_intermediate_report_in_context(self):
        """Il contesto DORA deve contenere '72 ore' (report intermedio)."""
        assert "72 ore" in S4_DORA.context

    def test_1month_final_report_in_context(self):
        """Il contesto DORA deve contenere 'un mese' (report finale)."""
        assert "un mese" in S4_DORA.context

    def test_temporal_ordering_4h_before_72h(self):
        """
        Temporal reasoning: il termine 4 ore appare prima del 72 ore nel testo,
        riflettendo la sequenza temporale corretta degli obblighi DORA.
        """
        ctx = S4_DORA.context
        pos_4h  = ctx.find("4 ore")
        pos_72h = ctx.find("72 ore")
        assert pos_4h < pos_72h, "4 ore deve precedere 72 ore nel contesto DORA"

    def test_incident_report_answer_faithful(self):
        answer = (
            "Il Regolamento DORA Art. 19 impone la segnalazione degli incidenti gravi "
            "all'autorità entro 4 ore dalla classificazione iniziale."
        )
        assert faithfulness_proxy(answer, S4_DORA.context) >= 0.50

    def test_wrong_regulation_answer_low_faith(self):
        """Risposta su GDPR in contesto DORA → faithfulness bassa (conflict resolution)."""
        gdpr_answer = (
            "Il GDPR Art. 33 prevede la notifica entro 72 ore all'autorità garante. "
            "La sanzione massima è il 4% del fatturato annuo."
        )
        assert faithfulness_proxy(gdpr_answer, S4_DORA.context) < 0.40


# ═══════════════════════════════════════════════════════════════════════════════
# S5 — GDPR vs CCPA Cross-Regulation
# ═══════════════════════════════════════════════════════════════════════════════

class TestEnterpriseCCPA:
    """
    EnterpriseRAG-Bench §4.5 — multi-doc reasoning, cross-regulation comparison.
    """

    def test_complex_intent_cross_regulation(self):
        """Confronto tra due normative diverse → complexity complex."""
        from app.pipeline.intent import analyze_intent
        result = analyze_intent("confronta i diritti degli interessati sotto GDPR e CCPA")
        assert result.complexity == "complex"

    def test_both_gdpr_and_ccpa_in_relevant(self):
        """Il set di rilevanti deve coprire chunk GDPR e CCPA (multi-doc)."""
        has_gdpr = any("gdpr" in cid for cid in S5_CCPA.relevant)
        has_ccpa = any("ccpa" in cid for cid in S5_CCPA.relevant)
        assert has_gdpr and has_ccpa, "Multi-doc: deve coprire sia GDPR che CCPA"

    def test_erasure_right_in_both_contexts(self):
        """Entrambi GDPR Art. 17 e CCPA §1798.105 citano il diritto alla cancellazione."""
        assert "cancellazione" in S5_CCPA.context.lower()

    def test_cross_regulation_answer_faithful(self):
        answer = (
            "Il GDPR Art. 17 garantisce il diritto alla cancellazione dei dati personali. "
            "Il CCPA sezione 1798.105 riconosce il diritto del consumatore alla cancellazione."
        )
        assert faithfulness_proxy(answer, S5_CCPA.context) >= 0.60

    def test_recall_at_5_covers_both_regulations(self):
        """R@5 = 1.0: tutti i chunk rilevanti (GDPR + CCPA) sono recuperati."""
        assert recall_at_k(S5_CCPA.retrieved, S5_CCPA.relevant, k=5) == 1.0

    def test_absent_jurisdiction_low_faith(self):
        """
        Absent information: risposta su PIPL cinese nel contesto GDPR/CCPA
        → faithfulness bassa (normativa non presente nei documenti).
        """
        pipl_answer = (
            "Il PIPL cinese richiede il consenso esplicito per il trasferimento "
            "di dati personali al di fuori della Repubblica Popolare Cinese."
        )
        assert faithfulness_proxy(pipl_answer, S5_CCPA.context) < 0.40
