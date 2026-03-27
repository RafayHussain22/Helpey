import logging
import time
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.engine import sync_engine
from app.models.document import Document
from app.models.user import User
from sqlalchemy.exc import IntegrityError

from app.services.embeddings import delete_document_chunks
from app.services.permission_cache import invalidate_all as invalidate_permission_cache_all
from app.services.google_drive import (
    EXPORT_MIME_MAP,
    SUPPORTED_MIME_TYPES,
    list_all_drive_files_sync,
    refresh_access_token_sync,
)
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

DRIVE_FILES_URL = "https://www.googleapis.com/drive/v3/files"

# Re-refresh token after this many seconds to avoid expiry during long syncs
TOKEN_REFRESH_INTERVAL = 45 * 60  # 45 minutes


def _download_file_sync(access_token: str, file_id: str, mime_type: str, dest_dir: str) -> tuple[str, str]:
    """Sync version of download_drive_file for use in Celery tasks."""
    import httpx
    from pathlib import Path

    dest = Path(dest_dir)
    dest.mkdir(parents=True, exist_ok=True)

    with httpx.Client(timeout=300) as client:
        if mime_type in EXPORT_MIME_MAP:
            export_mime, ext = EXPORT_MIME_MAP[mime_type]
            meta_res = client.get(
                f"{DRIVE_FILES_URL}/{file_id}",
                params={"fields": "name", "supportsAllDrives": True},
                headers={"Authorization": f"Bearer {access_token}"},
            )
            meta_res.raise_for_status()
            filename = meta_res.json()["name"] + ext

            res = client.get(
                f"{DRIVE_FILES_URL}/{file_id}/export",
                params={"mimeType": export_mime},
                headers={"Authorization": f"Bearer {access_token}"},
            )
        else:
            meta_res = client.get(
                f"{DRIVE_FILES_URL}/{file_id}",
                params={"fields": "name", "supportsAllDrives": True},
                headers={"Authorization": f"Bearer {access_token}"},
            )
            meta_res.raise_for_status()
            filename = meta_res.json()["name"]

            res = client.get(
                f"{DRIVE_FILES_URL}/{file_id}",
                params={"alt": "media", "supportsAllDrives": True},
                headers={"Authorization": f"Bearer {access_token}"},
            )

        res.raise_for_status()

        safe_filename = f"{file_id}_{filename}"
        local_path = dest / safe_filename
        local_path.write_bytes(res.content)

        return str(local_path), filename


def _parse_drive_modified_time(modified_time_str: str | None) -> datetime | None:
    """Parse Google Drive modifiedTime (RFC 3339) into a timezone-aware datetime."""
    if not modified_time_str:
        return None
    # Google returns ISO 8601 format like "2026-03-20T10:30:00.000Z"
    return datetime.fromisoformat(modified_time_str.replace("Z", "+00:00"))


