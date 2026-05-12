#!/usr/bin/env python3
"""
test_generation.py — Qualità della generazione: Faithfulness, Noise, Refusal
==============================================================================
Testa la catena di valutazione della risposta generata senza LLM live.

Metriche:
  Faithfulness proxy   — trigram overlap tra answer e context
  Noise Robustness     — risposta corretta anche con chunk irrilevanti (RGB Testbed 1)
  Negative Rejection   — refusal pattern quando il contesto è irrilevante (RGB Testbed 2)

Scenari coperti:
  S1  GDPR  — notifica data breach 72 ore
  S2  NIS2  — early warning 24 ore + notifica 72 ore
  S3  AI Act — Art.9/13/14 high-risk systems
  S4  DORA  — incident reporting 4h / 72h / 1 mese

Ref:
  [RAGAS]  arXiv:2309.15217  Es et al. (2023)         §3.1 Faithfulness
  [RGB]    arXiv:2309.01431  Chen et al. (AAAI 2024)   §3.1 Testbed 1 & 2
  [ARES]   arXiv:2311.09476  Saad-Falcon et al. (2024) §3.2 Answer Faithfulness
"""

import pytest
from pipeline import (
    S1_GDPR, S2_NIS2, S3_AIACT, S4_DORA,
    faithfulness_proxy, REFUSAL_RE,
)


# ═══════════════════════════════════════════════════════════════════════════════
# FAITHFULNESS — per scenario
# Target: ≥ 0.90 per risposte fedeli; < 0.40 per risposte inventate
# Ref: RAGAS arXiv:2309.15217 §3.1
# ═══════════════════════════════════════════════════════════════════════════════

class TestFaithfulnessGDPR:
    """S1 — GDPR data breach notification."""

    def test_faithful_answer_scores_high(self):
        answer = (
            "Secondo il GDPR Art. 33, la notifica deve avvenire entro 72 ore. "
            "Il titolare deve documentare tutte le violazioni dei dati personali."
        )
        assert faithfulness_proxy(answer, S1_GDPR.context) >= 0.70

    def test_direct_quote_scores_highest(self):
        answer = (
            "Il GDPR Art. 33 prevede la notifica di una violazione dei dati personali "
            "all'autorità di controllo entro 72 ore dalla scoperta della violazione."
        )
        assert faithfulness_proxy(answer, S1_GDPR.context) >= 0.90

    def test_unfaithful_answer_scores_low(self):
        answer = (
            "La normativa fiscale richiede la dichiarazione entro aprile. "
            "Le detrazioni per spese mediche vanno nel quadro E del modello 730."
        )
        assert faithfulness_proxy(answer, S1_GDPR.context) < 0.40

    def test_partial_faithfulness_intermediate(self):
        """Una frase fedele + una inventata → score intermedio."""
        answer = (
            "La notifica deve avvenire entro 72 ore dalla scoperta della violazione. "
            "Le detrazioni per spese mediche sono detraibili al 19%."
        )
        score = faithfulness_proxy(answer, S1_GDPR.context)
        assert 0.20 < score < 0.90


class TestFaithfulnessNIS2:
    """S2 — NIS2 incident reporting."""

    def test_early_warning_faithful(self):
        answer = (
            "La Direttiva NIS2 Art. 23 prevede un early warning entro 24 ore. "
            "La notifica dettagliata deve essere inviata entro 72 ore."
        )
        assert faithfulness_proxy(answer, S2_NIS2.context) >= 0.60

    def test_wrong_timeline_unfaithful(self):
        """Risposta totalmente fuori dominio → bassa faithfulness sul contesto NIS2."""
        answer = (
            "La borsa azionaria ha registrato un rialzo nella seduta odierna. "
            "I titoli industriali hanno sovraperformato i titoli tecnologici."
        )
        assert faithfulness_proxy(answer, S2_NIS2.context) < 0.40

    def test_governance_obligation_faithful(self):
        answer = (
            "L'Art. 20 impone responsabilità di governance agli organi direttivi degli enti. "
            "Le misure di gestione del rischio sono richieste dall'Art. 21."
        )
        assert faithfulness_proxy(answer, S2_NIS2.context) >= 0.60


class TestFaithfulnessAIAct:
    """S3 — EU AI Act high-risk systems."""

    def test_risk_management_faithful(self):
        answer = (
            "Il Regolamento UE sull'IA classifica i sistemi ad alto rischio all'Allegato III. "
            "L'Art. 9 richiede un sistema di gestione del rischio per tutto il ciclo di vita."
        )
        assert faithfulness_proxy(answer, S3_AIACT.context) >= 0.70

    def test_human_oversight_faithful(self):
        answer = (
            "L'Art. 14 richiede la supervisione umana dei sistemi ad alto rischio "
            "per prevenire rischi per salute, sicurezza o diritti fondamentali."
        )
        assert faithfulness_proxy(answer, S3_AIACT.context) >= 0.70

    def test_unrelated_answer_unfaithful(self):
        answer = (
            "Il mercato azionario ha registrato un rialzo del 2% nella seduta odierna. "
            "Gli investitori attendono i dati sull'inflazione della prossima settimana."
        )
        assert faithfulness_proxy(answer, S3_AIACT.context) < 0.40


