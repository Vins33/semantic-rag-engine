"""
H5 — Compliance Check (ComplianceNLP, arXiv:2604.23585 — ACL 2026 Industry Track)

Verifica gap normativi nella risposta generata quando il dominio del documento
è regolamentato (GDPR, NIS2, AI Act, DORA, CCPA, HIPAA).

Logica:
  1. Rileva i framework attivi dal dominio + topics del documento
  2. Per ogni framework attivo applica la rule engine (regex sincrona, no LLM)
     a. Rileva azioni regolamentate senza disclaimer obbligatori
     b. Rileva obblighi-chiave non menzionati nella risposta
     c. Aggiunge nota legale se la query contiene verbi d'azione
  3. Ritorna ComplianceResult strutturato con warning + compliance_note

Riferimento: ComplianceNLP (arXiv:2604.23585, ACL 2026 Industry Track)
"""

import re
from dataclasses import dataclass, field

# ── Mapping dominio → framework normativi attivi ──────────────────────────────

_DOMAIN_FRAMEWORKS: dict[str, list[str]] = {
    # Domini espliciti
    "gdpr":             ["GDPR"],
    "nis2":             ["NIS2"],
    "ai_act":           ["AI_ACT"],
    "dora":             ["DORA"],
    "ccpa":             ["CCPA"],
    "hipaa":            ["HIPAA"],
    # Domini aggregati
    "legal":            ["GDPR", "NIS2", "AI_ACT", "DORA"],
    "compliance":       ["GDPR", "NIS2", "AI_ACT", "DORA", "CCPA"],
    "security":         ["NIS2", "DORA"],
    "financial":        ["DORA"],
    "medical":          ["HIPAA", "GDPR"],
    "regulatory":       ["GDPR", "NIS2", "AI_ACT", "DORA", "CCPA"],
}

# Topic-keyword → framework (controlliamo se la parola appare nei topics)
_TOPIC_KEYWORDS: dict[str, str] = {
    "gdpr":         "GDPR",
    "rgpd":         "GDPR",
    "nis2":         "NIS2",
    "ai act":       "AI_ACT",
    "ai_act":       "AI_ACT",
    "artificial intelligence act": "AI_ACT",
    "dora":         "DORA",
    "ccpa":         "CCPA",
    "hipaa":        "HIPAA",
}

# ── Rule engine ───────────────────────────────────────────────────────────────
# Ogni regola: (regex, messaggio_warning, severità)
# La regex è applicata alla risposta generata (case-insensitive)

