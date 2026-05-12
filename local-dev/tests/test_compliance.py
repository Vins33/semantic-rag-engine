#!/usr/bin/env python3
"""
test_compliance.py — H5 Compliance Check test suite
=====================================================
Test offline (no LLM, no servizi) per app.pipeline.compliance.

Struttura:
  TestDetectFrameworks     (8 test)  — mapping domain/topics → frameworks
  TestGDPRRules            (8 test)  — GDPR rule engine
  TestNIS2Rules            (6 test)  — NIS2 rule engine
  TestAIActRules           (6 test)  — AI Act rule engine
  TestDORARules            (6 test)  — DORA rule engine
  TestCCPARules            (4 test)  — CCPA rule engine
  TestHIPAARules           (4 test)  — HIPAA rule engine
  TestActionVerbDisclaimer (5 test)  — disclaimer legale per action verbs
  TestNoRegulatedDomain    (5 test)  — domini non regolamentati → nessun warning
  TestEdgeCases            (4 test)  — empty answer, None domain, multi-framework

Totale: 56 test
"""

import pytest
from app.pipeline.compliance import (
    ComplianceResult,
    check_compliance,
    _detect_frameworks,
)


# ═══════════════════════════════════════════════════════════════════════════════
# TestDetectFrameworks — _detect_frameworks()
# ═══════════════════════════════════════════════════════════════════════════════

class TestDetectFrameworks:

    def test_gdpr_domain(self):
        assert "GDPR" in _detect_frameworks("gdpr", None)

    def test_nis2_domain(self):
        assert "NIS2" in _detect_frameworks("nis2", None)

    def test_ai_act_domain(self):
        assert "AI_ACT" in _detect_frameworks("ai_act", None)

    def test_dora_domain(self):
        assert "DORA" in _detect_frameworks("dora", None)

    def test_compliance_domain_multi(self):
        fws = _detect_frameworks("compliance", None)
        assert "GDPR" in fws
        assert "NIS2" in fws
        assert "DORA" in fws

    def test_topics_override(self):
        """Topic 'gdpr' su dominio non regolamentato deve attivare GDPR."""
        fws = _detect_frameworks("rag_foundation", ["gdpr", "privacy"])
        assert "GDPR" in fws

    def test_topics_nis2(self):
        fws = _detect_frameworks(None, ["nis2", "cybersecurity"])
        assert "NIS2" in fws

    def test_unknown_domain_no_frameworks(self):
        assert _detect_frameworks("unknown_xyz", None) == []


# ═══════════════════════════════════════════════════════════════════════════════
# TestGDPRRules
# ═══════════════════════════════════════════════════════════════════════════════

class TestGDPRRules:

    def test_data_breach_triggers_warning(self):
        result = check_compliance(
            answer="Si è verificato un data breach che ha esposto 10.000 record.",
            domain="gdpr",
        )
        assert result.has_warning
        fw_names = [w["framework"] for w in result.warnings]
        assert "GDPR" in fw_names

    def test_data_breach_message_contains_72h(self):
        result = check_compliance(
            answer="Un data breach è avvenuto ieri.",
            domain="gdpr",
        )
        gdpr_warnings = [w for w in result.warnings if w["framework"] == "GDPR"]
        assert any("72" in w["message"] for w in gdpr_warnings)

    def test_international_transfer_warning(self):
        result = check_compliance(
            answer="Trasferiremo i dati personali degli utenti negli USA tramite cloud.",
            domain="gdpr",
        )
        assert result.has_warning
        assert any("GDPR" == w["framework"] for w in result.warnings)

    def test_international_transfer_message_contains_scc(self):
        result = check_compliance(
            answer="I dati vengono trasferiti fuori dall'UE a provider cloud americani.",
            domain="gdpr",
        )
        gdpr_warnings = [w for w in result.warnings if w["framework"] == "GDPR"]
        assert any("SCC" in w["message"] or "Contractual" in w["message"] for w in gdpr_warnings)

    def test_retention_warning(self):
        result = check_compliance(
            answer="Conserviamo i dati personali degli utenti per 10 anni.",
            domain="gdpr",
        )
        assert result.has_warning

    def test_action_verb_disclaimer_added(self):
        result = check_compliance(
            answer="Sì, puoi raccogliere dati personali per le tue attività.",
            domain="gdpr",
            query="Posso raccogliere dati personali dei clienti?",
        )
        assert result.legal_disclaimer_added
        assert "⚠️" in result.compliance_note

    def test_neutral_answer_no_warning(self):
        result = check_compliance(
            answer="Il RAG (Retrieval-Augmented Generation) migliora l'accuratezza dei LLM.",
            domain="gdpr",
        )
        # Risposta su RAG non triggera regole GDPR
        gdpr_high = [w for w in result.warnings if w["framework"] == "GDPR" and w["severity"] == "high"]
        assert len(gdpr_high) == 0

    def test_severity_high_in_result(self):
        result = check_compliance(
            answer="C'è stato un data breach con esposizione di dati personali sensibili.",
            domain="gdpr",
        )
        high_warnings = [w for w in result.warnings if w["severity"] == "high"]
        assert len(high_warnings) > 0


