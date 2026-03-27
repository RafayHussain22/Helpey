"""Celery task: parse, chunk, embed a downloaded document."""
import logging

from sqlalchemy.orm import Session

from app.db.engine import sync_engine
from app.models.document import Document
from app.services.chunker import chunk_text
from app.services.document_parser import parse_document
from app.services.embeddings import store_chunks
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=2)
def process_document(self, document_id: str):
    """Parse a document, chunk it, generate embeddings, and store in pgvector."""
    with Session(sync_engine) as db:
        doc = db.get(Document, document_id)
        if not doc:
            logger.error("Document %s not found", document_id)
            return

        if not doc.local_path:
            doc.status = "failed"
            doc.error_message = "No local file path"
            db.commit()
            return

        doc.status = "processing"
        db.commit()

        try:
            # Step 1: Parse
            logger.info("Parsing document %s (%s)", doc.id, doc.filename)
            text = parse_document(doc.local_path)

            # Step 2: Chunk
            logger.info("Chunking document %s", doc.id)
            chunks = chunk_text(text)

            if not chunks:
                doc.status = "failed"
                doc.error_message = "No chunks produced from document"
                db.commit()
                return

            # Step 3: Embed and store
            logger.info("Embedding %d chunks for document %s", len(chunks), doc.id)
            count = store_chunks(db, doc.id, chunks)

            doc.chunk_count = count
            doc.status = "processed"
            doc.error_message = None
            db.commit()

            logger.info("Document %s processed: %d chunks stored", doc.id, count)
            return {"document_id": doc.id, "chunks": count}

        except Exception as e:
            logger.exception("Failed to process document %s", doc.id)
            doc.status = "failed"
            doc.error_message = str(e)[:500]
            db.commit()
            raise self.retry(exc=e, countdown=60)
