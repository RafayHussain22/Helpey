"""Google Gemini embeddings + ChromaDB vector store."""
import logging

import chromadb
import google.generativeai as genai

from app.config import settings

logger = logging.getLogger(__name__)

_chroma_client: chromadb.ClientAPI | None = None


def get_chroma_client() -> chromadb.ClientAPI:
    global _chroma_client
    if _chroma_client is None:
        _chroma_client = chromadb.PersistentClient(path=settings.CHROMA_PERSIST_DIR)
    return _chroma_client


def get_collection(user_id: str) -> chromadb.Collection:
    """Get or create a ChromaDB collection for a user."""
    client = get_chroma_client()
    return client.get_or_create_collection(
        name=f"user_{user_id}",
        metadata={"hnsw:space": "cosine"},
    )


def generate_embeddings(texts: list[str]) -> list[list[float]]:
    """Generate embeddings using Google Gemini text-embedding-004."""
    if not settings.GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY is not configured")

    genai.configure(api_key=settings.GEMINI_API_KEY)

    model_name = "models/gemini-embedding-001"
    logger.info("Using embedding model: %s", model_name)

    # Gemini supports batches of up to 100 texts
    all_embeddings = []
    batch_size = 100
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        result = genai.embed_content(
            model=model_name,
            content=batch,
        )
        all_embeddings.extend(result["embedding"])

    return all_embeddings


def store_chunks(user_id: str, document_id: str, chunks: list[str]) -> int:
    """Embed chunks and store in ChromaDB. Returns number stored."""
    if not chunks:
        return 0

    collection = get_collection(user_id)
    embeddings = generate_embeddings(chunks)

    ids = [f"{document_id}_chunk_{i}" for i in range(len(chunks))]
    metadatas = [{"document_id": document_id, "chunk_index": i} for i in range(len(chunks))]

    collection.add(
        ids=ids,
        embeddings=embeddings,
        documents=chunks,
        metadatas=metadatas,
    )

    logger.info("Stored %d chunks for document %s", len(chunks), document_id)
    return len(chunks)


def query_chunks(user_id: str, query: str, n_results: int = 5) -> list[dict]:
    """Query ChromaDB for relevant chunks."""
    collection = get_collection(user_id)

    if collection.count() == 0:
        return []

    query_embedding = generate_embeddings([query])[0]

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=min(n_results, collection.count()),
        include=["documents", "metadatas", "distances"],
    )

    chunks = []
    for i in range(len(results["ids"][0])):
        chunks.append({
            "id": results["ids"][0][i],
            "text": results["documents"][0][i],
            "document_id": results["metadatas"][0][i]["document_id"],
            "distance": results["distances"][0][i],
        })

    return chunks


def delete_document_chunks(user_id: str, document_id: str) -> None:
    """Delete all chunks for a document from ChromaDB."""
    collection = get_collection(user_id)
    # Get all IDs with this document_id
    results = collection.get(where={"document_id": document_id})
    if results["ids"]:
        collection.delete(ids=results["ids"])
        logger.info("Deleted %d chunks for document %s", len(results["ids"]), document_id)
