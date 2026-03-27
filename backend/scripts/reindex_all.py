"""One-time script to re-index all processed documents into pgvector.

Usage: cd backend && uv run python scripts/reindex_all.py
"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.engine import sync_engine
from app.models.document import Document
from app.tasks.process_document import process_document


def main():
    with Session(sync_engine) as db:
        result = db.execute(
            select(Document).where(Document.status == "processed")
        )
        docs = result.scalars().all()

        if not docs:
            print("No processed documents found.")
            return

        # Reset status so process_document will re-process them
        for doc in docs:
            doc.status = "downloaded"
            doc.chunk_count = 0
        db.commit()

        # Queue each for re-processing
        for doc in docs:
            process_document.delay(doc.id)

        print(f"Queued {len(docs)} documents for re-indexing into pgvector.")


if __name__ == "__main__":
    main()
