from datetime import datetime

from sqlalchemy import Boolean, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import BaseModel


class User(BaseModel):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    picture_url: Mapped[str | None] = mapped_column(Text)
    google_id: Mapped[str | None] = mapped_column(Text, unique=True, nullable=True)
    google_access_token: Mapped[str | None] = mapped_column(Text)
    google_refresh_token: Mapped[str | None] = mapped_column(Text)
    token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    workos_user_id: Mapped[str | None] = mapped_column(Text, unique=True, nullable=True)
    initial_sync_done: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    synced_documents = relationship("Document", back_populates="synced_by_user", passive_deletes=True)
    chats = relationship("Chat", back_populates="user", cascade="all, delete-orphan")
