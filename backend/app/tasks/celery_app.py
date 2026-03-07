from celery import Celery

from app.config import settings

celery_app = Celery(
    "helpey",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    result_expires=3600,
    task_track_started=True,
    broker_connection_retry_on_startup=True,
)

celery_app.conf.update(
    include=["app.tasks.sync_drive", "app.tasks.process_document"],
)
