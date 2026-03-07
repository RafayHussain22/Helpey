"""Semantic chunking using Chonkie."""
import logging

from chonkie import SemanticChunker

logger = logging.getLogger(__name__)

_chunker: SemanticChunker | None = None


def get_chunker() -> SemanticChunker:
    global _chunker
    if _chunker is None:
        _chunker = SemanticChunker(
            embedding_model="minishlab/potion-base-32M",
            chunk_size=400,
            chunk_overlap=50,
        )
    return _chunker


def chunk_text(text: str) -> list[str]:
    """Split text into semantic chunks. Returns list of chunk strings."""
    if not text.strip():
        return []

    chunker = get_chunker()
    chunks = chunker.chunk(text)
    result = [c.text for c in chunks if c.text.strip()]
    logger.info("Chunked text into %d chunks", len(result))
    return result