# ═══════════════════════════════════════════════════════════════════════════════
# TestNIS2Rules
# ═══════════════════════════════════════════════════════════════════════════════

class TestNIS2Rules:

    def test_incident_notification_warning(self):
        result = check_compliance(
            answer="Un incidente ha compromesso le reti critiche dell'azienda.",
            domain="nis2",
        )
        assert result.has_warning
        assert any(w["framework"] == "NIS2" for w in result.warnings)

    def test_incident_message_contains_24h(self):
        result = check_compliance(
            answer="L'attacco informatico ha colpito i sistemi IT e OT.",
            domain="nis2",
        )
        nis2_warnings = [w for w in result.warnings if w["framework"] == "NIS2"]
        assert any("24" in w["message"] for w in nis2_warnings)

    def test_supply_chain_warning(self):
        result = check_compliance(
            answer="Il rischio supply chain dei fornitori ICT è stato identificato.",
            domain="nis2",
        )
        assert result.has_warning

    def test_risk_management_warning(self):
        result = check_compliance(
            answer="Il piano di gestione del rischio cyber è stato approvato.",
            domain="nis2",
        )
        assert result.has_warning
        mfa_messages = [w for w in result.warnings if "MFA" in w["message"] or "multi-fattore" in w["message"]]
        assert len(mfa_messages) > 0

    def test_security_domain_activates_nis2(self):
        result = check_compliance(
            answer="Un attacco informatico ha colpito i sistemi aziendali.",
            domain="security",
        )
        assert any(w["framework"] == "NIS2" for w in result.warnings)

    def test_penalty_warning(self):
        result = check_compliance(
            answer="La sanzione NIS2 può essere molto elevata per le aziende.",
            domain="nis2",
        )
        assert result.has_warning


# ═══════════════════════════════════════════════════════════════════════════════
# TestAIActRules
# ═══════════════════════════════════════════════════════════════════════════════

class TestAIActRules:

    def test_high_risk_ai_warning(self):
        result = check_compliance(
            answer="Vogliamo utilizzare un sistema AI ad alto rischio in ambito bancario.",
            domain="ai_act",
        )
        assert result.has_warning
        assert any(w["framework"] == "AI_ACT" for w in result.warnings)

    def test_high_risk_message_contains_conformity(self):
        result = check_compliance(
            answer="Il sistema AI critico verrà distribuito nel settore assicurativo.",
            domain="ai_act",
        )
        ai_warnings = [w for w in result.warnings if w["framework"] == "AI_ACT"]
        assert any("conformità" in w["message"] or "human" in w["message"].lower() for w in ai_warnings)

    def test_bias_warning(self):
        result = check_compliance(
            answer="Il modello AI mostra bias discriminatori nei confronti di alcune categorie.",
            domain="ai_act",
        )
        assert result.has_warning

    def test_gpai_warning(self):
        result = check_compliance(
            answer="Il modello GPAI (general purpose) deve rispettare gli obblighi di trasparenza.",
            domain="ai_act",
        )
        assert result.has_warning
        ai_warnings = [w for w in result.warnings if w["framework"] == "AI_ACT"]
        assert any("GPAI" in w["message"] or "sistemico" in w["message"] for w in ai_warnings)

    def test_prohibited_ai_warning(self):
        result = check_compliance(
            answer="Il sistema di social scoring è vietato dall'AI Act nell'UE.",
            domain="ai_act",
        )
        assert result.has_warning

    def test_llm_triggers_gpai_rule(self):
        result = check_compliance(
            answer="Stiamo sviluppando un LLM con 10^26 FLOPs di addestramento.",
            domain="ai_act",
        )
        assert result.has_warning


