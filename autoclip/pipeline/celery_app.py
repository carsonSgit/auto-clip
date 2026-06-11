from celery import Celery

from autoclip.config import settings

celery_app = Celery(
    "autoclip",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["autoclip.pipeline.tasks"],
)

celery_app.conf.update(
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    broker_connection_retry_on_startup=True,
)
