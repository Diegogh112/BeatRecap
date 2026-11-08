"""Configuración de la aplicación Celery."""

from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "faceswap",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    # Serialización
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,

    # Timeouts — videos de 5 min pueden tomar hasta 90 min en CPU
    task_soft_time_limit=7200,   # 2 horas soft limit
    task_time_limit=7800,        # 2h10 hard limit

    # Reintentos
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_max_retries=2,

    # Un solo worker para procesamiento de video (evitar OOM)
    worker_concurrency=1,
    worker_prefetch_multiplier=1,

    # Resultados
    result_expires=86400,        # 24 horas

    # Routing
    task_routes={
        "app.workers.tasks.run_face_detection": {"queue": "detection"},
        "app.workers.tasks.run_face_swap": {"queue": "processing"},
        "app.workers.tasks.cleanup_old_files": {"queue": "maintenance"},
    },
)