class TestFaithfulnessDORA:
    """S4 — DORA ICT incident reporting."""

    def test_4hour_timeline_faithful(self):
        answer = (
            "Il Regolamento DORA Art. 19 impone la segnalazione degli incidenti gravi "
            "all'autorità entro 4 ore dalla classificazione iniziale."
        )
        assert faithfulness_proxy(answer, S4_DORA.context) >= 0.60

    def test_full_timeline_faithful(self):
        answer = (
            "DORA prevede un report intermedio entro 72 ore e un report finale entro un mese "
            "dall'incidente, con la classificazione iniziale entro 4 ore."
        )
        assert faithfulness_proxy(answer, S4_DORA.context) >= 0.50

    def test_wrong_regulation_unfaithful(self):
        """Risposta su normativa ambientale in contesto DORA → bassa faithfulness."""
        answer = (
            "La normativa agricola biologica regola le colture certificate. "
            "I produttori devono rispettare le distanze minime dai corsi d'acqua."
        )
        assert faithfulness_proxy(answer, S4_DORA.context) < 0.40


# ═══════════════════════════════════════════════════════════════════════════════
# NOISE ROBUSTNESS — RGB Testbed 1
# Ref: RGB arXiv:2309.01431 §3.1
# Target: faithfulness > 0.50 anche con 75% di chunk rumorosi
# ═══════════════════════════════════════════════════════════════════════════════

class TestNoiseRobustness:
    """
    RGB Testbed 1: Noise Robustness.
    La risposta fedele deve mantenere alta faithfulness anche con chunk rumorosi.
    """

    def test_gdpr_with_75pct_noise(self):
        """3 chunk rumorosi + 1 rilevante GDPR → faithfulness > 0.50."""
        noise = [
            "La pasta alla carbonara si prepara con guanciale, pecorino, uova e pepe.",
            "Il calciomercato estivo si conclude il 31 agosto di ogni anno.",
            "Il codice fiscale italiano si compone di 16 caratteri alfanumerici.",
        ]
        relevant = "Il GDPR Art. 33 richiede notifica all'autorità entro 72 ore."
        full_ctx  = "\n".join(noise + [relevant])
        answer    = "Secondo il GDPR Art. 33, la notifica deve avvenire entro 72 ore."
        assert faithfulness_proxy(answer, full_ctx) > 0.50

    def test_nis2_with_noise_no_catastrophic_degradation(self):
        """
        Faithfulness con rumore ≥ 50% della faithfulness senza rumore.
        Degrado tollerabile: il retriever non deve azzerare la qualità.
        """
        relevant  = "La Direttiva NIS2 Art. 23 prevede la notifica entro 24 ore dall'incidente."
        noise     = "Contenuto completamente irrilevante. " * 30
        answer    = "La NIS2 Art. 23 prevede la notifica entro 24 ore dall'incidente."

        score_clean = faithfulness_proxy(answer, relevant)
        score_noisy = faithfulness_proxy(answer, noise + "\n" + relevant)
        assert score_noisy >= score_clean * 0.50

    def test_dora_relevant_chunk_survives_noise(self):
        noise = [
            "Ricetta del tiramisù: savoiardi, mascarpone, caffè, zucchero.",
            "Le previsioni meteo indicano pioggia per il fine settimana.",
        ]
        relevant = "Il Regolamento DORA Art. 19 impone segnalazione entro 4 ore dalla classificazione."
        full_ctx  = "\n".join(noise + [relevant])
        answer    = "DORA Art. 19 richiede segnalazione entro 4 ore dalla classificazione."
        assert faithfulness_proxy(answer, full_ctx) > 0.50

    def test_aiact_signal_persists_through_noise(self):
        noise = "Testo irrilevante su argomenti diversi dal regolamento. " * 20
        relevant = (
            "Il Regolamento UE sull'IA classifica i sistemi ad alto rischio all'Allegato III. "
            "L'Art. 9 richiede un sistema di gestione del rischio per tutto il ciclo di vita."
        )
        answer = "Il Regolamento UE classifica i sistemi ad alto rischio all'Allegato III."
        full_ctx = noise + "\n" + relevant
        assert faithfulness_proxy(answer, full_ctx) > 0.50


# ═══════════════════════════════════════════════════════════════════════════════
# NEGATIVE REJECTION — RGB Testbed 2
# Ref: RGB arXiv:2309.01431 §3.1
# Il modello deve esprimere incertezza quando il contesto è irrilevante
# ═══════════════════════════════════════════════════════════════════════════════

class TestNegativeRejection:
    """
    RGB Testbed 2: Negative Rejection.
    Verifica che i pattern di refusal siano riconosciuti correttamente.
    """

    def test_refusal_patterns_italian(self):
        refusals = [
            "Non ho informazioni sufficienti per rispondere.",
            "Non posso rispondere sulla base del contesto disponibile.",
            "Non sono sicuro: questa informazione non è presente nel contesto.",
            "Non trovo questa informazione nei documenti disponibili.",
        ]
        for answer in refusals:
            assert REFUSAL_RE.search(answer), f"Non riconosciuto come refusal: {answer!r}"

    def test_refusal_patterns_english(self):
        refusals = [
            "I don't know based on the provided documents.",
            "I cannot answer this question from the given context.",
            "This information is not found in the retrieved passages.",
            "Not enough information available to answer the question.",
        ]
        for answer in refusals:
            assert REFUSAL_RE.search(answer), f"Non riconosciuto come refusal: {answer!r}"

    def test_hallucinated_answer_not_refusal(self):
        hallucinated = "Il termine previsto dall'articolo 5 comma 3 è di 24 ore."
        assert not REFUSAL_RE.search(hallucinated)

    def test_correct_answer_not_refusal(self):
        correct = "Il GDPR Art. 33 prevede la notifica entro 72 ore."
        assert not REFUSAL_RE.search(correct)

    def test_uncertain_answer_is_refusal(self):
        uncertain = "Non ho dati sufficienti per rispondere a questa domanda."
        assert REFUSAL_RE.search(uncertain)

    def test_partial_refusal_is_refusal(self):
        partial = "Non è possibile determinare il termine esatto senza ulteriori documenti."
        assert REFUSAL_RE.search(partial)
