import aiosqlite
import pytest


@pytest.fixture(autouse=True)
async def setup_db(tmp_path, monkeypatch):
    import services.bootstrap_service as bootstrap_service
    import services.habit_service as habit_service
    import services.mobile_query_service as mobile_query_service
    import services.note_service as note_service
    import services.pomodoro_service as pomodoro_service
    import services.subtask_service as subtask_service
    import services.tag_service as tag_service
    import services.task_command_service as task_command_service
    import services.task_detail_service as task_detail_service
    import services.task_query_service as task_query_service
    import services.calendar_sync_service as calendar_sync_service

    db_path = tmp_path / "test_mobile_query.db"
    monkeypatch.setattr(bootstrap_service, "DB_PATH", db_path)
    monkeypatch.setattr(task_command_service, "DB_PATH", db_path)
    monkeypatch.setattr(task_detail_service, "DB_PATH", db_path)
    monkeypatch.setattr(task_query_service, "DB_PATH", db_path)
    monkeypatch.setattr(habit_service, "DB_PATH", db_path)
    monkeypatch.setattr(tag_service, "DB_PATH", db_path)
    monkeypatch.setattr(subtask_service, "DB_PATH", db_path)
    monkeypatch.setattr(pomodoro_service, "DB_PATH", db_path)
    monkeypatch.setattr(note_service, "DB_PATH", db_path)
    monkeypatch.setattr(calendar_sync_service, "DB_PATH", db_path)

    await bootstrap_service.init_db()
    async with aiosqlite.connect(str(db_path)) as db:
        await db.executescript(
            """
            DELETE FROM habit_checkins;
            DELETE FROM habits;
            DELETE FROM task_tags;
            DELETE FROM tags;
            DELETE FROM subtasks;
            DELETE FROM notes;
            DELETE FROM pomodoro_sessions;
            DELETE FROM tasks;
            """
        )
        await db.commit()

    return task_command_service, habit_service, mobile_query_service


@pytest.mark.asyncio
async def test_mobile_dashboard_snapshot_uses_domain_queries(setup_db):
    task_service, habit_service, mobile_query_service = setup_db

    first = await task_service.add_task(
        task_name="今天任务A",
        due_time="2026-06-13T09:00:00",
        priority=1,
    )
    await task_service.add_task(
        task_name="今天任务B",
        due_time="2026-06-13T11:00:00",
        priority=2,
    )
    await task_service.add_task(
        task_name="本周任务",
        due_time="2026-06-12T15:00:00",
        priority=3,
    )
    completed = await task_service.add_task(
        task_name="已完成任务",
        due_time="2026-06-13T12:00:00",
        priority=0,
    )
    await task_service.complete_task(completed["task_id"])

    created_habit = await habit_service.create_habit(name="晨跑", frequency="daily")
    await habit_service.checkin_habit(created_habit["habit_id"])

    snapshot = await mobile_query_service.get_mobile_dashboard_snapshot()

    assert [task["task_name"] for task in snapshot["today_tasks"]] == ["今天任务A", "今天任务B"]
    assert snapshot["pending_count"] == 3
    assert snapshot["week_tasks"] == 4
    assert len(snapshot["habits"]) == 1
    assert snapshot["habits"][0]["habit_id"] == created_habit["habit_id"]
    assert snapshot["habits"][0]["checked_in"] is True


@pytest.mark.asyncio
async def test_mobile_dashboard_snapshot_limits_today_tasks(setup_db):
    task_service, habit_service, mobile_query_service = setup_db

    for index in range(12):
        await task_service.add_task(
            task_name=f"任务{index:02d}",
            due_time=f"2026-06-13T{8 + index % 10:02d}:00:00",
            priority=index,
        )

    snapshot = await mobile_query_service.get_mobile_dashboard_snapshot()

    assert len(snapshot["today_tasks"]) == 10
    assert snapshot["today_tasks"][0]["task_name"] == "任务00"
