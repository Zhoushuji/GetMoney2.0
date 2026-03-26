from datetime import datetime, timezone
import uuid

from app.models.task import Task
from app.services.workspace_store import task_to_status


def test_task_to_status_exposes_eta_and_search_budget_fields():
    now = datetime.now(timezone.utc)
    task = Task(
        id=uuid.uuid4(),
        type="lead_search",
        status="running",
        progress=45,
        total=20,
        completed=9,
        confirmed_leads=6,
        target_count=20,
        stopped_early=False,
        error=None,
        estimated_total_seconds=180,
        estimated_remaining_seconds=99,
        phase="searching",
        processed_search_requests=12,
        planned_search_requests=24,
        processed_candidates=15,
        planned_candidate_budget=40,
        created_at=now,
        updated_at=now,
    )

    serialized = task_to_status(task)

    assert serialized.status == "running"
    assert serialized.estimated_total_seconds == 180
    assert serialized.estimated_remaining_seconds == 99
    assert serialized.phase == "searching"
    assert serialized.processed_search_requests == 12
    assert serialized.planned_search_requests == 24
    assert serialized.processed_candidates == 15
    assert serialized.planned_candidate_budget == 40
    assert serialized.results_url == f"/api/v1/leads?task_id={task.id}"


def test_task_to_status_maps_completed_stopped_early_to_terminal_status():
    now = datetime.now(timezone.utc)
    task = Task(
        id=uuid.uuid4(),
        type="lead_search",
        status="completed",
        progress=100,
        total=20,
        completed=20,
        confirmed_leads=20,
        target_count=20,
        stopped_early=True,
        estimated_total_seconds=120,
        estimated_remaining_seconds=0,
        phase="completed",
        processed_search_requests=18,
        planned_search_requests=24,
        processed_candidates=20,
        planned_candidate_budget=40,
        created_at=now,
        updated_at=now,
    )

    serialized = task_to_status(task)

    assert serialized.status == "stopped_early"
    assert serialized.stopped_early is True
    assert serialized.estimated_remaining_seconds == 0
