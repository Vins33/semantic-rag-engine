"""
PDF → Markdown converter (E1 parsed/ prefix).

Usa PyMuPDF per esportare ogni pagina in formato markdown.
Il risultato viene salvato in MinIO sotto parsed/{doc_id}.md.

Struttura output:
  ## Page 1
  [contenuto markdown pagina 1]

  ---

  ## Page 2
  [contenuto markdown pagina 2]
  ...
"""

import fitz  # PyMuPDF


def pdf_to_markdown(pdf_bytes: bytes) -> str:
    """
    Converte un PDF in testo markdown strutturato per pagina.
    Usa get_text('markdown') di PyMuPDF (>=1.24.2) con fallback a 'text'.
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pages_md: list[str] = []

    for i in range(len(doc)):
        page = doc[i]
        try:
            text = page.get_text("markdown")
        except Exception:
            text = page.get_text("text")

        text = text.replace("\x00", "").replace("\r", " ").strip()
        if text:
            pages_md.append(f"## Page {i + 1}\n\n{text}")

    doc.close()
    return "\n\n---\n\n".join(pages_md)


def markdown_to_pages(md_text: str) -> list[dict]:
    """
    Parsing di un markdown prodotto da pdf_to_markdown().
    Ritorna [{page: int, text: str}, ...] compatibile con il chunker.

    Funziona anche su markdown generici (senza ## Page N header):
    in quel caso tratta tutto come pagina 1.
    """
    import re

    # Split sul separatore di pagina "---" preceduto/seguito da ## Page N
    page_block_re = re.compile(r"\n\n---\n\n")
    blocks = page_block_re.split(md_text)

    header_re = re.compile(r"^##\s+Page\s+(\d+)\s*\n", re.MULTILINE)
    pages: list[dict] = []

    for block in blocks:
        block = block.strip()
        if not block:
            continue
        m = header_re.match(block)
        if m:
            page_num = int(m.group(1))
            text = block[m.end():].strip()
        else:
            # Markdown generico senza header di pagina
            page_num = len(pages) + 1
            text = block

        text = text.replace("\x00", "").replace("\r", " ").strip()
        if text:
            pages.append({"page": page_num, "text": text})

    return pages if pages else [{"page": 1, "text": md_text.strip()}]
