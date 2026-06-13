import aiosqlite
import pytest


@pytest.fixture(autouse=True)
async def setup_db(tmp_path, monkeypatch):
    import services.bootstrap_service as bootstrap_service
    import services.task_command_service as task_command_service
    import services.task_planning_service as task_planning_service
    import services.task_query_service as task_query_service
    import services.note_service as note_service
    import services.tag_service as tag_service
    import services.subtask_service as subtask_service
    import services.pomodoro_service as pomodoro_service
    import services.calendar_sync_service as calendar_sync_service

    db_path = tmp_path / "test_task_planning.db"
    monkeypatch.setattr(bootstrap_service, "DB_PATH", db_path)
    monkeypatch.setattr(task_command_service, "DB_PATH", db_path)
    monkeypatch.setattr(task_planning_service, "DB_PATH", db_path)
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

    return task_planning_service


def test_task_planning_service_normalize_time_supports_multiple_formats(setup_db):
    task_planning_service = setup_db

    assert task_planning_service.normalize_time("2026-06-13")
    assert task_planning_service.normalize_time("6月14日")
    assert task_planning_service.normalize_time("06-15")
    assert task_planning_service.normalize_time("2026-06-13T10:00:00") == "2026-06-13T10:00:00"


def test_task_planning_service_generate_daily_plan_returns_distribution(setup_db):
    task_planning_service = setup_db

    daily_plan = task_planning_service.generate_daily_plan([
        {
            "task_name": "准备汇报",
            "due_time": "2026-06-15T09:00:00",
            "time_valid": True,
            "estimated_hours": 8.0,
        }
    ])

    assert isinstance(daily_plan, dict)
    assert daily_plan
    first_day = next(iter(daily_plan.values()))
    assert "tasks" in first_day
    assert "total_hours" in first_day


@pytest.mark.asyncio
async def test_task_planning_service_analyze_tasks_returns_existing_tasks(setup_db):
    task_planning_service = setup_db
    import services.task_command_service as task_command_service

    await task_command_service.add_task(
        task_name="已有任务",
        due_time="2026-06-15T12:00:00",
        start_time="2026-06-15T09:00:00",
    )

    analyzed = await task_planning_service.analyze_tasks([
        {"task_name": "准备汇报", "due_time": "2026-06-15", "recurrence": "once"},
    ])

    assert analyzed["status"] == "success"
    assert isinstance(analyzed["existing_tasks"], list)
    assert any(item["task_name"] == "已有任务" for item in analyzed["existing_tasks"])
