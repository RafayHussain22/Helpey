import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.document import Document
from app.models.user import User
from app.tasks.process_document import process_document
from app.tasks.sync_drive import sync_user_drive

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/documents", tags=["documents"])

# Statuses that indicate a sync is actively running
_ACTIVE_STATUSES = ("syncing", "downloaded", "processing")


@router.post("/sync")
async def trigger_sync(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Trigger a full Drive sync. No request body needed."""
    if not user.google_refresh_token:
        raise HTTPException(status_code=400, detail="Google Drive not connected")

    # Check if a sync is already running for this user
    result = await db.execute(
        select(func.count())
        .where(Document.synced_by_user_id == user.id, Document.status.in_(_ACTIVE_STATUSES))
    )
    active_count = result.scalar()
    if active_count and active_count > 0:
        return {"status": "already_running", "active_files": active_count}

    task = sync_user_drive.delay(user.id)
    return {"task_id": task.id, "status": "started"}


@router.get("")
async def list_documents(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List documents synced by this user."""
    result = await db.execute(
        select(Document)
        .where(Document.synced_by_user_id == user.id)
        .order_by(Document.created_at.desc())
    )
    docs = result.scalars().all()
    return [
        {
            "id": doc.id,
            "filename": doc.filename,
            "mime_type": doc.mime_type,
            "file_size_bytes": doc.file_size_bytes,
            "status": doc.status,
            "error_message": doc.error_message,
            "chunk_count": doc.chunk_count,
            "created_at": doc.created_at.isoformat(),
        }
        for doc in docs
    ]


@router.post("/{document_id}/reprocess")
async def reprocess_document(
    document_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Re-trigger processing for a failed document."""
    result = await db.execute(
        select(Document).where(Document.id == document_id)
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if doc.status not in ("downloaded", "failed"):
        raise HTTPException(status_code=400, detail=f"Cannot reprocess document in '{doc.status}' state")

    process_document.delay(doc.id)
    return {"status": "queued", "document_id": doc.id}


@router.post("/reprocess-failed")
async def reprocess_all_failed(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Re-trigger processing for all failed documents."""
    result = await db.execute(
        select(Document)
        .where(Document.status == "failed")
    )
    failed_docs = result.scalars().all()
    if not failed_docs:
        return {"status": "no_failed", "queued": 0}

    for doc in failed_docs:
        doc.status = "processing"
        doc.error_message = None
        process_document.delay(doc.id)
    await db.commit()

    return {"status": "queued", "queued": len(failed_docs)}


@router.get("/sync/status")
async def sync_status(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get sync status summary."""
    result = await db.execute(
        select(Document.status, func.count())
        .where(Document.synced_by_user_id == user.id)
        .group_by(Document.status)
    )
    counts = dict(result.all())

    pending = counts.get("pending", 0)
    syncing = counts.get("syncing", 0)
    downloaded = counts.get("downloaded", 0)
    processing = counts.get("processing", 0)

    # is_syncing is true if there are active documents OR the initial sync hasn't completed yet
    # (the task may still be enumerating/downloading files from Drive)
    is_syncing = (pending + syncing + downloaded + processing) > 0 or not user.initial_sync_done

    return {
        "initial_sync_done": user.initial_sync_done,
        "last_sync_at": user.last_sync_at.isoformat() if user.last_sync_at else None,
        "total": sum(counts.values()),
        "pending": pending,
        "syncing": syncing,
        "downloaded": downloaded,
        "processing": processing,
        "processed": counts.get("processed", 0),
        "failed": counts.get("failed", 0),
        "is_syncing": is_syncing,
    }
