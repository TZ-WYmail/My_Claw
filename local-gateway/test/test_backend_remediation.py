"""
Backend remediation tests
"""
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest


with tempfile.TemporaryDirectory() as temp_dir:
    temp_db_path = Path(temp_dir) / "test_backend_remediation.db"
    with patch('config.DB_PATH', temp_db_path), \
         patch('services.task_service.DB_PATH', temp_db_path), \
         patch('services.note_service.DB_PATH', temp_db_path), \
         patch('services.tag_service.DB_PATH', temp_db_path), \
         patch('services.subtask_service.DB_PATH', temp_db_path), \
         patch('services.pomodoro_service.DB_PATH', temp_db_path):
        from services.task_service import init_db, add_task, batch_update_tasks, get_task_detail
        from services.note_service import create_note
        from services.subtask_service import create_subtask
        from services.pomodoro_service import start_pomodoro


@pytest.fixture(autouse=True)
async def setup_db():
    await init_db()
    yield


@pytest.mark.asyncio
async def test_batch_update_tasks_updates_priority_and_tags():
    task1 = await add_task(task_name="批量1", due_time="2026-05-20T10:00:00")
    task2 = await add_task(task_name="批量2", due_time="2026-05-20T11:00:00")

    result = await batch_update_tasks(
        [task1["task_id"], task2["task_id"]],
        priority=0,
        tags_add=["batch", "urgent"],
    )

    assert result["status"] == "success"
    assert result["success_count"] == 2
    assert result["error_count"] == 0
    assert len(result["results"]) == 2


@pytest.mark.asyncio
async def test_get_task_detail_aggregates_related_data():
    task = await add_task(
        task_name="聚合任务",
        due_time="2026-05-21T10:00:00",
        description="detail",
    )
    task_id = task["task_id"]

    note = await create_note(
        title="聚合笔记",
        content="关联内容",
        tags=["x"],
        task_id=task_id,
    )
    assert note["status"] == "success"
    await create_subtask(task_id, "第一步")
    await start_pomodoro(task_id=task_id, duration_minutes=25)

    result = await get_task_detail(task_id)
    assert result["status"] == "success"
    assert result["task"]["task_id"] == task_id
    assert len(result["notes"]) == 1
    assert len(result["subtasks"]) == 1
    assert result["active_pomodoro"] is not None
    assert isinstance(result["weekly_neighbors"], list)
