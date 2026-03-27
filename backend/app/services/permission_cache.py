"""In-memory cache of allowed document IDs per user for fast permission filtering."""
import logging
from datetime import datetime, timezone

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.document import Document

logger = logging.getLogger(__name__)

# {user_id: {"doc_ids": set[str], "built_at": datetime}}
_cache: dict[str, dict] = {}


def build_allowed_docs(db: Session, user_id: str, user_email: str) -> set[str]:
    """Query the DB for all document IDs this user can access, cache the result."""
    user_domain = user_email.split("@")[1] if "@" in user_email else None

    permission_filters = [
        Document.permissions.is_(None),
        Document.permissions.contains([{"type": "anyone"}]),
        Document.permissions.contains([{"type": "user", "emailAddress": user_email}]),
    ]
    if user_domain:
        permission_filters.append(
            Document.permissions.contains([{"type": "domain", "domain": user_domain}]),
        )

    result = db.execute(
        select(Document.id)
        .where(Document.status == "processed")
        .where(or_(*permission_filters))
    )
    doc_ids = {row[0] for row in result.all()}

    _cache[user_id] = {
        "doc_ids": doc_ids,
        "built_at": datetime.now(timezone.utc),
    }
    logger.info("Built permission cache for user %s: %d accessible documents", user_id, len(doc_ids))
    return doc_ids


def get_allowed_docs(db: Session, user_id: str, user_email: str) -> set[str]:
    """Get cached allowed doc IDs, building the cache if needed."""
    entry = _cache.get(user_id)
    if entry is not None:
        return entry["doc_ids"]
    return build_allowed_docs(db, user_id, user_email)


def invalidate(user_id: str) -> None:
    """Clear the cache for a user. Call after sync completes."""
    _cache.pop(user_id, None)
    logger.info("Invalidated permission cache for user %s", user_id)


def invalidate_all() -> None:
    """Clear the entire permission cache. Call after any sync completes since documents are shared."""
    _cache.clear()
    logger.info("Invalidated entire permission cache")
