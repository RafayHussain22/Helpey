"""OpenAI embeddings + pgvector storage."""
import logging

from openai import OpenAI
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.config import settings
from app.models.document_chunk import DocumentChunk
from app.services.permission_cache import get_allowed_docs

logger = logging.getLogger(__name__)

_openai_client: OpenAI | None = None

EMBEDDING_MODEL = "text-embedding-3-small"


def _get_openai() -> OpenAI:
    global _openai_client
    if _openai_client is None:
        if not settings.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY is not configured")
        _openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)
    return _openai_client


def generate_embeddings(texts: list[str]) -> list[list[float]]:
    """Generate embeddings using OpenAI text-embedding-3-small."""
    client = _get_openai()

    all_embeddings = []
    batch_size = 2048  # OpenAI supports large batches
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        response = client.embeddings.create(model=EMBEDDING_MODEL, input=batch)
        all_embeddings.extend([item.embedding for item in response.data])

    return all_embeddings


def store_chunks(db: Session, document_id: str, chunks: list[str]) -> int:
    """Embed chunks and store in Postgres via pgvector. Returns number stored."""
    if not chunks:
        return 0

    embeddings = generate_embeddings(chunks)

    for i, (text, embedding) in enumerate(zip(chunks, embeddings)):
        chunk = DocumentChunk(
            document_id=document_id,
            chunk_index=i,
            content=text,
            embedding=embedding,
        )
        db.add(chunk)

    db.flush()
    logger.info("Stored %d chunks for document %s", len(chunks), document_id)
    return len(chunks)


async def query_chunks(
    db: AsyncSession,
    user_id: str,
    user_email: str,
    query: str,
    n_results: int = 5,
) -> list[dict]:
    """Query pgvector for relevant chunks, filtered by cached permission set."""
    # Get allowed document IDs from cache (runs sync DB query on cache miss)
    from app.db.engine import sync_engine
    with Session(sync_engine) as sync_db:
        allowed_ids = get_allowed_docs(sync_db, user_id, user_email)

    if not allowed_ids:
        return []

    query_embedding = generate_embeddings([query])[0]

    stmt = (
        select(
            DocumentChunk.id,
            DocumentChunk.content,
            DocumentChunk.document_id,
            DocumentChunk.embedding.cosine_distance(query_embedding).label("distance"),
        )
        .where(DocumentChunk.document_id.in_(allowed_ids))
        .order_by("distance")
        .limit(n_results)
    )

    result = await db.execute(stmt)
    rows = result.all()

    return [
        {
            "id": row.id,
            "text": row.content,
            "document_id": row.document_id,
            "distance": row.distance,
        }
        for row in rows
    ]


def delete_document_chunks(db: Session, document_id: str) -> None:
    """Delete all chunks for a document."""
    result = db.execute(
        delete(DocumentChunk).where(DocumentChunk.document_id == document_id)
    )
    if result.rowcount:
        logger.info("Deleted %d chunks for document %s", result.rowcount, document_id)
