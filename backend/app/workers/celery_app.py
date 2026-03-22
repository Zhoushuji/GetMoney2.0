from celery import Celery

celery_app = Celery("leadgen")
celery_app.conf.update(
    broker_url="redis://redis:6379/0",
    result_backend="redis://redis:6379/1",
    task_serializer="json",
    result_expires=86400,
    worker_concurrency=4,
    task_soft_time_limit=300,
    task_time_limit=600,
    task_annotations={"workers.lead_tasks.scrape_domain": {"rate_limit": "10/m"}},
)
