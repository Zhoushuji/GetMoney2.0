from celery import shared_task


@shared_task(name="workers.contact_tasks.run_contact_enrichment")
def run_contact_enrichment(task_id: str) -> dict:
    return {"task_id": task_id, "status": "queued"}
