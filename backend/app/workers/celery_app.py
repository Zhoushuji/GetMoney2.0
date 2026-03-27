from celery import Celery
from celery.schedules import crontab

from app.config import get_settings

settings = get_settings()
redis_backend_base = settings.redis_url.rsplit("/", 1)[0]

celery_app = Celery("leadgen")
celery_app.conf.update(
    broker_url=settings.redis_url,
    result_backend=f"{redis_backend_base}/1",
    task_serializer="json",
    result_expires=86400,
    worker_concurrency=4,
    task_soft_time_limit=300,
    task_time_limit=600,
    task_annotations={"workers.lead_tasks.scrape_domain": {"rate_limit": "10/m"}},
    beat_schedule={
        "refresh-due-search-keywords-hourly": {
            "task": "workers.keyword_refresh_tasks.refresh_due_search_keywords",
            "schedule": crontab(minute=0),
            "args": (20,),
        }
    },
)

# Import task modules so Celery can register named tasks.
from app.workers import keyword_refresh_tasks  # noqa: E402,F401
