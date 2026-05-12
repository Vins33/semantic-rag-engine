"""
H4 — Citation Validator

Verifica che le citazioni di documento/pagina nella risposta generata
corrispondano effettivamente alle fonti recuperate.

Analizza la risposta cercando pattern tipo:
  "[filename.pdf | pag. N]"
  "[filename | pag. N]"
  "(documento X, pagina N)"

Per ogni citazione trovata:
  - Verifica che il documento sia nelle fonti recuperate
  - Verifica che la pagina sia in range plausibile rispetto alle fonti

Output: CitationResult con:
  - valid_citations: list[dict]    → citazioni verificate
  - invalid_citations: list[dict]  → citazioni non trovate nelle fonti
  - uncited_sources: list[str]     → fonti recuperate ma non citate nella risposta
  - citation_coverage: float       → % fonti effettivamente citate
"""

import re
from dataclasses import dataclass, field


# ── Pattern di citazione nel formato usato dal nostro prompt ─────────────────

# Formato primario: [filename.pdf | pag. 12]  o  [filename | pag. 12]
_CITE_PATTERN_PIPE = re.compile(
    r"\[([^\]|]+?)\s*\|\s*pag\.\s*(\d+)\]", re.I
)

# Formato secondario: (documento X, pagina N)
_CITE_PATTERN_PAREN = re.compile(
    r"\(([^)]+?),\s*pagina\s*(\d+)\)", re.I
)

# Formato inglese: [filename, p. 12] o [filename, page 12]
_CITE_PATTERN_EN = re.compile(
    r"\[([^\]]+?),\s*p(?:age|\.)\s*(\d+)\]", re.I
)


@dataclass
class CitationResult:
    valid_citations: list[dict] = field(default_factory=list)
    invalid_citations: list[dict] = field(default_factory=list)
    uncited_sources: list[str] = field(default_factory=list)
    citation_coverage: float = 0.0   # % delle fonti recuperate citate nella risposta
    all_valid: bool = True


def _extract_citations(answer: str) -> list[dict]:
    """Estrae tutte le citazioni dalla risposta nei formati supportati."""
    citations: list[dict] = []

    for pat in [_CITE_PATTERN_PIPE, _CITE_PATTERN_PAREN, _CITE_PATTERN_EN]:
        for match in pat.finditer(answer):
            citations.append({
                "raw":      match.group(0),
                "filename": match.group(1).strip(),
                "page":     int(match.group(2)),
            })

    return citations


def _normalize_filename(name: str) -> str:
    """Normalizza filename per confronto tollerante."""
    # Rimuovi estensione, lowercase, rimuovi caratteri speciali
    name = re.sub(r"\.(pdf|md|txt)$", "", name.lower())
    name = re.sub(r"[_\-\s]+", " ", name).strip()
    return name


def validate_citations(answer: str, sources: list[dict]) -> CitationResult:
    """
    Valida le citazioni nella risposta rispetto alle fonti effettivamente recuperate.
    
    Args:
        answer: testo della risposta generata
        sources: lista di dict con chiavi 'filename', 'page' (dalle fonti recuperate)
    
    Returns:
        CitationResult
    """
    citations = _extract_citations(answer)

    # Costruisci lookup normalizzato delle fonti recuperate
    source_lookup: dict[str, list[int]] = {}
    for src in sources:
        norm = _normalize_filename(src.get("filename", ""))
        if norm not in source_lookup:
            source_lookup[norm] = []
        source_lookup[norm].append(src.get("page", 0))

    valid: list[dict] = []
    invalid: list[dict] = []

    for cite in citations:
        cite_norm = _normalize_filename(cite["filename"])
        # Ricerca fuzzy: il nome citato deve essere contenuto in un filename fonte
        matched = False
        for src_norm, pages in source_lookup.items():
            if cite_norm in src_norm or src_norm in cite_norm:
                matched = True
                # Pagina nella risposta vs pagine effettivamente recuperate
                # Tolleriamo ±2 pagine (il chunk può iniziare a pagina N ma citare N+1)
                page_ok = any(abs(cite["page"] - p) <= 2 for p in pages)
                entry = {**cite, "source_filename": src_norm, "page_ok": page_ok}
                if page_ok:
                    valid.append(entry)
                else:
                    invalid.append({**entry, "reason": f"page {cite['page']} not in retrieved pages {pages}"})
                break

        if not matched:
            invalid.append({**cite, "reason": "document not in retrieved sources"})

    # Fonti recuperate non citate nella risposta
    cited_filenames = {_normalize_filename(c["filename"]) for c in citations}
    uncited: list[str] = []
    for src in sources:
        src_norm = _normalize_filename(src.get("filename", ""))
        if not any(cf in src_norm or src_norm in cf for cf in cited_filenames):
            uncited.append(src.get("filename", ""))

    # Coverage: % delle fonti recuperate che appaiono nella risposta
    n_sources = len(sources)
    n_uncited = len(uncited)
    coverage = round(1.0 - (n_uncited / n_sources), 3) if n_sources > 0 else 1.0

    # Se non ci sono citazioni nella risposta → non invalidiamo (il LLM potrebbe aver scelto non citare)
    all_valid = len(invalid) == 0

    return CitationResult(
        valid_citations=valid,
        invalid_citations=invalid,
        uncited_sources=uncited,
        citation_coverage=coverage,
        all_valid=all_valid,
    )