_RULES: dict[str, list[tuple[re.Pattern, str, str]]] = {

    "GDPR": [
        (
            re.compile(
                r"\b(posso|può|si può|è possibile|è lecito|è consentito|allowed to|may I|can I)\b"
                r".{0,120}"
                r"\b(dati personali|personal data|dati degli utenti|dati sensibili|tratt\w*|raccoglier\w*|raccogli\w*|condivid\w*|process|collect|share)\b",
                re.I | re.S,
            ),
            "GDPR Art. 6 — il trattamento di dati personali richiede una base giuridica "
            "(consenso, contratto, obbligo legale, legittimo interesse). "
            "Verificare la base giuridica applicabile prima di procedere.",
            "high",
        ),
        (
            # Lookaheads: ordine-indipendenti + stem matching per coniugazioni
            re.compile(
                r"(?=.*\btrasfer\w*|.*\btransfer|.*\bsend\b|.*\bexport|.*\binviar\w*|.*\besport\w*)"
                r"(?=.*\bdati personali|.*\bpersonal data|.*\butenti\b|.*\busers\b|.*\bdati\b)"
                r"(?=.*\bUSA\b|.*\bstati uniti|.*\bcloud\b|.*\bpaesi terzi|.*fuori dall\w*\s*UE|.*third countr|.*non.EU)",
                re.I | re.S,
            ),
            "GDPR Cap. V — i trasferimenti internazionali di dati richiedono garanzie adeguate: "
            "Standard Contractual Clauses (SCC), Binding Corporate Rules (BCR) o decisione di adeguatezza.",
            "high",
        ),
        (
            re.compile(
                r"\b(data breach|violazione dei dati|violazione della sicurezza|data violation|security breach|incidente di sicurezza)\b",
                re.I,
            ),
            "GDPR Art. 33/34 — un data breach deve essere notificato all'autorità di controllo entro 72 ore "
            "e, se l'incidente comporta un alto rischio per gli interessati, anche a questi ultimi senza ingiustificato ritardo.",
            "high",
        ),
        (
            # Stem matching per coniugazioni: conserv(are/iamo/ato), archivi(are/amo)
            re.compile(
                r"(?=.*\bconserv\w*|.*\bretention\b|.*\barchivi\w*|.*\bmantenere\b|.*\bstore\b|.*\bretain\b|.*\barchive\b)"
                r"(?=.*\bdati personali|.*\bpersonal data|.*\blog\b|.*\bregistrazioni|.*\brecords\b)",
                re.I | re.S,
            ),
            "GDPR Art. 5(1)(e) — principio di limitazione della conservazione: i dati personali non devono "
            "essere conservati in forma identificabile oltre il tempo necessario alle finalità di trattamento.",
            "medium",
        ),
        (
            re.compile(
                r"\b(diritto all'oblio|right to erasure|cancellazione|delete.*personal|right to be forgotten)\b",
                re.I,
            ),
            "GDPR Art. 17 — il diritto alla cancellazione è soggetto a specifiche condizioni ed eccezioni "
            "(obbligo legale, esercizio di diritti in sede giudiziaria, interesse pubblico).",
            "medium",
        ),
    ],

    "NIS2": [
        (
            # Stem + plurali italiani (rete/reti, critico/critici/critiche) + lookahead
            re.compile(
                r"(?=.*\bincident\w*|.*\battacc\w*|.*\bviolazion\w*|.*\bbreach|.*\bcompromission\w*|.*\bdisruption|.*\boutage)"
                r"(?=.*\bret[ei]\b|.*\bsistem\w*|.*\binfrastruttur\w*|.*\bOT\b|.*\bIT\b|.*\bnetwork|.*\bsystem|.*\bcritich?\w*)",
                re.I | re.S,
            ),
            "NIS2 Art. 23 — gli incidenti significativi devono essere notificati al CSIRT nazionale: "
            "early warning entro 24 h, notifica formale entro 72 h, relazione finale entro 1 mese.",
            "high",
        ),
        (
            # Lookahead: supply chain o fornitore + sicurezza o rischio (ordine qualunque)
            re.compile(
                r"(?=.*\bsupply chain|.*\bfornitor\w*|.*\bvendor|.*\bterze parti|.*\bthird.part|.*\boutsourcing)"
                r"(?=.*\bsicurezza|.*\brischio|.*\bvulnerabilità|.*\bsecurity|.*\brisk|.*\bvulnerability)",
                re.I | re.S,
            ),
            "NIS2 Art. 21(2)(d) — le organizzazioni devono gestire i rischi della supply chain ICT: "
            "valutazione della sicurezza dei fornitori, clausole contrattuali minime di sicurezza.",
            "high",
        ),
        (
            re.compile(
                r"\b(gestione del rischio|risk management|misure di sicurezza|security measures|cybersecurity measures)\b",
                re.I,
            ),
            "NIS2 Art. 21 — le misure minime obbligatorie includono: autenticazione multi-fattore (MFA), "
            "crittografia dei dati, gestione degli accessi privilegiati, business continuity e disaster recovery.",
            "medium",
        ),
        (
            re.compile(
                r"(?=.*\bsanzion\w*|.*\bmulta|.*\bpenalty|.*\bfine\b)"
                r"(?=.*\bNIS2|.*\bdirettiva|.*\bdirective|.*\bcybersecurity)",
                re.I | re.S,
            ),
            "NIS2 Art. 34 — le sanzioni per i soggetti essenziali arrivano fino a 10 M€ o il 2% del fatturato "
            "mondiale annuo; per i soggetti importanti fino a 7 M€ o l'1,4% del fatturato.",
            "medium",
        ),
    ],

    "AI_ACT": [
        (
            re.compile(
                r"(?=.*\bsistema AI|.*\bmodell\w* AI|.*\balgoritm\w*|.*\bAI system|.*\bintelligenza artificiale|.*\bartificial intelligence)"
                r"(?=.*\balto rischio|.*\bhigh.risk|.*\bcritich?\w*|.*\bcritico|.*\bdeploy|.*\bdistribuir\w*|.*\busare|.*\butilizzar\w*|.*\buse\b|.*\bimplement)",
                re.I | re.S,
            ),
            "AI Act Tit. III — i sistemi AI ad alto rischio richiedono: valutazione della conformità prima "
            "del deployment, documentazione tecnica, registrazione nel database EU, supervisione umana (human-in-the-loop).",
            "high",
        ),
        (
            # Lookahead: bias + AI (in qualunque ordine)
            re.compile(
                r"(?=.*\bbias|.*\bdiscriminazion\w*|.*\bequità|.*\bfairness|.*\bdiscriminatory|.*\bunfair)"
                r"(?=.*\bAI\b|.*\bmodell\w*|.*\bsistem\w*|.*\balgoritm\w*|.*\bmodel\b|.*\bsystem\b)",
                re.I | re.S,
            ),
            "AI Act Art. 10 — i dataset di addestramento per sistemi ad alto rischio devono rispettare "
            "i requisiti di qualità dei dati: privi di errori, rappresentativi, esenti da bias discriminatori.",
            "medium",
        ),
        (
            re.compile(
                r"\b(GPAI|general.purpose AI|uso generale|foundation model|LLM|large language model)\b",
                re.I,
            ),
            "AI Act Tit. VIII — i modelli GPAI con impatto sistemico (>10²⁵ FLOPs di addestramento) hanno "
            "obblighi aggiuntivi: trasparenza, valutazione avversariale, notifica all'UAIO, adversarial testing.",
            "medium",
        ),
        (
            re.compile(
                r"\b(proibito|vietato|prohibited|forbidden|banned)\b"
                r".{0,80}"
                r"\b(AI|sistema|sistema AI|algoritmo|riconoscimento facciale|facial recognition|social scoring)\b",
                re.I | re.S,
            ),
            "AI Act Art. 5 — i sistemi AI con pratiche proibite (social scoring, manipolazione subliminale, "
            "biometric categorisation basata su caratteristiche protette) non possono essere sviluppati o immessi sul mercato UE.",
            "high",
        ),
    ],

    "DORA": [
        (
            # Lookahead: ICT/infrastruttura + incident/disruption (ordine qualunque)
            re.compile(
                r"(?=.*\bICT\b|.*\binfrastruttur\w*|.*\bsistema informatico|.*\bIT system|.*\binformation system)"
                r"(?=.*\bincident\w*|.*\bincidente|.*\bdisruption|.*\binterruzion\w*|.*\bresilienza|.*\bresilience|.*\bfailure)",
                re.I | re.S,
            ),
            "DORA Art. 17-18 — gli incidenti ICT nel settore finanziario devono essere classificati "
            "e segnalati alle autorità competenti (BCE, EBA, ESMA, EIOPA) entro le scadenze stabilite: "
            "notifica iniziale entro 4 h, intermedia entro 72 h, finale entro 1 mese.",
            "high",
        ),
        (
            # Lookahead: terze parti/cloud/fornitore + ICT/servizi (ordine qualunque)
            re.compile(
                r"(?=.*\bterze parti|.*\boutsourcing|.*\bcloud\b|.*\bfornitor\w*|.*\bCTPP|.*\bthird.part|.*\bvendor|.*\bprovider)"
                r"(?=.*\bICT\b|.*\bservizi|.*\btecnologia|.*\bservices|.*\btechnology)",
                re.I | re.S,
            ),
            "DORA Art. 28-30 — i contratti con fornitori ICT terzi critici (CTPP) devono includere: "
            "diritto di audit, exit strategy documentata, obblighi di sicurezza minimi, "
            "notifica degli incidenti al cliente finanziario.",
            "high",
        ),
        (
            re.compile(
                r"\b(TLPT|penetration test|test di penetrazione|resilience test|stress test|threat.led)\b",
                re.I,
            ),
            "DORA Art. 26 — le entità finanziarie significative devono condurre TLPT "
            "(Threat-Led Penetration Testing) ogni 3 anni con scenari threat intelligence approvati dall'autorità competente.",
            "medium",
        ),
        (
            re.compile(
                r"\b(business continuity|continuità operativa|disaster recovery|BCP|RTO|RPO)\b",
                re.I,
            ),
            "DORA Art. 11 — le entità finanziarie devono disporre di piani di business continuity ICT "
            "testati periodicamente, con RTO/RPO definiti e comunicati all'autorità di vigilanza.",
            "medium",
        ),
    ],

    "CCPA": [
        (
            # Stem matching: vend(ere/iamo/uto), condivis(ione/iamo), condivid(ere)
            re.compile(
                r"(?=.*\bvend\w*|.*\bsell\b|.*\bcondivis\w*|.*\bcondivid\w*|.*\bshare\b|.*\bdivulg\w*|.*\bdisclose|.*\bmonetizz\w*|.*\bmonetize)"
                r"(?=.*\bdati personali|.*\bpersonal data|.*\bpersonal information|.*\bconsumer|.*\butenti\b)",
                re.I | re.S,
            ),
            "CCPA § 1798.100 / CPRA — i consumatori della California hanno il diritto di opt-out "
            "dalla vendita/condivisione di dati personali. La privacy notice deve includere un link "
            "'Do Not Sell or Share My Personal Information'.",
            "high",
        ),
        (
            re.compile(
                r"\b(dati sensibili|sensitive data|sensitive personal information|SPI|"
                r"SSN|codice fiscale|biometric|biometrico|geolocalizzazione|precise.*location|health.*data|dati sanitari)\b",
                re.I,
            ),
            "CCPA § 1798.121 (CPRA) — i dati sensibili (SSN, coordinate bancarie, geolocalizzazione precisa, "
            "biometria, dati sanitari) richiedono il diritto di limitarne l'uso. "
            "Pubblicare un link 'Limit the Use of My Sensitive Personal Information'.",
            "high",
        ),
        (
            # Lookahead: minori + dati (ordine qualunque)
            re.compile(
                r"(?=.*\bminori\b|.*\bbambini|.*\bchildren|.*\bminors|.*\bunder 16|.*\bunder 13|.*\bCOPPA)"
                r"(?=.*\bdati\b|.*\bdata\b|.*\binformation|.*\binformazioni)",
                re.I | re.S,
            ),
            "CCPA § 1798.120 — i dati di minori di 16 anni non possono essere venduti senza consenso: "
            "opt-in richiesto per 13-15 anni, consenso dei genitori per under 13.",
            "high",
        ),
    ],

    "HIPAA": [
        (
            re.compile(
                r"\b(PHI|ePHI|dati sanitari|cartella clinica|informazioni mediche|health data|"
                r"patient data|medical record|health information|protected health)\b",
                re.I,
            ),
            "HIPAA Privacy Rule — le PHI (Protected Health Information) possono essere usate o divulgate "
            "solo per trattamento (Treatment), pagamento (Payment) o operazioni sanitarie (Healthcare Operations), "
            "oppure con autorizzazione scritta del paziente.",
            "high",
        ),
        (
            re.compile(
                r"\b(breach|violazione)\b"
                r".{0,80}"
                r"\b(PHI|ePHI|dati sanitari|health|medical)\b",
                re.I | re.S,
            ),
            "HIPAA Breach Notification Rule — una violazione di PHI non protetta deve essere notificata: "
            "agli individui entro 60 giorni, al Dipartimento HHS e, se >500 individui nello stesso Stato, "
            "ai principali media locali.",
            "high",
        ),
        (
            re.compile(
                r"\b(de.identif|anonimizzare|anonymize|de.id|safe.harbor)\b"
                r".{0,80}"
                r"\b(PHI|dati sanitari|health|medical|paziente|patient)\b",
                re.I | re.S,
            ),
            "HIPAA § 164.514 — la de-identificazione deve seguire il metodo Safe Harbor "
            "(rimozione di 18 identificatori specifici) o il metodo statistico certificato da un esperto.",
            "medium",
        ),
    ],
}

