import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.user import User

logger = logging.getLogger(__name__)

GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
DRIVE_FILES_URL = "https://www.googleapis.com/drive/v3/files"

# Mime types we can process
SUPPORTED_MIME_TYPES = {
    "application/pdf",
    "application/vnd.google-apps.document",
    "application/vnd.google-apps.spreadsheet",
    "application/vnd.google-apps.presentation",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "text/plain",
    "text/csv",
    "text/html",
    "image/png",
    "image/jpeg",
}

# Google Workspace types need to be exported as different formats
EXPORT_MIME_MAP = {
    "application/vnd.google-apps.document": ("application/pdf", ".pdf"),
    "application/vnd.google-apps.spreadsheet": (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".xlsx",
    ),
    "application/vnd.google-apps.presentation": ("application/pdf", ".pdf"),
}


async def refresh_access_token(user: User, db: AsyncSession) -> str:
    """Get a valid Google access token, refreshing if needed."""
    if not user.google_refresh_token:
        raise ValueError("No refresh token available. User must re-authenticate.")

    # Always refresh to get a guaranteed-fresh token
    async with httpx.AsyncClient() as client:
        res = await client.post(GOOGLE_TOKEN_URL, data={
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "refresh_token": user.google_refresh_token,
            "grant_type": "refresh_token",
        })
        if res.status_code != 200:
            logger.error("Token refresh failed: %s %s", res.status_code, res.text[:200])
            # Fall back to stored token
            return user.google_access_token
        tokens = res.json()

    new_token = tokens["access_token"]
    user.google_access_token = new_token
    if "expires_in" in tokens:
        user.token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=tokens["expires_in"])
    await db.commit()

    logger.info("Refreshed token for user %s: %s...", user.id, new_token[:15])
    return new_token


async def list_drive_files(access_token: str, page_token: str | None = None, search: str | None = None) -> dict:
    """List files from user's Google Drive."""
    q_parts = ["trashed = false"]
    if search:
        q_parts.append(f"name contains '{search}'")

    params: dict[str, str | int] = {
        "pageSize": 100,
        "fields": "nextPageToken,files(id,name,mimeType,size,modifiedTime)",
        "q": " and ".join(q_parts),
        "orderBy": "modifiedTime desc",
    }
    if page_token:
        params["pageToken"] = page_token

    async with httpx.AsyncClient() as client:
        res = await client.get(
            DRIVE_FILES_URL,
            params=params,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        res.raise_for_status()
        return res.json()


async def download_drive_file(access_token: str, file_id: str, mime_type: str, dest_dir: str) -> tuple[str, str]:
    """Download a file from Google Drive. Returns (local_path, filename)."""
    dest = Path(dest_dir)
    dest.mkdir(parents=True, exist_ok=True)

    async with httpx.AsyncClient(timeout=300) as client:
        if mime_type in EXPORT_MIME_MAP:
            export_mime, ext = EXPORT_MIME_MAP[mime_type]
            # Get file name first
            meta_res = await client.get(
                f"{DRIVE_FILES_URL}/{file_id}",
                params={"fields": "name"},
                headers={"Authorization": f"Bearer {access_token}"},
            )
            meta_res.raise_for_status()
            filename = meta_res.json()["name"] + ext

            res = await client.get(
                f"{DRIVE_FILES_URL}/{file_id}/export",
                params={"mimeType": export_mime},
                headers={"Authorization": f"Bearer {access_token}"},
            )
        else:
            # Regular file download
            meta_res = await client.get(
                f"{DRIVE_FILES_URL}/{file_id}",
                params={"fields": "name"},
                headers={"Authorization": f"Bearer {access_token}"},
            )
            meta_res.raise_for_status()
            filename = meta_res.json()["name"]

            res = await client.get(
                f"{DRIVE_FILES_URL}/{file_id}",
                params={"alt": "media"},
                headers={"Authorization": f"Bearer {access_token}"},
            )

        res.raise_for_status()

        # Save with file_id prefix to avoid collisions
        safe_filename = f"{file_id}_{filename}"
        local_path = dest / safe_filename
        local_path.write_bytes(res.content)

        return str(local_path), filename
