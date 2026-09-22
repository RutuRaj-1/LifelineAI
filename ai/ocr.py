"""Document text extraction. Returns (text, status). Status: ok | empty | ocr_unavailable | error."""
from __future__ import annotations

import shutil
from pathlib import Path

IMAGE_EXT = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"}


def _ocr_image(path: Path) -> tuple[str, str]:
    if shutil.which("tesseract"):
        try:
            import pytesseract
            from PIL import Image

            return pytesseract.image_to_string(Image.open(path)), "ok"
        except Exception:  # noqa: BLE001
            pass
    try:  # DocTR is an optional, heavier alternative
        from doctr.io import DocumentFile
        from doctr.models import ocr_predictor

        result = ocr_predictor(pretrained=True)(DocumentFile.from_images(str(path)))
        return result.render(), "ok"
    except Exception:  # noqa: BLE001
        return "", "ocr_unavailable"


def _read_pdf(path: Path) -> tuple[str, str]:
    from pypdf import PdfReader

    text = "\n".join((p.extract_text() or "") for p in PdfReader(str(path)).pages).strip()
    if len(text) >= 20:
        return text, "ok"
    try:  # scanned PDF -> rasterise then OCR
        from pdf2image import convert_from_path
        import pytesseract

        return "\n".join(pytesseract.image_to_string(i) for i in convert_from_path(str(path))), "ok"
    except Exception:  # noqa: BLE001
        return text, "ocr_unavailable" if not text else "ok"


def extract_text(path: str | Path) -> tuple[str, str]:
    p = Path(path)
    ext = p.suffix.lower()
    try:
        if ext in {".txt", ".md", ".csv"}:
            text, status = p.read_text(encoding="utf-8", errors="ignore"), "ok"
        elif ext == ".pdf":
            text, status = _read_pdf(p)
        elif ext in IMAGE_EXT:
            text, status = _ocr_image(p)
        else:
            return "", "error"
    except Exception:  # noqa: BLE001
        return "", "error"
    text = text.strip()
    return text, (status if text or status != "ok" else "empty")