# ═══════════════════════════════════════════════════════════════════════════════
# TestDORARules
# ═══════════════════════════════════════════════════════════════════════════════

class TestDORARules:

    def test_ict_incident_warning(self):
        result = check_compliance(
            answer="Un incidente ICT ha causato l'interruzione dei sistemi bancari.",
            domain="dora",
        )
        assert result.has_warning
        assert any(w["framework"] == "DORA" for w in result.warnings)

    def test_ict_incident_message_contains_authorities(self):
        result = check_compliance(
            answer="La disruption ICT ha colpito l'infrastruttura finanziaria.",
            domain="dora",
        )
        dora_warnings = [w for w in result.warnings if w["framework"] == "DORA"]
        assert any("EBA" in w["message"] or "BCE" in w["message"] for w in dora_warnings)

    def test_third_party_outsourcing_warning(self):
        result = check_compliance(
            answer="I servizi ICT sono stati esternalizzati a un fornitore cloud terzo critico.",
            domain="dora",
        )
        assert result.has_warning

    def test_tlpt_warning(self):
        result = check_compliance(
            answer="Il TLPT (Threat-Led Penetration Testing) è richiesto ogni 3 anni.",
            domain="dora",
        )
        assert result.has_warning

    def test_bcp_warning(self):
        result = check_compliance(
            answer="Il piano di business continuity prevede un RTO di 4 ore.",
            domain="dora",
        )
        assert result.has_warning

    def test_financial_domain_activates_dora(self):
        result = check_compliance(
            answer="Un incidente ICT ha colpito l'infrastruttura di pagamenti.",
            domain="financial",
        )
        assert any(w["framework"] == "DORA" for w in result.warnings)


# ═══════════════════════════════════════════════════════════════════════════════
# TestCCPARules
# ═══════════════════════════════════════════════════════════════════════════════

class TestCCPARules:

    def test_data_selling_warning(self):
        result = check_compliance(
            answer="Vendiamo i dati personali degli utenti a terze parti pubblicitarie.",
            domain="ccpa",
        )
        assert result.has_warning
        assert any(w["framework"] == "CCPA" for w in result.warnings)

    def test_data_sharing_warning(self):
        result = check_compliance(
            answer="Condividiamo le personal information dei consumer con i partner.",
            domain="ccpa",
        )
        assert result.has_warning

    def test_sensitive_data_warning(self):
        result = check_compliance(
            answer="Raccogliamo dati biometrici e SSN dei clienti.",
            domain="ccpa",
        )
        assert result.has_warning
        ccpa_warnings = [w for w in result.warnings if w["framework"] == "CCPA"]
        assert any("sensibili" in w["message"].lower() or "SPI" in w["message"] for w in ccpa_warnings)

    def test_children_data_warning(self):
        result = check_compliance(
            answer="Raccogliamo dati di minori di 13 anni senza restrizioni.",
            domain="ccpa",
        )
        assert result.has_warning


# ═══════════════════════════════════════════════════════════════════════════════
# TestHIPAARules
# ═══════════════════════════════════════════════════════════════════════════════

class TestHIPAARules:

    def test_phi_warning(self):
        result = check_compliance(
            answer="Le cartelle cliniche (PHI) vengono condivise con il laboratorio.",
            domain="medical",
        )
        assert result.has_warning
        assert any(w["framework"] == "HIPAA" for w in result.warnings)

    def test_phi_breach_warning(self):
        result = check_compliance(
            answer="C'è stata una violazione delle PHI di 600 pazienti.",
            domain="medical",
        )
        assert result.has_warning
        hipaa_warnings = [w for w in result.warnings if w["framework"] == "HIPAA"]
        assert any("60" in w["message"] for w in hipaa_warnings)

    def test_de_identification_warning(self):
        result = check_compliance(
            answer="Occorre de-identificare i dati sanitari dei pazienti correttamente.",
            domain="medical",
        )
        assert result.has_warning

    def test_health_data_message_contains_treatment(self):
        result = check_compliance(
            answer="I dati sanitari dei pazienti vengono elaborati dal sistema.",
            domain="medical",
        )
        hipaa_warnings = [w for w in result.warnings if w["framework"] == "HIPAA"]
        assert any("Treatment" in w["message"] or "trattamento" in w["message"].lower() for w in hipaa_warnings)


