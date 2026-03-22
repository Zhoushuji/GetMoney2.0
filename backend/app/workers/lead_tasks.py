from celery import shared_task


@shared_task(name="workers.lead_tasks.run_lead_search")
def run_lead_search(task_id: str) -> dict:
    return {"task_id": task_id, "status": "queued"}
