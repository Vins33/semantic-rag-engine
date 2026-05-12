#!/usr/bin/env python3
"""
Migration script — arricchisce i metadati (D3+D4) dei documenti già indicizzati.

Non tocca gli embedding, non cancella nulla:
  1. Legge tutti i doc_id da PostgreSQL
  2. Per ogni documento: estrae excerpt dai chunk esistenti
  3. Chiama Ollama (llama3.2) per estrarre domain/doc_type/language/year/topics
  4. Aggiorna PostgreSQL (colonne documents) e Qdrant (payload dei chunk)
  5. Registra ogni migrazione nell'audit log (E6)

Uso (dalla directory mvp/ con venv attivato):
    python3 migrate_metadata.py

Stima tempo: ~3-5 secondi per documento × 58 documenti ≈ 3-5 minuti totali.
"""

import asyncio
import sys
from pathlib import Path

# Assicura che il path includa mvp/ per gli import relativi
sys.path.insert(0, str(Path(__file__).parent))

from app.core.audit import log_event
from app.knowledge.metadata import enrich_document
from app.storage import db, vector as vec_store


async def migrate_one(doc: dict, idx: int, total: int) -> bool:
    doc_id   = doc["doc_id"]
    filename = doc["filename"]
    domain   = doc["domain"]

    # Salta se già arricchito (domain diverso da 'unknown')
    if domain != "unknown":
        print(f"  [{idx}/{total}] ↷ {filename}  (già arricchito: {domain})")
        return True

    # Estrai excerpt dai chunk esistenti
    excerpt = db.get_document_text_excerpt(doc_id, max_chars=1500)
    if not excerpt.strip():
        print(f"  [{idx}/{total}] ✗ {filename}  (nessun testo disponibile)")
        return False

    # Enrichment via LLM
    try:
        meta = await enrich_document(filename, excerpt)
    except Exception as exc:
        print(f"  [{idx}/{total}] ✗ {filename}  LLM error: {exc}")
        return False

    # Aggiorna PostgreSQL
    db.update_document_metadata(
        doc_id,
        meta["domain"],
        meta["doc_type"],
        meta["language"],
        meta["year"],
        meta["topics"],
    )

    # Aggiorna payload Qdrant per tutti i chunk di questo documento
    payload_update = {
        "domain":   meta["domain"],
        "language": meta["language"],
        "doc_type": meta["doc_type"],
        "year":     meta["year"],
        "topics":   meta["topics"],
    }
    n_updated = vec_store.update_doc_payload(doc_id, payload_update)

    # Audit log
    log_event("migrate", doc_id, {
        "filename":  filename,
        "domain":    meta["domain"],
        "doc_type":  meta["doc_type"],
        "language":  meta["language"],
        "year":      meta["year"],
        "topics":    meta["topics"],
        "qdrant_updated": n_updated,
    })

    topics_str = ", ".join(meta["topics"][:3]) if meta["topics"] else "—"
    print(
        f"  [{idx}/{total}] ✓ {filename}\n"
        f"          domain={meta['domain']}  lang={meta['language']}  "
        f"year={meta['year']}  topics=[{topics_str}]\n"
        f"          Qdrant chunks aggiornati: {n_updated}"
    )
    return True


async def main():
    print("=== Metadata Migration (D3+D4) ===\n")

    # Inizializza schema (aggiunge colonne se mancanti)
    db.init_schema()
    print("✓ Schema PostgreSQL aggiornato\n")

    docs = db.get_all_documents()
    if not docs:
        print("Nessun documento trovato nel DB.")
        return

    total = len(docs)
    print(f"Trovati {total} documenti da elaborare...\n")

    ok = 0
    for i, doc in enumerate(docs, 1):
        success = await migrate_one(doc, i, total)
        if success:
            ok += 1

    # Statistiche finali
    docs_after = db.get_all_documents()
    domain_counts: dict[str, int] = {}
    for d in docs_after:
        domain_counts[d["domain"]] = domain_counts.get(d["domain"], 0) + 1

    print(f"\n=== Completato: {ok}/{total} documenti arricchiti ===")
    print("\nDistribuzione domini:")
    for domain, count in sorted(domain_counts.items(), key=lambda x: -x[1]):
        bar = "█" * count
        print(f"  {domain:<25} {count:>3}  {bar}")


if __name__ == "__main__":
    asyncio.run(main())