# ═══════════════════════════════════════════════════════════════════════════════
# TestActionVerbDisclaimer
# ═══════════════════════════════════════════════════════════════════════════════

class TestActionVerbDisclaimer:

    def test_posso_in_query_adds_disclaimer(self):
        result = check_compliance(
            answer="Sì, è possibile raccogliere dati.",
            domain="gdpr",
            query="Posso raccogliere dati personali?",
        )
        assert result.legal_disclaimer_added
        assert "⚠️" in result.compliance_note

    def test_can_i_in_query_adds_disclaimer(self):
        result = check_compliance(
            answer="Yes, you can process personal data with consent.",
            domain="gdpr",
            query="Can I process personal data for marketing?",
        )
        assert result.legal_disclaimer_added

    def test_devo_in_answer_adds_disclaimer(self):
        result = check_compliance(
            answer="Devo notificare il data breach entro 72 ore al Garante.",
            domain="gdpr",
        )
        assert result.legal_disclaimer_added

    def test_disclaimer_text_mentions_legal_professional(self):
        result = check_compliance(
            answer="È possibile trattare questi dati personali.",
            domain="gdpr",
            query="È possibile?",
        )
        note = result.compliance_note
        assert "professionista" in note or "avvocato" in note or "DPO" in note

    def test_no_action_verb_no_disclaimer(self):
        result = check_compliance(
            answer="Il GDPR è entrato in vigore nel maggio 2018.",
            domain="gdpr",
        )
        assert not result.legal_disclaimer_added


# ═══════════════════════════════════════════════════════════════════════════════
# TestNoRegulatedDomain — domini non regolamentati → nessun warning
# ═══════════════════════════════════════════════════════════════════════════════

class TestNoRegulatedDomain:

    def test_rag_foundation_no_warning(self):
        result = check_compliance(
            answer="RAG combina retrieval denso con generazione linguistica per migliorare la qualità.",
            domain="rag_foundation",
        )
        assert not result.has_warning
        assert result.active_frameworks == []

    def test_graph_rag_no_warning(self):
        result = check_compliance(
            answer="GraphRAG usa knowledge graph per arricchire il contesto recuperato.",
            domain="graph_rag",
        )
        assert not result.has_warning

    def test_embeddings_memory_no_warning(self):
        result = check_compliance(
            answer="I vettori nomic-embed-text hanno dimensione 768.",
            domain="embeddings_memory",
        )
        assert not result.has_warning

    def test_none_domain_none_topics_no_warning(self):
        result = check_compliance(
            answer="Qualsiasi testo qui.",
            domain=None,
            topics=None,
        )
        assert not result.has_warning

    def test_unknown_domain_no_warning(self):
        result = check_compliance(
            answer="Contenuto arbitrario.",
            domain="xyz_non_esiste",
        )
        assert not result.has_warning


# ═══════════════════════════════════════════════════════════════════════════════
# TestEdgeCases
# ═══════════════════════════════════════════════════════════════════════════════

class TestEdgeCases:

    def test_empty_answer_no_warning(self):
        result = check_compliance(answer="", domain="gdpr")
        assert not result.has_warning

    def test_whitespace_answer_no_warning(self):
        result = check_compliance(answer="   \n\t  ", domain="gdpr")
        assert not result.has_warning

    def test_multi_framework_compliance_domain(self):
        """Domain 'compliance' attiva GDPR+NIS2+AI_ACT+DORA contemporaneamente."""
        result = check_compliance(
            answer=(
                "C'è stato un data breach che ha colpito l'ICT infrastruttura. "
                "Un sistema AI ad alto rischio è stato distribuito senza conformità."
            ),
            domain="compliance",
        )
        frameworks_hit = {w["framework"] for w in result.warnings}
        assert len(frameworks_hit) >= 2

    def test_result_is_compliance_result_type(self):
        result = check_compliance(answer="Test risposta.", domain="gdpr")
        assert isinstance(result, ComplianceResult)
