from celery import Celery

from app.config import settings

celery_app = Celery(
    settings.app_name,
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    task_default_queue="default",
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    imports=("app.tasks.events",),
    beat_schedule={
        "recover-stuck-deliveries-hourly": {
            "task": "events.recover_stuck_deliveries",
            "schedule": 300.0,
            "options": {"queue": "default"},
        },
    },
)
