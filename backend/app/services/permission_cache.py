"""Shared in-memory permission cache with cross-process invalidation via DB version counter."""
import logging

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.models.document import Document

logger = logging.getLogger(__name__)

# Shared cache: {doc_id: permissions} or None = not loaded
_cache: dict[str, list | None] | None = None
_cache_version: int | None = None


def _get_db_version(db: Session) -> int:
    """Read the current cache version from the DB."""
    result = db.execute(text("SELECT version FROM cache_version WHERE id = 1"))
    row = result.one_or_none()
    return row[0] if row else 0


def _load_cache(db: Session) -> dict[str, list | None]:
    """Load all processed documents and their permissions into the shared cache."""
    global _cache, _cache_version

    result = db.execute(
        select(Document.id, Document.permissions)
        .where(Document.status == "processed")
    )
    _cache = {row[0]: row[1] for row in result.all()}
    _cache_version = _get_db_version(db)

    logger.info("Loaded permission cache: %d documents, version %d", len(_cache), _cache_version)
    return _cache


def _matches_user(permissions: list | None, user_email: str, user_domain: str | None) -> bool:
    """Check if a document's permissions grant access to a user."""
    if permissions is None:
        return True
    for perm in permissions:
        perm_type = perm.get("type")
        if perm_type == "anyone":
            return True
        if perm_type == "user" and perm.get("emailAddress") == user_email:
            return True
        if perm_type == "domain" and user_domain and perm.get("domain") == user_domain:
            return True
    return False


def get_allowed_docs(db: Session, user_id: str, user_email: str) -> set[str]:
    """Get document IDs this user can access, using the shared cache."""
    global _cache, _cache_version

    db_version = _get_db_version(db)
    if _cache is None or _cache_version != db_version:
        _load_cache(db)

    user_domain = user_email.split("@")[1] if "@" in user_email else None
    allowed = {
        doc_id
        for doc_id, permissions in _cache.items()
        if _matches_user(permissions, user_email, user_domain)
    }

    logger.info("User %s (%s): %d accessible documents", user_id, user_email, len(allowed))
    return allowed


def invalidate_all() -> None:
    """Increment the DB version counter so all processes reload on next query.

    Also clears the local cache for the current process.
    """
    global _cache, _cache_version

    from app.db.engine import sync_engine

    with Session(sync_engine) as db:
        db.execute(text("UPDATE cache_version SET version = version + 1 WHERE id = 1"))
        db.commit()

    _cache = None
    _cache_version = None
    logger.info("Invalidated permission cache (incremented DB version)")
