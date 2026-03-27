from sqlalchemy import ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from pgvector.sqlalchemy import Vector

from app.db.base import BaseModel


class DocumentChunk(BaseModel):
    __tablename__ = "document_chunks"

    document_id: Mapped[str] = mapped_column(
        Text, ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding = mapped_column(Vector(1536), nullable=False)

    document = relationship("Document", back_populates="chunks")
