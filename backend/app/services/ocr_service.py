"""OCR service: extract text from base64-encoded images using pytesseract."""

import base64
import io
import os
import re
import sys
import logging
from PIL import Image

logger = logging.getLogger(__name__)

# ── Locate Tesseract executable ──────────────────────────────────────────────
_TESSERACT_CANDIDATES = [
    # PyInstaller bundle
    (os.path.join(sys._MEIPASS, 'tesseract', 'tesseract.exe') if getattr(sys, 'frozen', False) else None,
     os.path.join(sys._MEIPASS, 'tessdata') if getattr(sys, 'frozen', False) else None),
    # Standard install paths (dev mode)
    os.path.join(os.environ.get('PROGRAMFILES', 'C:/Program Files'), 'Tesseract-OCR'),
    os.path.join(os.environ.get('PROGRAMFILES(X86)', 'C:/Program Files (x86)'), 'Tesseract-OCR'),
    os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Programs', 'Tesseract-OCR'),
]


def _find_tesseract():
    """Return (tesseract_exe_path, tessdata_dir) or None."""
    for cand in _TESSERACT_CANDIDATES:
        if cand is None:
            continue
        if isinstance(cand, tuple):  # (exe, tessdata) from PyInstaller
            exe, td = cand
            if exe and os.path.exists(exe):
                return exe, td
        else:  # install directory from dev mode
            exe = os.path.join(cand, 'tesseract.exe')
            td = os.path.join(cand, 'tessdata')
            if os.path.exists(exe):
                return exe, td
    return None


_tess = _find_tesseract()
if _tess:
    import pytesseract
    tesseract_exe, tessdata_dir = _tess
    pytesseract.pytesseract.tesseract_cmd = tesseract_exe
    if tessdata_dir and os.path.exists(tessdata_dir):
        os.environ['TESSDATA_PREFIX'] = tessdata_dir
    logger.info("OCR tesseract_cmd set to: %s (tessdata: %s)", tesseract_exe, tessdata_dir)
else:
    logger.warning("Tesseract engine not found — OCR will be unavailable")


def _strip_data_uri_prefix(data_uri: str) -> bytes:
    match = re.match(r"^data:image/[a-zA-Z]+;base64,(.+)", data_uri)
    if not match:
        raise ValueError("Invalid data URI format")
    return base64.b64decode(match.group(1))


def ocr_image_from_base64(data_uri: str, lang: str = "chi_sim+eng") -> str:
    """Extract text from a base64 data URI image using Tesseract OCR."""
    try:
        image_bytes = _strip_data_uri_prefix(data_uri)
        image = Image.open(io.BytesIO(image_bytes))
        import pytesseract
        text = pytesseract.image_to_string(image, lang=lang)
        return text.strip()
    except ImportError:
        logger.warning("pytesseract is not installed — OCR unavailable")
        return ""
    except FileNotFoundError as e:
        logger.warning("Tesseract engine not found: %s", e)
        return ""
    except Exception as e:
        logger.error("OCR processing error: %s", e)
        return ""
