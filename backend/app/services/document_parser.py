"""3-tier document parsing: Docling -> PyMuPDF -> Gemini Vision (OCR)."""
import base64
import logging
from pathlib import Path

import google.generativeai as genai
import pymupdf

from app.config import settings

logger = logging.getLogger(__name__)


def parse_with_docling(file_path: str) -> str | None:
    """Tier 1: Parse document using Docling."""
    try:
        from docling.document_converter import DocumentConverter

        converter = DocumentConverter()
        result = converter.convert(file_path)
        text = result.document.export_to_markdown()
        if text and len(text.strip()) > 50:
            logger.info("Docling parsed %s successfully (%d chars)", file_path, len(text))
            return text
        logger.warning("Docling produced insufficient text for %s", file_path)
        return None
    except Exception as e:
        logger.warning("Docling failed for %s: %s", file_path, e)
        return None


def parse_with_pymupdf(file_path: str) -> str | None:
    """Tier 2: Parse PDF/images using PyMuPDF."""
    try:
        doc = pymupdf.open(file_path)
        pages = []
        for page in doc:
            text = page.get_text()
            if text.strip():
                pages.append(text)
        doc.close()

        if pages:
            full_text = "\n\n---\n\n".join(pages)
            logger.info("PyMuPDF parsed %s successfully (%d chars)", file_path, len(full_text))
            return full_text
        logger.warning("PyMuPDF extracted no text from %s", file_path)
        return None
    except Exception as e:
        logger.warning("PyMuPDF failed for %s: %s", file_path, e)
        return None


def parse_with_gemini_vision(file_path: str) -> str | None:
    """Tier 3: OCR using Gemini Vision for scanned/image-based documents."""
    if not settings.GEMINI_API_KEY:
        logger.warning("No Gemini API key, skipping Vision OCR for %s", file_path)
        return None

    try:
        path = Path(file_path)
        suffix = path.suffix.lower()

        genai.configure(api_key=settings.GEMINI_API_KEY)
        model = genai.GenerativeModel("gemini-2.5-flash-lite")

        mime_map = {
            ".pdf": "application/pdf",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".webp": "image/webp",
        }
        mime_type = mime_map.get(suffix)
        if not mime_type:
            logger.warning("Unsupported file type for Gemini Vision: %s", suffix)
            return None

        file_data = path.read_bytes()
        response = model.generate_content([
            {
                "mime_type": mime_type,
                "data": base64.standard_b64encode(file_data).decode("utf-8"),
            },
            "Extract all text content from this document. Preserve the structure (headings, lists, tables). Return only the extracted text, no commentary.",
        ])

        text = response.text
        if text and len(text.strip()) > 20:
            logger.info("Gemini Vision parsed %s successfully (%d chars)", file_path, len(text))
            return text
        return None
    except Exception as e:
        logger.warning("Gemini Vision failed for %s: %s", file_path, e)
        return None


def parse_document(file_path: str) -> str:
    """Parse a document using the 3-tier strategy. Returns extracted text."""
    path = Path(file_path)
    suffix = path.suffix.lower()

    # Plain text files - read directly
    if suffix in (".txt", ".csv", ".html", ".md"):
        text = path.read_text(encoding="utf-8", errors="replace")
        logger.info("Direct read of %s (%d chars)", file_path, len(text))
        return text

    # Tier 1: Docling (handles PDF, DOCX, PPTX, XLSX, images)
    text = parse_with_docling(file_path)
    if text:
        return text

    # Tier 2: PyMuPDF (PDF fallback)
    if suffix == ".pdf":
        text = parse_with_pymupdf(file_path)
        if text:
            return text

    # Tier 3: Gemini Vision OCR (last resort for PDFs and images)
    if suffix in (".pdf", ".png", ".jpg", ".jpeg", ".gif", ".webp"):
        text = parse_with_gemini_vision(file_path)
        if text:
            return text

    raise ValueError(f"Could not extract text from {file_path}")