@celery_app.task(bind=True, max_retries=3)
def sync_user_drive(self, user_id: str):
    """Sync ALL files from a user's Google Drive (including shared drives and shared-with-me)."""
    logger.info("Starting full Drive sync for user %s", user_id)

    # 1. Refresh token
    access_token = refresh_access_token_sync(user_id)
    last_refresh = time.monotonic()

    # 2. Enumerate all Drive files
    try:
        drive_files = list_all_drive_files_sync(access_token)
    except Exception as e:
        logger.error("Failed to enumerate Drive files for user %s: %s", user_id, e)
        raise self.retry(exc=e, countdown=60)

    logger.info("Found %d supported files in Drive for user %s", len(drive_files), user_id)

    with Session(sync_engine) as db:
        # 3. Diff against ALL existing documents (shared pool)
        result = db.execute(
            select(Document.google_file_id, Document.status, Document.google_modified_time)
        )
        existing = {
            row[0]: {"status": row[1], "modified_time": row[2]}
            for row in result.all()
            if row[0] is not None
        }

        files_to_create: list[dict] = []
        files_to_update: list[dict] = []
        files_existing_only_perms: list[dict] = []

        for f in drive_files:
            file_id = f["id"]
            drive_modified = _parse_drive_modified_time(f.get("modifiedTime"))

            if file_id not in existing:
                # New file — not yet in shared pool
                files_to_create.append(f)
            else:
                ex = existing[file_id]
                # Re-sync if file was modified since last sync and was previously processed
                if (
                    ex["status"] == "processed"
                    and drive_modified
                    and ex["modified_time"]
                    and drive_modified > ex["modified_time"]
                ):
                    files_to_update.append(f)
                else:
                    # File already exists and is up-to-date — just refresh permissions
                    files_existing_only_perms.append(f)

        logger.info(
            "User %s: %d new files, %d modified files, %d unchanged",
            user_id,
            len(files_to_create),
            len(files_to_update),
            len(drive_files) - len(files_to_create) - len(files_to_update),
        )

        # Update permissions and synced_by on existing unchanged files
        for f in files_existing_only_perms:
            result = db.execute(
                select(Document).where(Document.google_file_id == f["id"])
            )
            doc = result.scalar_one_or_none()
            if doc:
                doc.permissions = f.get("permissions")
                if doc.synced_by_user_id is None:
                    doc.synced_by_user_id = user_id
        db.commit()

        # Create new document records
        new_docs: list[tuple[Document, dict]] = []
        for f in files_to_create:
            doc = Document(
                synced_by_user_id=user_id,
                google_file_id=f["id"],
                filename=f["name"],
                mime_type=f["mimeType"],
                file_size_bytes=int(f.get("size", 0)) or None,
                status="syncing",
                google_modified_time=_parse_drive_modified_time(f.get("modifiedTime")),
                celery_task_id=self.request.id,
                permissions=f.get("permissions"),
            )
            db.add(doc)
            new_docs.append((doc, f))
        try:
            db.commit()
        except IntegrityError:
            # Race condition: another user synced the same file concurrently
            db.rollback()
            # Retry each individually, skipping duplicates
            new_docs = []
            for f in files_to_create:
                existing_doc = db.execute(
                    select(Document).where(Document.google_file_id == f["id"])
                ).scalar_one_or_none()
                if existing_doc:
                    existing_doc.permissions = f.get("permissions")
                    if existing_doc.synced_by_user_id is None:
                        existing_doc.synced_by_user_id = user_id
                else:
                    doc = Document(
                        synced_by_user_id=user_id,
                        google_file_id=f["id"],
                        filename=f["name"],
                        mime_type=f["mimeType"],
                        file_size_bytes=int(f.get("size", 0)) or None,
                        status="syncing",
                        google_modified_time=_parse_drive_modified_time(f.get("modifiedTime")),
                        celery_task_id=self.request.id,
                        permissions=f.get("permissions"),
                    )
                    db.add(doc)
                    new_docs.append((doc, f))
            db.commit()

        # Reset modified documents for re-sync
        update_docs: list[tuple[Document, dict]] = []
        for f in files_to_update:
            result = db.execute(
                select(Document).where(Document.google_file_id == f["id"])
            )
            doc = result.scalar_one()
            # Delete old chunks before re-indexing
            delete_document_chunks(db, doc.id)
            doc.status = "syncing"
            doc.synced_by_user_id = user_id
            doc.google_modified_time = _parse_drive_modified_time(f.get("modifiedTime"))
            doc.chunk_count = 0
            doc.error_message = None
            doc.celery_task_id = self.request.id
            doc.permissions = f.get("permissions")
            update_docs.append((doc, f))
        db.commit()

        # 4. Download and process all files that need syncing
        all_docs = new_docs + update_docs
        success_count = 0
        fail_count = 0
        uploads_dir = settings.UPLOADS_DIR

        for doc, f in all_docs:
            # Re-refresh token if needed
            elapsed = time.monotonic() - last_refresh
            if elapsed >= TOKEN_REFRESH_INTERVAL:
                try:
                    access_token = refresh_access_token_sync(user_id)
                    last_refresh = time.monotonic()
                except Exception as e:
                    logger.warning("Mid-sync token refresh failed: %s", e)

            try:
                local_path, _ = _download_file_sync(
                    access_token, f["id"], f["mimeType"], uploads_dir
                )
                doc.local_path = local_path
                doc.status = "downloaded"
                success_count += 1
                # Queue document processing
                from app.tasks.process_document import process_document
                process_document.delay(doc.id)
            except Exception as e:
                logger.error("Failed to download file %s (%s): %s", f["id"], f["name"], e)
                doc.status = "failed"
                doc.error_message = str(e)[:500]
                fail_count += 1
            db.commit()

        # 5. Mark sync complete and invalidate permission cache
        user = db.get(User, user_id)
        if user:
            user.initial_sync_done = True
            user.last_sync_at = datetime.now(timezone.utc)
            db.commit()

        invalidate_permission_cache_all()

        logger.info(
            "Drive sync complete for user %s: %d succeeded, %d failed",
            user_id, success_count, fail_count,
        )
        return {"synced": success_count, "failed": fail_count}
