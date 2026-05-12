"""
Pipeline di ingestione PDF e Markdown.

Flusso PDF:
  1. Upload raw PDF → MinIO (E1 raw/)
  2. Conversione PDF → Markdown → MinIO (E1 parsed/)
  3. Estrazione testo per pagina → PyMuPDF
     └─ Fallback OCR (facebook/nougat-base) per PDF image-only
  4. Chunking section-aware (~400 token con overlap)
  5. Metadata documento → PostgreSQL (E4)
  6. Embedding batch → Ollama (nomic-embed-text)
  7. Upsert vettori + payload → Qdrant (E2)
  8. Testo chunk → PostgreSQL (E4, per FTS ibrida)
  9. D1/D2 — Entity + Relation extraction (background, primi N chunk)
 10. C6 — KG build da triple estratte → Neo4j

Flusso Markdown:
  1. Upload .md → MinIO (E1 parsed/)
  2. Parsing pagine dal markdown
  3. Chunking → embedding → Qdrant/PostgreSQL (stessa pipeline) + D1/D2/C6
"""

import hashlib
import logging
import re
import uuid
import asyncio

import fitz  # PyMuPDF
from qdrant_client.models import PointStruct

from app.core import ollama
from app.core.audit import log_event
from app.core.config import settings
from app.knowledge.metadata import enrich_document
from app.ingestion.pdf_to_md import pdf_to_markdown, markdown_to_pages
from app.storage import db, object as obj_store, vector as vec_store

logger = logging.getLogger(__name__)

# ── Costanti ──────────────────────────────────────────────────────────────────
_TARGET_CHARS  = settings.chunk_target_tokens  * 4   # ~4 char/token
_OVERLAP_CHARS = settings.chunk_overlap_tokens * 4

# Pattern per intestazioni di sezione accademiche
_HEADER_RE = re.compile(
    r"^(?:"
    r"\d{1,2}(?:\.\d{1,2}){0,2}\.?\s+[A-Z][a-zA-Z]"  # "1. Intro", "2.1 Method"
    r"|[A-Z][A-Z\s\-]{3,50}$"                          # ABSTRACT, INTRODUCTION
    r"|Abstract|Introduction|Conclusion(?:s)?"
    r"|Related\s+Work|Method(?:ology|s)?|Experiment(?:s|al\s+Setup)?"
    r"|Discussion|Results?|References|Acknowledgement(?:s)?"
    r"|Appendix|Background"
    r")"
)

# Splitting frasi: divide dopo ".!?" seguiti da maiuscola, ma non abbreviazioni
_SENT_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z\d\"])")


def _is_section_header(text: str) -> bool:
    line = text.strip()
    return len(line) < 100 and bool(_HEADER_RE.match(line))


def _split_sentences(text: str) -> list[str]:
    """Sentence splitting via regex — nessuna dipendenza esterna."""
    return [s.strip() for s in _SENT_SPLIT_RE.split(text) if s.strip()]


# ── Estrazione testo ──────────────────────────────────────────────────────────

