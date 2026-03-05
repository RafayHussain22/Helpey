from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import settings

async_engine = create_async_engine(settings.DATABASE_URL, echo=False)
sync_engine = create_engine(settings.DATABASE_URL_SYNC, echo=False)
