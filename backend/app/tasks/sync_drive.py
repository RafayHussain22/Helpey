import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.engine import sync_engine
from app.models.document import Document
from app.services.google_drive import (
    SUPPORTED_MIME_TYPES,
    download_drive_file,
)
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

DRIVE_FILES_URL = "https://www.googleapis.com/drive/v3/files"


def _get_file_metadata_sync(access_token: str, file_id: str) -> dict:
    """Fetch metadata for a single file by ID."""
    import httpx

    with httpx.Client() as client:
        res = client.get(
            f"{DRIVE_FILES_URL}/{file_id}",
            params={"fields": "id,name,mimeType,size,modifiedTime"},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        res.raise_for_status()
        return res.json()


def _download_file_sync(access_token: str, file_id: str, mime_type: str, dest_dir: str) -> tuple[str, str]:
    """Sync version of download_drive_file for use in Celery tasks."""
    import httpx
    from pathlib import Path

    from app.services.google_drive import EXPORT_MIME_MAP

    dest = Path(dest_dir)
    dest.mkdir(parents=True, exist_ok=True)

    with httpx.Client(timeout=300) as client:
        if mime_type in EXPORT_MIME_MAP:
            export_mime, ext = EXPORT_MIME_MAP[mime_type]
            meta_res = client.get(
                f"{DRIVE_FILES_URL}/{file_id}",
                params={"fields": "name"},
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
                params={"fields": "name"},
                headers={"Authorization": f"Bearer {access_token}"},
            )
            meta_res.raise_for_status()
            filename = meta_res.json()["name"]

            res = client.get(
                f"{DRIVE_FILES_URL}/{file_id}",
                params={"alt": "media"},
                headers={"Authorization": f"Bearer {access_token}"},
            )

        res.raise_for_status()

        safe_filename = f"{file_id}_{filename}"
        local_path = dest / safe_filename
        local_path.write_bytes(res.content)

        return str(local_path), filename


@celery_app.task(bind=True, max_retries=3)
def sync_user_drive(self, user_id: str, access_token: str, file_ids: list[str] | None = None):
    """Sync files from a user's Google Drive. If file_ids given, only sync those."""
    logger.info("Starting Drive sync for user %s (selected: %s)", user_id, len(file_ids) if file_ids else "all")

    with Session(sync_engine) as db:
        # Get existing google_file_ids for this user
        result = db.execute(
            select(Document.google_file_id).where(Document.user_id == user_id)
        )
        existing_file_ids = {row[0] for row in result.all()}

        # Fetch metadata for selected files directly by ID
        files_to_sync = []
        for fid in (file_ids or []):
            if fid in existing_file_ids:
                continue
            try:
                meta = _get_file_metadata_sync(access_token, fid)
                files_to_sync.append(meta)
            except Exception as e:
                logger.error("Failed to get metadata for file %s: %s", fid, e)

        logger.info("Found %d new files to sync for user %s", len(files_to_sync), user_id)

        # Create document records as "syncing"
        doc_map = {}
        for f in files_to_sync:
            doc = Document(
                user_id=user_id,
                google_file_id=f["id"],
                filename=f["name"],
                mime_type=f["mimeType"],
                file_size_bytes=int(f.get("size", 0)) or None,
                status="syncing",
                celery_task_id=self.request.id,
            )
            db.add(doc)
            doc_map[f["id"]] = doc
        db.commit()

        # Download each file
        success_count = 0
        fail_count = 0
        uploads_dir = settings.UPLOADS_DIR

        for f in files_to_sync:
            doc = doc_map[f["id"]]
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
                logger.error("Failed to download file %s: %s", f["id"], e)
                doc.status = "failed"
                doc.error_message = str(e)[:500]
                fail_count += 1
            db.commit()

        logger.info(
            "Drive sync complete for user %s: %d succeeded, %d failed",
            user_id, success_count, fail_count,
        )
        return {"synced": success_count, "failed": fail_count}
