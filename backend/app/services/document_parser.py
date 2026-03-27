"""3-tier document parsing: Docling -> PyMuPDF -> Claude Vision (OCR)."""
import base64
import logging
from pathlib import Path

import anthropic

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


def parse_with_claude_vision(file_path: str) -> str | None:
    """Tier 3: OCR using Claude Vision for scanned/image-based documents."""
    if not settings.ANTHROPIC_API_KEY:
        logger.warning("No Anthropic API key, skipping Vision OCR for %s", file_path)
        return None

    try:
        path = Path(file_path)
        suffix = path.suffix.lower()

        mime_map = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".webp": "image/webp",
            ".pdf": "application/pdf",
        }
        mime_type = mime_map.get(suffix)
        if not mime_type:
            logger.warning("Unsupported file type for Claude Vision: %s", suffix)
            return None

        file_data = base64.standard_b64encode(path.read_bytes()).decode("utf-8")
        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

        # Claude Vision uses image content blocks for images, document blocks for PDFs
        if suffix == ".pdf":
            content_block = {
                "type": "document",
                "source": {"type": "base64", "media_type": mime_type, "data": file_data},
            }
        else:
            content_block = {
                "type": "image",
                "source": {"type": "base64", "media_type": mime_type, "data": file_data},
            }

        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=8192,
            messages=[{
                "role": "user",
                "content": [
                    content_block,
                    {
                        "type": "text",
                        "text": "Extract all text content from this document. Preserve the structure (headings, lists, tables). Return only the extracted text, no commentary.",
                    },
                ],
            }],
        )

        text = response.content[0].text
        if text and len(text.strip()) > 20:
            logger.info("Claude Vision parsed %s successfully (%d chars)", file_path, len(text))
            return text
        return None
    except Exception as e:
        logger.warning("Claude Vision failed for %s: %s", file_path, e)
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

    # Tier 3: Claude Vision OCR (last resort for PDFs and images)
    if suffix in (".pdf", ".png", ".jpg", ".jpeg", ".gif", ".webp"):
        text = parse_with_claude_vision(file_path)
        if text:
            return text

    raise ValueError(f"Could not extract text from {file_path}")
