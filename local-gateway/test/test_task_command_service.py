import aiosqlite
import pytest


@pytest.fixture(autouse=True)
async def setup_db(tmp_path, monkeypatch):
    import services.bootstrap_service as bootstrap_service
    import services.task_command_service as task_command_service
    import services.task_query_service as task_query_service
    import services.note_service as note_service
    import services.tag_service as tag_service
    import services.subtask_service as subtask_service
    import services.pomodoro_service as pomodoro_service
    import services.calendar_sync_service as calendar_sync_service

    db_path = tmp_path / "test_task_command.db"
    monkeypatch.setattr(bootstrap_service, "DB_PATH", db_path)
    monkeypatch.setattr(task_command_service, "DB_PATH", db_path)
    monkeypatch.setattr(task_query_service, "DB_PATH", db_path)
    monkeypatch.setattr(note_service, "DB_PATH", db_path)
    monkeypatch.setattr(tag_service, "DB_PATH", db_path)
    monkeypatch.setattr(subtask_service, "DB_PATH", db_path)
    monkeypatch.setattr(pomodoro_service, "DB_PATH", db_path)
    monkeypatch.setattr(calendar_sync_service, "DB_PATH", db_path)

    await bootstrap_service.init_db()
    async with aiosqlite.connect(str(db_path)) as db:
        await db.executescript(
            """
            DELETE FROM task_tags;
            DELETE FROM tags;
            DELETE FROM subtasks;
            DELETE FROM notes;
            DELETE FROM pomodoro_sessions;
            DELETE FROM download_history;
            DELETE FROM operation_logs;
            DELETE FROM tasks;
            """
        )
        await db.commit()

    return task_command_service, task_query_service


@pytest.mark.asyncio
async def test_task_command_service_add_and_complete_task(setup_db):
    task_command_service, task_query_service = setup_db

    created = await task_command_service.add_task(
        task_name="命令侧任务",
        due_time="2026-06-13T10:00:00",
        tags=["cmd"],
    )
    assert created["status"] == "success"

    stored = await task_query_service.get_task_by_id(created["task_id"])
    assert stored is not None
    assert stored["task_name"] == "命令侧任务"
    assert "cmd" in stored["tags"]

    completed = await task_command_service.complete_task(created["task_id"])
    assert completed["status"] == "success"

    finished = await task_query_service.get_task_by_id(created["task_id"])
    assert finished["status"] == "completed"
    assert finished["completed_at"] is not None


@pytest.mark.asyncio
async def test_task_command_service_batch_update_and_delete(setup_db):
    task_command_service, task_query_service = setup_db

    first = await task_command_service.add_task(
        task_name="批量任务A",
        due_time="2026-06-13T10:00:00",
    )
    second = await task_command_service.add_task(
        task_name="批量任务B",
        due_time="2026-06-14T10:00:00",
    )

    updated = await task_command_service.batch_update_tasks(
        task_ids=[first["task_id"], second["task_id"]],
        priority=0,
        tags_add=["hot"],
    )
    assert updated["status"] == "success"
    assert updated["success_count"] == 2

    first_row = await task_query_service.get_task_by_id(first["task_id"])
    second_row = await task_query_service.get_task_by_id(second["task_id"])
    assert first_row["priority"] == 0
    assert second_row["priority"] == 0
    assert "hot" in first_row["tags"]
    assert "hot" in second_row["tags"]

    deleted = await task_command_service.batch_delete_tasks([first["task_id"], second["task_id"]])
    assert deleted["status"] == "success"
    assert deleted["success_count"] == 2

    first_deleted = await task_query_service.get_task_by_id(first["task_id"])
    second_deleted = await task_query_service.get_task_by_id(second["task_id"])
    assert first_deleted["status"] == "deleted"
    assert second_deleted["status"] == "deleted"


@pytest.mark.asyncio
async def test_task_command_service_analyze_tasks_returns_planning_artifacts(setup_db):
    task_command_service, _ = setup_db

    analyzed = await task_command_service.analyze_tasks([
        {"task_name": "准备汇报", "due_time": "2026-06-15", "recurrence": "once"},
        {"task_name": "整理材料", "due_time": "6月16日", "recurrence": "once"},
    ])

    assert analyzed["status"] == "success"
    assert analyzed["total"] == 2
    assert len(analyzed["analyzed"]) == 2
    assert isinstance(analyzed["timeline"], list)
    assert isinstance(analyzed["daily_plan"], dict)
    assert isinstance(analyzed["daily_timeline"], list)
