"""
OCR fallback per PDF image-only (scansionati, grafici, poster).

Modello HuggingFace: facebook/nougat-base
  - Vision Encoder-Decoder addestrato su ~8M pagine di paper accademici
  - Comprende formule LaTeX, tabelle, layout multi-colonna
  - Output: testo/markdown con markup matematico (\( \), \[ \])

Caricamento lazy al primo utilizzo; il modello viene cachato in ~/.cache/huggingface.
GPU usata automaticamente se CUDA disponibile, altrimenti CPU (lento ma funziona).
"""

import logging

import fitz  # PyMuPDF — rendering pagine → immagine senza poppler
import torch
from PIL import Image

logger = logging.getLogger(__name__)

# ── Configurazione ─────────────────────────────────────────────────────────────

_MODEL_ID = "facebook/nougat-base"
_DEVICE   = "cuda" if torch.cuda.is_available() else "cpu"
_DPI_SCALE = 2.0   # 144 DPI — buon compromesso qualità/velocità su GPU

# ── Lazy-load ──────────────────────────────────────────────────────────────────

_processor = None
_model     = None


def _load() -> None:
    """Carica processor e modello nougat-base (solo al primo uso)."""
    global _processor, _model
    if _processor is not None:
        return

    from transformers import NougatProcessor, VisionEncoderDecoderModel

    logger.info(f"[OCR] Caricamento facebook/nougat-base su {_DEVICE} …")
    _processor = NougatProcessor.from_pretrained(_MODEL_ID)
    _model = (
        VisionEncoderDecoderModel
        .from_pretrained(_MODEL_ID)
        .to(_DEVICE)
    )
    _model.eval()
    logger.info("[OCR] Nougat pronto.")


# ── API pubblica ───────────────────────────────────────────────────────────────

def ocr_pdf(pdf_bytes: bytes) -> list[dict]:
    """
    Esegue OCR su tutte le pagine del PDF e restituisce
    [{page: int, text: str}, ...] (solo pagine con testo estratto).

    Usa PyMuPDF per rendering → PIL.Image → Nougat per la trascrizione.
    """
    _load()

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pages: list[dict] = []

    mat = fitz.Matrix(_DPI_SCALE, _DPI_SCALE)

    for i in range(len(doc)):
        # Render pagina come immagine RGB
        pix = doc[i].get_pixmap(matrix=mat, alpha=False)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

        # Preprocessing Nougat
        pixel_values = _processor(images=img, return_tensors="pt").pixel_values.to(_DEVICE)

        with torch.no_grad():
            output_ids = _model.generate(
                pixel_values,
                min_length=1,
                max_new_tokens=1500,
                bad_words_ids=[[_processor.tokenizer.unk_token_id]],
                return_dict_in_generate=True,
            ).sequences

        text = _processor.batch_decode(output_ids, skip_special_tokens=True)[0]

        # Pulizia per PostgreSQL
        text = text.replace("\x00", "").replace("\r", " ").strip()

        if text:
            pages.append({"page": i + 1, "text": text})

    doc.close()
    return pages
