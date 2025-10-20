"""PDF text extraction utility.

Uses PyMuPDF (fitz) to extract text from embedded PDF text. If pages have no
extractable text (scanned PDFs), an optional OCR fallback using pytesseract is
available. The module exposes a function `extract_text_from_pdf` and a small
CLI for convenience.

Notes:
- pytesseract requires the Tesseract binary installed on the system.
"""

from pathlib import Path
import logging
import tempfile
from typing import Optional

import fitz  # PyMuPDF

try:
    import pytesseract
    from PIL import Image
    _HAS_OCR = True
except Exception:
    pytesseract = None
    Image = None
    _HAS_OCR = False


logger = logging.getLogger(__name__)


def _page_image_from_pixmap(pix, fmt="png"):
    """Return a PIL Image created from a fitz.Pixmap."""
    if pix.n < 5:  # this is GRAY or RGB
        mode = "RGB" if pix.n == 3 else "L"
        img = Image.frombytes(mode, [pix.width, pix.height], pix.samples)
        return img

    # CMYK: convert
    pix = fitz.Pixmap(fitz.csRGB, pix)
    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    return img


def extract_text_from_pdf(
    pdf_path: str | Path,
    ocr: bool = False,
    dpi: int = 300,
    lang: str = "eng",
    tesseract_cmd: Optional[str] = None,
) -> str:
    """Extract text from a PDF file.

    Args:
        pdf_path: Path to the PDF file.
        ocr: If True, perform OCR on pages with no extractable text.
        dpi: Resolution used when rendering pages for OCR.
        lang: Tesseract language code (e.g., 'eng').
        tesseract_cmd: Optional path to tesseract executable. If provided,
            sets pytesseract.pytesseract.tesseract_cmd.

    Returns:
        Extracted text as a single string.
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(pdf_path)

    if tesseract_cmd and _HAS_OCR:
        pytesseract.pytesseract.tesseract_cmd = str(tesseract_cmd)

    doc = fitz.open(str(pdf_path))
    parts = []

    for page_number, page in enumerate(doc, start=1):
        text = page.get_text().strip()
        if text:
            parts.append(text)
            continue

        # No embedded text on this page.
        if ocr:
            if not _HAS_OCR:
                logger.warning("pytesseract or Pillow not available; skipping OCR")
                continue

            # Render page to an image for OCR
            mat = fitz.Matrix(dpi / 72, dpi / 72)
            pix = page.get_pixmap(matrix=mat)
            try:
                img = _page_image_from_pixmap(pix)
            finally:
                # explicit cleanup for PyMuPDF pixmap
                try:
                    pix = None
                except Exception:
                    pass

            ocr_text = pytesseract.image_to_string(img, lang=lang)
            parts.append(ocr_text)
        else:
            logger.debug("Page %d: no text and OCR disabled", page_number)

    return "\n\n".join(p.strip() for p in parts if p and p.strip())


if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Extract text from PDF with optional OCR")
    parser.add_argument("pdf", help="Path to PDF file")
    parser.add_argument("-o", "--output", help="Write extracted text to file")
    parser.add_argument("--ocr", action="store_true", help="Enable OCR for pages without text")
    parser.add_argument("--dpi", type=int, default=300, help="DPI to render pages at for OCR (default 300)")
    parser.add_argument("--lang", default="eng", help="Tesseract language code (default: eng)")
    parser.add_argument("--tesseract-cmd", help="Path to tesseract executable if not on PATH")
    parser.add_argument("--verbose", action="store_true")

    args = parser.parse_args()

    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level, format="%(levelname)s: %(message)s")

    try:
        text = extract_text_from_pdf(args.pdf, ocr=args.ocr, dpi=args.dpi, lang=args.lang, tesseract_cmd=args.tesseract_cmd)
    except Exception as exc:
        logger.exception("Failed to extract text: %s", exc)
        sys.exit(2)

    if args.output:
        out_path = Path(args.output)
        out_path.write_text(text, encoding="utf-8")
        logger.info("Wrote extracted text to %s", out_path)
    else:
        sys.stdout.write(text)