def _extract_pages(pdf_bytes: bytes) -> list[dict]:
    """
    Ritorna [{page: int, text: str}, ...].
    Se PyMuPDF non estrae testo (PDF image-only) attiva il fallback OCR via Nougat.
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pages = []
    has_text = False
    for i in range(len(doc)):
        text = doc[i].get_text("text").strip()
        text = text.replace("\x00", "").replace("\r", " ")
        if text:
            has_text = True
            pages.append({"page": i + 1, "text": text})
    doc.close()

    if not has_text:
        # Fallback: OCR con facebook/nougat-base
        import logging
        logging.getLogger(__name__).info("PDF image-only — avvio OCR Nougat …")
        from app.ingestion.ocr import ocr_pdf
        pages = ocr_pdf(pdf_bytes)

    return pages


# ── Chunking section-aware ────────────────────────────────────────────────────

def _chunk_pages(pages: list[dict]) -> list[dict]:
    """
    Chunker section-aware con overlap testuale.
    - Forza flush prima di ogni intestazione di sezione rilevata.
    - Sentence-splitting su regex per chunk > TARGET.
    - Ogni chunk registra pagina di inizio e fine.
    """
    chunks: list[dict] = []
    buf_text  = ""
    buf_pages: list[int] = []

    def _flush(overlap_text: str = "") -> None:
        nonlocal buf_text, buf_pages
        if buf_text.strip():
            chunks.append({
                "text":       buf_text.strip(),
                "page_start": buf_pages[0] if buf_pages else 1,
                "page_end":   buf_pages[-1] if buf_pages else 1,
            })
        buf_text  = overlap_text
        buf_pages = []

    for page_data in pages:
        page_num = page_data["page"]
        paragraphs = [p.strip() for p in page_data["text"].split("\n\n") if p.strip()]

        for para in paragraphs:
            # Intestazione di sezione → flush immediato per non mescolare sezioni
            if _is_section_header(para):
                if buf_text.strip():
                    _flush()
                buf_text = para
                buf_pages = [page_num]
                continue

            # Paragrafo lungo → splitting a livello di frase
            if len(para) > _TARGET_CHARS:
                for sent in _split_sentences(para):
                    if not sent:
                        continue
                    if len(buf_text) + len(sent) + 2 > _TARGET_CHARS:
                        overlap = buf_text[-_OVERLAP_CHARS:] if buf_text else ""
                        _flush(overlap)
                    buf_text += (" " if buf_text else "") + sent
                    if page_num not in buf_pages:
                        buf_pages.append(page_num)
            else:
                if len(buf_text) + len(para) + 4 > _TARGET_CHARS:
                    overlap = buf_text[-_OVERLAP_CHARS:] if buf_text else ""
                    _flush(overlap)
                buf_text += ("\n\n" if buf_text else "") + para
                if page_num not in buf_pages:
                    buf_pages.append(page_num)

    _flush()
    return chunks


# ── Pipeline principale ───────────────────────────────────────────────────────

async def ingest_pdf(filename: str, pdf_bytes: bytes) -> dict:
    sha256 = hashlib.sha256(pdf_bytes).hexdigest()

    # Deduplicazione: se il PDF è già indicizzato restituisce subito il risultato
    if db.document_exists(sha256):
        raise ValueError(
            f"Il documento '{filename}' è già presente nel corpus (SHA-256: {sha256[:12]}…). "
            "Nessuna reingestione necessaria."
        )

    doc_id = str(uuid.uuid4())

    # 1. MinIO — raw PDF
    obj_store.upload_pdf(doc_id, pdf_bytes)

    # 2. PDF → Markdown → MinIO parsed/
    md_text = pdf_to_markdown(pdf_bytes)
    if md_text.strip():
        obj_store.upload_markdown(doc_id, md_text)

    # 3. Estrai testo
    pages = _extract_pages(pdf_bytes)
    if not pages:
        raise ValueError("PDF vuoto o senza testo estraibile (potrebbe richiedere OCR).")

    # 4. Chunking + metadata enrichment in parallelo (D3+D4)
    text_excerpt = " ".join(p["text"] for p in pages[:3])[:1500]
    chunks, metadata = await asyncio.gather(
        asyncio.coroutine(_chunk_pages)(pages) if False else _chunk_pages_async(pages),
        enrich_document(filename, text_excerpt),
    )

    # 5. PostgreSQL — documento
    doc_id = db.insert_document(doc_id, sha256, filename, len(pages))
    db.update_document_metadata(
        doc_id,
        metadata["domain"],
        metadata["doc_type"],
        metadata["language"],
        metadata["year"],
        metadata["topics"],
    )

    result = await _embed_and_store(doc_id, filename, chunks, len(pages), metadata)

    # E6 — Audit log
    log_event("ingest", doc_id, {
        "filename": filename,
        "pages": len(pages),
        "chunks": result["chunks_created"],
        "domain": metadata["domain"],
        "sha256": sha256[:16],
    })

    # D1+D2+C6 — entity/relation extraction + KG build (background)
    asyncio.create_task(_run_knowledge_pipeline(doc_id, chunks))

    return result


async def _chunk_pages_async(pages: list[dict]) -> list[dict]:
    """Wrapper asincrono per _chunk_pages (sync) — permette gather con coro."""
    return _chunk_pages(pages)


async def ingest_markdown(filename: str, md_bytes: bytes) -> dict:
    """
    Ingestione diretta di un file Markdown (.md).
    Equivalente a ingest_pdf ma salta la conversione PDF→MD.
    """
    sha256 = hashlib.sha256(md_bytes).hexdigest()

    if db.document_exists(sha256):
        raise ValueError(
            f"Il documento '{filename}' è già presente nel corpus (SHA-256: {sha256[:12]}…). "
            "Nessuna reingestione necessaria."
        )

    doc_id = str(uuid.uuid4())

    # 1. MinIO — parsed/
    md_text = md_bytes.decode("utf-8", errors="replace")
    obj_store.upload_markdown(doc_id, md_text)

    # 2. Parsing pagine
    pages = markdown_to_pages(md_text)
    if not pages:
        raise ValueError("Markdown vuoto o non parsabile.")

    # 3. Chunking + metadata enrichment
    text_excerpt = " ".join(p["text"] for p in pages[:3])[:1500]
    chunks, metadata = await asyncio.gather(
        _chunk_pages_async(pages),
        enrich_document(filename, text_excerpt),
    )

    # 4. PostgreSQL — documento
    doc_id = db.insert_document(doc_id, sha256, filename, len(pages))
    db.update_document_metadata(
        doc_id,
        metadata["domain"],
        metadata["doc_type"],
        metadata["language"],
        metadata["year"],
        metadata["topics"],
    )

    result = await _embed_and_store(doc_id, filename, chunks, len(pages), metadata)

    log_event("ingest", doc_id, {
        "filename": filename,
        "pages": len(pages),
        "chunks": result["chunks_created"],
        "domain": metadata["domain"],
        "sha256": sha256[:16],
    })

    # D1+D2+C6 — entity/relation extraction + KG build (background)
    asyncio.create_task(_run_knowledge_pipeline(doc_id, chunks))

    return result


async def _embed_and_store(
    doc_id: str,
    filename: str,
    chunks: list[dict],
    page_count: int,
    metadata: dict | None = None,
) -> dict:
    """Embedding + upsert Qdrant + insert PostgreSQL (condiviso PDF e MD)."""
    meta = metadata or {}
    texts = [c["text"] for c in chunks]
    embeddings = await asyncio.gather(*[ollama.embed(t) for t in texts])

    points: list[PointStruct] = []
    chunk_records: list[tuple] = []

    for chunk, embedding in zip(chunks, embeddings):
        chunk_id = str(uuid.uuid4())

        points.append(
            PointStruct(
                id=chunk_id,
                vector=embedding,
                payload={
                    "chunk_id":    chunk_id,
                    "doc_id":      doc_id,
                    "filename":    filename,
                    "text":        chunk["text"],
                    "page_start":  chunk["page_start"],
                    "page_end":    chunk["page_end"],
                    "token_count": len(chunk["text"]) // 4,
                    # D3+D4 metadata fields (for G3 filtering)
                    "domain":   meta.get("domain", "unknown"),
                    "language": meta.get("language", "en"),
                    "doc_type": meta.get("doc_type", "research_paper"),
                    "year":     meta.get("year"),
                    "topics":   meta.get("topics", []),
                },
            )
        )
        chunk_records.append(
            (chunk_id, doc_id, chunk["text"], chunk["page_start"], chunk["page_end"])
        )

    # Qdrant — upsert vettori
    vec_store.upsert_points(points)

    # PostgreSQL — chunk (per FTS ibrida / fallback)
    db.insert_chunks(chunk_records)

    # OpenSearch — BM25 index (E3)
    from app.storage import opensearch as os_store
    os_chunks = [
        {
            "chunk_id": c_id,
            "doc_id":   doc_id,
            "filename": filename,
            "text":     chunk["text"],
            "page_start": chunk["page_start"],
            "domain":   meta.get("domain", ""),
            "language": meta.get("language", ""),
            "doc_type": meta.get("doc_type", ""),
        }
        for c_id, chunk in zip(
            [r[0] for r in chunk_records], chunks
        )
    ]
    os_store.index_chunks_bulk(os_chunks)

    # Tree Index — E5 (build hierarchy for adaptive retrieval)
    from app.indexing import tree_index
    tree_index.build_tree(doc_id)

    return {
        "doc_id":         doc_id,
        "filename":       filename,
        "pages":          page_count,
        "chunks_created": len(chunks),
    }


async def _run_knowledge_pipeline(doc_id: str, chunks: list[dict], max_chunks: int = 10) -> None:
    """
    D1+D2+C6 — Eseguito in background dopo _embed_and_store.
    Estrae entità (D1) e relazioni (D2) dai primi max_chunks chunk,
    poi costruisce il subgraph Neo4j (C6).
    """
    from app.services.knowledge_service import KnowledgeService
    from app.knowledge import kg_builder

    svc = KnowledgeService()
    chunk_ids = [r for r in db.get_chunks_for_doc(doc_id, limit=max_chunks)]

    for chunk_data in chunk_ids:
        try:
            entities = await svc.extract_entities(
                text=chunk_data["text"],
                doc_id=doc_id,
                chunk_id=chunk_data["chunk_id"],
                page=chunk_data["page_start"],
            )
            if entities:
                await svc.extract_relations(
                    text=chunk_data["text"],
                    entities=entities,
                    doc_id=doc_id,
                    chunk_id=chunk_data["chunk_id"],
                    page=chunk_data["page_start"],
                )
        except Exception as exc:
            logger.warning("D1/D2 extraction error for chunk %s: %s", chunk_data.get("chunk_id"), exc)

    # C6 — build Neo4j subgraph from extracted triples
    try:
        await asyncio.get_event_loop().run_in_executor(None, kg_builder.build_from_doc, doc_id)
        logger.info("C6 KG build completed for doc_id=%s", doc_id)
    except Exception as exc:
        logger.warning("C6 KG build error for doc_id=%s: %s", doc_id, exc)