# ── Action-verb detector — aggiunge disclaimer legale ────────────────────────

_ACTION_VERB_RE = re.compile(
    r"\b(posso|può|si può|è possibile|è lecito|è consentito|devo|dobbiamo|"
    r"è obbligatorio|è vietato|can I|may I|am I allowed|should I|must I|is it legal)\b",
    re.I,
)

_LEGAL_DISCLAIMER = (
    "⚠️  Nota legale: questa risposta ha scopo puramente informativo e non costituisce "
    "parere legale. Per decisioni operative in materia di conformità normativa, "
    "è necessario consultare un professionista qualificato (avvocato o DPO)."
)


# ── Dataclass risultato ───────────────────────────────────────────────────────

@dataclass
class ComplianceResult:
    """Risultato del compliance check H5."""
    has_warning:            bool
    warnings:               list[dict]  = field(default_factory=list)
    active_frameworks:      list[str]   = field(default_factory=list)
    legal_disclaimer_added: bool        = False
    compliance_note:        str         = ""


# ── Funzioni helper ───────────────────────────────────────────────────────────

def _detect_frameworks(domain: str | None, topics: list[str] | None) -> list[str]:
    """Deduce i framework normativi attivi da domain + topics estratti dai metadati."""
    frameworks: set[str] = set()

    if domain:
        d = domain.lower().replace("-", "_").replace(" ", "_")
        frameworks.update(_DOMAIN_FRAMEWORKS.get(d, []))

    if topics:
        for t in topics:
            t_lower = t.lower()
            for kw, fw in _TOPIC_KEYWORDS.items():
                if kw in t_lower:
                    frameworks.add(fw)

    return sorted(frameworks)


