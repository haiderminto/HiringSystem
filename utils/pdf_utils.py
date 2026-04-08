import base64
import logging

import fitz  # PyMuPDF

logger = logging.getLogger(__name__)


def validate_pdf(file_path: str) -> dict:
    """
    Validate a PDF file and return metadata.

    Returns:
        dict with keys: valid, page_count, error
    """
    try:
        doc = fitz.open(file_path)
        page_count = len(doc)
        doc.close()
        return {
            "valid": True,
            "page_count": page_count,
            "error": None,
            "unusual": page_count > 10
        }
    except Exception as e:
        logger.error(f"PDF validation failed: {e}")
        return {
            "valid": False,
            "page_count": 0,
            "error": str(e),
            "unusual": False
        }


def extract_text_from_pdf(file_path: str) -> str:
    """Extract plain text from a PDF using PyMuPDF."""
    try:
        doc = fitz.open(file_path)
        text_parts = []
        for page in doc:
            text_parts.append(page.get_text())
        doc.close()
        return "\n".join(text_parts).strip()
    except Exception as e:
        logger.error(f"PDF text extraction failed: {e}")
        return ""


def encode_pdf_base64(file_path: str) -> str:
    """Read a PDF file and return its base64-encoded content."""
    with open(file_path, "rb") as f:
        return base64.standard_b64encode(f.read()).decode("utf-8")
