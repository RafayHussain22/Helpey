from datetime import datetime, timezone

from sqlalchemy import Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.utils.id import generate_id


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class BaseModel(Base, TimestampMixin):
    __abstract__ = True

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=generate_id)