# ── Funzione principale ───────────────────────────────────────────────────────

def check_compliance(
    answer: str,
    domain: str | None = None,
    topics: list[str] | None = None,
    query: str | None = None,
) -> ComplianceResult:
    """
    H5 — Compliance Check sincrono (pura regex rule engine, no LLM).

    Args:
        answer:  risposta generata dal LLM
        domain:  dominio del documento (da metadata, es. "gdpr", "security")
        topics:  parole chiave del documento (da metadata enrichment)
        query:   query originale dell'utente (per rilevare action verbs)

    Returns:
        ComplianceResult con has_warning, warnings, compliance_note
    """
    if not answer or not answer.strip():
        return ComplianceResult(has_warning=False)

    active_frameworks = _detect_frameworks(domain, topics)

    # Dominio non regolamentato → skip
    if not active_frameworks:
        return ComplianceResult(has_warning=False)

    warnings: list[dict] = []

    for fw in active_frameworks:
        rules = _RULES.get(fw, [])
        for pattern, message, severity in rules:
            if pattern.search(answer):
                warnings.append({
                    "framework": fw,
                    "message":   message,
                    "severity":  severity,
                })

    # Action-verb check: se la query o la risposta contiene verbi d'azione
    # aggiungiamo il disclaimer legale
    combined_check = f"{query or ''} {answer}"
    legal_disclaimer_added = bool(
        active_frameworks and _ACTION_VERB_RE.search(combined_check)
    )

    # Componi nota compliance (solo warning high + disclaimer)
    notes: list[str] = []
    if legal_disclaimer_added:
        notes.append(_LEGAL_DISCLAIMER)
    for w in warnings:
        if w["severity"] == "high":
            notes.append(f"[{w['framework']}] {w['message']}")

    return ComplianceResult(
        has_warning=bool(warnings) or legal_disclaimer_added,
        warnings=warnings,
        active_frameworks=active_frameworks,
        legal_disclaimer_added=legal_disclaimer_added,
        compliance_note="\n\n".join(notes),
    )
