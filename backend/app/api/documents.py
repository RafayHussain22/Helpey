import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.document import Document
from app.models.user import User
from app.services.google_drive import list_drive_files, refresh_access_token
from app.tasks.process_document import process_document
from app.tasks.sync_drive import sync_user_drive

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/documents", tags=["documents"])


@router.get("/drive/files")
async def get_drive_files(
    page_token: str | None = Query(None),
    search: str | None = Query(None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List files from user's Google Drive, marking already-synced ones."""
    access_token = await refresh_access_token(user, db)
    data = await list_drive_files(access_token, page_token, search)

    # Get already-synced google file IDs
    result = await db.execute(
        select(Document.google_file_id, Document.status)
        .where(Document.user_id == user.id)
    )
    synced_map = dict(result.all())

    # Annotate files with sync status
    for f in data.get("files", []):
        f["synced"] = f["id"] in synced_map
        f["sync_status"] = synced_map.get(f["id"])

    return data


class SyncSelectedRequest(BaseModel):
    file_ids: list[str]


@router.post("/sync")
async def sync_selected_files(
    body: SyncSelectedRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Sync selected files from Google Drive."""
    if not body.file_ids:
        raise HTTPException(status_code=400, detail="No files selected")
    if len(body.file_ids) > 50:
        raise HTTPException(status_code=400, detail="Maximum 50 files per sync")

    access_token = await refresh_access_token(user, db)

    # Filter out already-synced files
    result = await db.execute(
        select(Document.google_file_id)
        .where(Document.user_id == user.id, Document.google_file_id.in_(body.file_ids))
    )
    existing = {row[0] for row in result.all()}
    new_file_ids = [fid for fid in body.file_ids if fid not in existing]

    if not new_file_ids:
        return {"status": "already_synced", "synced": 0}

    task = sync_user_drive.delay(user.id, access_token, new_file_ids)
    return {"task_id": task.id, "status": "started", "file_count": len(new_file_ids)}


@router.get("")
async def list_documents(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List user's synced documents."""
    result = await db.execute(
        select(Document)
        .where(Document.user_id == user.id)
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
        select(Document).where(Document.id == document_id, Document.user_id == user.id)
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if doc.status not in ("downloaded", "failed"):
        raise HTTPException(status_code=400, detail=f"Cannot reprocess document in '{doc.status}' state")

    process_document.delay(doc.id)
    return {"status": "queued", "document_id": doc.id}


@router.get("/sync/status")
async def sync_status(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get sync status summary."""
    result = await db.execute(
        select(Document.status, func.count())
        .where(Document.user_id == user.id)
        .group_by(Document.status)
    )
    counts = dict(result.all())
    return {
        "total": sum(counts.values()),
        "pending": counts.get("pending", 0),
        "syncing": counts.get("syncing", 0),
        "downloaded": counts.get("downloaded", 0),
        "processed": counts.get("processed", 0),
        "failed": counts.get("failed", 0),
    }
