from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import BaseModel


class Document(BaseModel):
    __tablename__ = "documents"
    __table_args__ = (
        UniqueConstraint("google_file_id", name="uq_google_file"),
    )

    synced_by_user_id: Mapped[str | None] = mapped_column(Text, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    google_file_id: Mapped[str] = mapped_column(Text, nullable=False)
    filename: Mapped[str] = mapped_column(Text, nullable=False)
    mime_type: Mapped[str] = mapped_column(Text, nullable=False)
    file_size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    local_path: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="pending", index=True)
    error_message: Mapped[str | None] = mapped_column(Text)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    celery_task_id: Mapped[str | None] = mapped_column(Text)
    google_modified_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    permissions: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    synced_by_user = relationship("User", back_populates="synced_documents")
    chunks = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan")
